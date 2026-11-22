import unittest

from visitor_perception.team_observer import TeamObserver


class TeamObserverTests(unittest.TestCase):
    def test_camera_blind_spot_does_not_claim_people_are_lost(self):
        observer = TeamObserver()
        result = observer.observe([], 1_000_000_000, True, 'rear_uncovered', 3)
        self.assertEqual(result['observation_state'], 'OUT_OF_VIEW')
        self.assertEqual(result['source'], 'vision_tracker')
        self.assertEqual(result['observed_count'], 0)
        self.assertTrue(result['requires_manual_confirmation'])

    def test_stale_or_invalid_sensor_is_unknown_and_requires_confirmation(self):
        observer = TeamObserver(max_age_sec=0.5)
        stale = observer.observe([], 1_600_000_000, True, 'forward', 3,
                                 sample_stamp_ns=1_000_000_000)
        invalid = observer.observe([], 1_000_000_000, False, 'forward', 3)
        self.assertEqual(stale['observation_state'], 'STALE')
        self.assertEqual(invalid['observation_state'], 'UNKNOWN')
        self.assertTrue(stale['requires_manual_confirmation'])
        self.assertTrue(invalid['requires_manual_confirmation'])

    def test_current_forward_view_reports_observation_without_identity_claim(self):
        observer = TeamObserver()
        track = type('Track', (), {'track_id': 'vision-epoch1-1',
                                   'observation_state': 'OBSERVED'})()
        result = observer.observe([track], 1_000_000_000, True, 'team_visible', 3)
        self.assertEqual(result['observation_state'], 'TEMPORARILY_LOST')
        self.assertEqual(result['track_ids'], ['vision-epoch1-1'])
        self.assertTrue(result['requires_manual_confirmation'])

    def test_full_count_in_partial_forward_coverage_does_not_confirm_team(self):
        observer = TeamObserver()
        tracks = [type('Track', (), {'track_id': f'vision-e1-{i}',
                                     'observation_state': 'OBSERVED'})()
                  for i in range(3)]
        result = observer.observe(tracks, 1_000_000_000, True, 'forward_only', 3)
        self.assertEqual(result['observation_state'], 'UNKNOWN')
        self.assertTrue(result['requires_manual_confirmation'])

