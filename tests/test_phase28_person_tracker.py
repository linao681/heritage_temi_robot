import unittest

from visitor_perception.person_tracker import PersonTracker


class PersonTrackerTests(unittest.TestCase):
    def test_tracks_boxes_across_small_motion_without_using_external_ids(self):
        tracker = PersonTracker()
        first = tracker.update([{'bbox': (0.1, 0.1, 0.3, 0.6), 'confidence': 0.9}], 1_000_000_000, 'camera')
        second = tracker.update([{'bbox': (0.11, 0.1, 0.31, 0.6), 'confidence': 0.8,
                                  'track_id': 'gazebo_person_99'}], 1_100_000_000, 'camera')
        self.assertEqual(first[0].track_id, second[0].track_id)
        self.assertEqual(second[0].source, 'vision_tracker')
        self.assertNotEqual(second[0].track_id, 'gazebo_person_99')

    def test_short_miss_is_temporary_loss_and_expired_track_is_removed(self):
        tracker = PersonTracker(max_missed_sec=0.5)
        tracker.update([{'bbox': (0.1, 0.1, 0.3, 0.6), 'confidence': 0.9}], 1_000_000_000, 'camera')
        missed = tracker.update([], 1_200_000_000, 'camera')
        self.assertEqual(missed[0].observation_state, 'TEMPORARILY_LOST')
        expired = tracker.update([], 1_600_000_000, 'camera')
        self.assertEqual(expired, [])

    def test_invalid_time_does_not_create_or_advance_tracks(self):
        tracker = PersonTracker()
        with self.assertRaises(ValueError):
            tracker.update([{'bbox': (0.1, 0.1, 0.3, 0.6), 'confidence': 0.9}], 0, 'camera')

    def test_clock_reset_starts_new_epoch_without_reusing_old_track_id(self):
        tracker = PersonTracker()
        detection = {'bbox': (0.1, 0.1, 0.3, 0.6), 'confidence': 0.9}
        old_track = tracker.update([detection], 2_000_000_000, 'camera')[0]
        new_track = tracker.update([detection], 1_000_000_000, 'camera')[0]
        self.assertNotEqual(old_track.track_id, new_track.track_id)

