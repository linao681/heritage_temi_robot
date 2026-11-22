const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const replay = require('../visualization/ros_hall/replay.js');

async function fixture() {
  const manifest = {
    run_id: 'WP-REPLAY-01', status: 'PASS_WITH_RISK', archive_sha256: 'a'.repeat(64),
  };
  const manifestRaw = JSON.stringify(manifest);
  const manifestSha = crypto.createHash('sha256').update(manifestRaw).digest('hex');
  const imageSha = crypto.createHash('sha256').update(Buffer.from('png')).digest('hex');
  const payload = {
    schema_version: 1, mode: 'RECORDED_ROS2', run_id: manifest.run_id,
    source: {status: manifest.status, archive_sha256: manifest.archive_sha256,
      manifest_sha256: manifestSha, manifest_json_raw: manifestRaw,
      verified_source_files: [{path: 'rgb.png', sha256: imageSha}]},
    integrity: {source_manifest_sha256: manifestSha, source_archive_sha256: manifest.archive_sha256},
    events: [{event_id: 'e1', stamp_ns: 100, relative_time_ns: 0, data: {tracks: []}}],
    rgb_frames: [{path: 'rgb.png', sha256: imageSha, stamp_ns: 100,
      width: 2, height: 1, data_url: 'data:image/png;base64,cG5n'}],
    depth_frames: [], controls_available: false,
  };
  const jsonText = JSON.stringify(payload);
  const sha = crypto.createHash('sha256').update(jsonText).digest('hex');
  return {payload, jsonText, checksum: `${sha}  replay.json\n`};
}

(async () => {
  const f = await fixture();
  const parsed = await replay.verifyRecordingFiles(f.jsonText, f.checksum, 'replay.json');
  assert.equal(parsed.mode, 'RECORDED_ROS2');
  assert.equal(replay.nearestFrame(parsed.rgb_frames, 100).path, 'rgb.png');
  assert.equal(replay.nearestFrame(parsed.rgb_frames, 500_000_000), null);
  assert.deepEqual(replay.boxesForEvent(parsed.events[0]), []);

  await assert.rejects(() => replay.verifyRecordingFiles(f.jsonText, `${'0'.repeat(64)}  replay.json\n`, 'replay.json'), /SHA256/);
  const invalid = {...f.payload, mode: 'DEMO_SIMULATED'};
  const invalidText = JSON.stringify(invalid);
  const invalidHash = crypto.createHash('sha256').update(invalidText).digest('hex');
  await assert.rejects(() => replay.verifyRecordingFiles(invalidText, `${invalidHash}  replay.json`, 'replay.json'), /模式或版本/);

  const html = fs.readFileSync(path.join(__dirname, '../visualization/ros_hall/replay.html'), 'utf8');
  const js = fs.readFileSync(path.join(__dirname, '../visualization/ros_hall/replay.js'), 'utf8');
  const liveJs = fs.readFileSync(path.join(__dirname, '../visualization/ros_hall/ros-live.js'), 'utf8');
  assert.match(html, /RECORDED_ROS2/);
  assert.match(liveJs, /LIVE_ROS2/);
  assert.match(liveJs, /DEMO_SIMULATED/);
  assert.doesNotMatch(js, /fetch\(|XMLHttpRequest|\/api\/interact/);
  console.log('replay integrity and read-only checks passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
