#!/usr/bin/env python3
"""Serve one hash-verified recorded ROS replay over loopback, without controls."""
import argparse
from dataclasses import dataclass
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

ALLOWED_STATUSES = {"PASS", "PASS_WITH_RISK", "FAIL"}
SHA256_RE = re.compile(r"^[a-f0-9]{64}$", re.IGNORECASE)
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ASSETS = ROOT / "visualization" / "ros_hall"


@dataclass(frozen=True)
class Resource:
    body: bytes
    content_type: str


def _read_file(path, *, inside=None):
    path = Path(path)
    if path.is_symlink():
        raise ValueError(f"symlink is not allowed: {path.name}")
    resolved = path.resolve(strict=True)
    if inside is not None and not resolved.is_relative_to(inside):
        raise ValueError("asset escapes the fixed replay asset directory")
    if not resolved.is_file():
        raise ValueError(f"not a regular file: {path.name}")
    return resolved.read_bytes()


def _validate_recording(payload):
    value = json.loads(payload)
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise ValueError("unsupported replay schema")
    if value.get("mode") != "RECORDED_ROS2":
        raise ValueError("only RECORDED_ROS2 recordings may be served")
    if value.get("controls_available") is not False:
        raise ValueError("recording is not read-only")
    if not isinstance(value.get("run_id"), str) or not value["run_id"]:
        raise ValueError("recording run id is missing")
    for key in ("events", "rgb_frames", "depth_frames"):
        if not isinstance(value.get(key), list):
            raise ValueError(f"recording field is invalid: {key}")
    source = value.get("source")
    integrity = value.get("integrity")
    if not isinstance(source, dict) or not isinstance(integrity, dict):
        raise ValueError("recording source integrity is missing")
    if source.get("status") not in ALLOWED_STATUSES:
        raise ValueError("recording source status is not allowed")
    archive_hash = source.get("archive_sha256")
    manifest_hash = source.get("manifest_sha256")
    if (not isinstance(archive_hash, str) or not SHA256_RE.fullmatch(archive_hash) or
            not isinstance(manifest_hash, str) or not SHA256_RE.fullmatch(manifest_hash)):
        raise ValueError("recording provenance hash is invalid")
    if (integrity.get("source_archive_sha256") != archive_hash or
            integrity.get("source_manifest_sha256") != manifest_hash):
        raise ValueError("recording provenance hashes do not match")
    manifest_raw = source.get("manifest_json_raw")
    if not isinstance(manifest_raw, str):
        raise ValueError("recording source manifest is missing")
    if hashlib.sha256(manifest_raw.encode("utf-8")).hexdigest() != manifest_hash.lower():
        raise ValueError("source manifest SHA256 mismatch")
    try:
        manifest = json.loads(manifest_raw)
    except json.JSONDecodeError as exc:
        raise ValueError("source manifest JSON is invalid") from exc
    if not isinstance(manifest, dict):
        raise ValueError("source manifest must be a JSON object")
    if (manifest.get("run_id") != value["run_id"] or
            manifest.get("status") != source.get("status") or
            manifest.get("archive_sha256") != archive_hash):
        raise ValueError("source manifest does not match recording")
    return value


def load_resources(assets_dir, recording_path, checksum_path=None):
    assets_dir = Path(assets_dir)
    if assets_dir.is_symlink():
        raise ValueError("symlink asset directory is not allowed")
    assets_root = assets_dir.resolve(strict=True)
    if not assets_root.is_dir():
        raise ValueError("replay assets must be a directory")

    recording_path = Path(recording_path)
    if checksum_path is None:
        checksum_path = Path(str(recording_path) + ".sha256")
    checksum_path = Path(checksum_path)
    recording_bytes = _read_file(recording_path)
    checksum_bytes = _read_file(checksum_path)
    checksum_text = checksum_bytes.decode("utf-8").strip()
    match = re.fullmatch(r"([a-f0-9]{64})  replay\.json", checksum_text, re.IGNORECASE)
    if not match:
        raise ValueError("replay SHA256 sidecar is invalid")
    if hashlib.sha256(recording_bytes).hexdigest() != match.group(1).lower():
        raise ValueError("replay JSON SHA256 mismatch")
    _validate_recording(recording_bytes)

    files = {
        "/": ("replay.html", "text/html; charset=utf-8"),
        "/replay.html": ("replay.html", "text/html; charset=utf-8"),
        "/replay.js": ("replay.js", "application/javascript; charset=utf-8"),
    }
    resources = {}
    for route, (name, mime) in files.items():
        asset = assets_root / name
        body = _read_file(asset, inside=assets_root)
        resources[route] = Resource(body, mime)
    resources["/recording/replay.json"] = Resource(recording_bytes, "application/json; charset=utf-8")
    resources["/recording/replay.json.sha256"] = Resource(checksum_bytes, "text/plain; charset=utf-8")
    return resources


def resolve_resource(request_target, resources):
    path = urlsplit(request_target).path
    return resources.get(path)


def make_handler(resources):
    class ReadOnlyReplayHandler(BaseHTTPRequestHandler):
        server_version = "HeritageReadOnlyReplay/1.0"

        def _send(self, include_body):
            resource = resolve_resource(self.path, resources)
            if resource is None:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", resource.content_type)
            self.send_header("Content-Length", str(len(resource.body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy",
                             "default-src 'self'; connect-src 'self'; img-src 'self' data:; "
                             "style-src 'self' 'unsafe-inline'; script-src 'self'; "
                             "object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
            self.end_headers()
            if include_body:
                self.wfile.write(resource.body)

        def do_GET(self):
            self._send(True)

        def do_HEAD(self):
            self._send(False)

    return ReadOnlyReplayHandler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recording", required=True, type=Path,
                        help="hash-verified replay.json exported by export_phase28_replay.py")
    parser.add_argument("--sha256", type=Path,
                        help="optional sidecar path; defaults to recording.json.sha256")
    parser.add_argument("--port", type=int, default=8099)
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error("port must be between 0 and 65535")
    try:
        resources = load_resources(DEFAULT_ASSETS, args.recording, args.sha256)
        server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(resources))
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(f"Read-only replay for {json.loads(resources['/recording/replay.json'].body)['run_id']}: "
          f"http://127.0.0.1:{server.server_address[1]}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
