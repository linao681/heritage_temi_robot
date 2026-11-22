"""Conservative team visibility assessment independent of Gazebo truth."""


class TeamObserver:
    def __init__(self, *, max_age_sec=0.5):
        if max_age_sec <= 0:
            raise ValueError('max_age_sec must be positive')
        self.max_age_ns = int(max_age_sec * 1e9)

    def observe(self, tracks, stamp_ns, sensor_valid, coverage, expected_count,
                sample_stamp_ns=None):
        ids = sorted(track.track_id for track in tracks
                     if track.observation_state == 'OBSERVED')
        age_ns = None if sample_stamp_ns is None else stamp_ns - sample_stamp_ns
        stale = (age_ns is not None and (age_ns < 0 or age_ns > self.max_age_ns))
        if stale:
            state = 'STALE'
        elif not sensor_valid:
            state = 'UNKNOWN'
        elif coverage == 'rear_uncovered':
            state = 'OUT_OF_VIEW'
        elif coverage != 'team_visible':
            state = 'UNKNOWN'
        elif expected_count > len(ids):
            state = 'TEMPORARILY_LOST' if ids else 'UNKNOWN'
        elif ids:
            state = 'OBSERVED'
        else:
            state = 'UNKNOWN'
        complete = state == 'OBSERVED' and len(ids) >= expected_count
        return {
            'schema_version': 1,
            'stamp_ns': stamp_ns,
            'frame_id': 'camera_optical_frame',
            'source': 'vision_tracker',
            'valid': bool(sensor_valid and not stale),
            'sample_age_sec': None if age_ns is None else max(0., age_ns / 1e9),
            'coverage': coverage,
            'observation_state': state,
            'observed_count': len(ids),
            'expected_count': expected_count,
            'track_ids': ids,
            'requires_manual_confirmation': not complete,
            'reason': ('rear camera coverage unavailable' if state == 'OUT_OF_VIEW'
                       else 'team count cannot be confirmed from current observation'
                       if not complete else 'visible anonymous tracks meet expected count'),
        }
