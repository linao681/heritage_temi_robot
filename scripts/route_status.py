"""Shared validation for read-only Gazebo route status."""

import time


def fresh_status(status, received_at, now=None):
    now = time.monotonic() if now is None else now
    if not isinstance(status, dict) or now - received_at > 3:
        return None
    if status.get('state') not in ('NAVIGATING', 'ARRIVED', 'COMPLETED', 'ERROR'):
        return None
    return {key: status.get(key) for key in ('state', 'name', 'index', 'total', 'error')}
