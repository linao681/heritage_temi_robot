"""Anonymous, frame-local person association over normalized detections."""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class PersonTrack:
    track_id: str
    bbox: tuple
    confidence: float
    observation_state: str
    last_seen_stamp_ns: int
    frame_id: str
    source: str = 'vision_tracker'
    distance_valid: bool = False
    distance_m: float | None = None


class PersonTracker:
    """Greedy IoU tracker with bounded linear prediction and short track expiry."""

    def __init__(self, *, iou_threshold=0.1, max_missed_sec=0.5, max_prediction_sec=0.3):
        if not 0 <= iou_threshold <= 1 or max_missed_sec <= 0 or max_prediction_sec < 0:
            raise ValueError('invalid tracker limits')
        self.iou_threshold = float(iou_threshold)
        self.max_missed_ns = int(max_missed_sec * 1e9)
        self.max_prediction_ns = int(max_prediction_sec * 1e9)
        self._epoch = 0
        self._next_id = 1
        self._last_stamp_ns = None
        self._tracks = {}

    @staticmethod
    def _valid_detection(detection):
        try:
            box = tuple(float(x) for x in detection['bbox'])
            confidence = float(detection['confidence'])
        except (KeyError, TypeError, ValueError):
            return None
        if (len(box) != 4 or not all(math.isfinite(x) for x in box + (confidence,)) or
                not 0 <= box[0] < box[2] <= 1 or not 0 <= box[1] < box[3] <= 1 or
                not 0 <= confidence <= 1):
            return None
        distance = detection.get('distance_m') if detection.get('distance_valid') else None
        if distance is not None:
            try:
                distance = float(distance)
            except (TypeError, ValueError):
                distance = None
            if distance is not None and (not math.isfinite(distance) or distance <= 0):
                distance = None
        return {'bbox': box, 'confidence': confidence,
                'distance_valid': distance is not None, 'distance_m': distance}

    @staticmethod
    def _iou(a, b):
        x1, y1 = max(a[0], b[0]), max(a[1], b[1])
        x2, y2 = min(a[2], b[2]), min(a[3], b[3])
        intersection = max(0., x2 - x1) * max(0., y2 - y1)
        area_a = (a[2] - a[0]) * (a[3] - a[1])
        area_b = (b[2] - b[0]) * (b[3] - b[1])
        union = area_a + area_b - intersection
        return intersection / union if union else 0.

    def _predicted_box(self, track, stamp_ns):
        elapsed = min(max(0, stamp_ns - track['stamp_ns']), self.max_prediction_ns)
        return tuple(max(0., min(1., value + velocity * elapsed / 1e9))
                     for value, velocity in zip(track['bbox'], track['velocity']))

    def update(self, detections, stamp_ns: int, frame_id: str) -> list[PersonTrack]:
        if type(stamp_ns) is not int or stamp_ns <= 0 or not isinstance(frame_id, str) or not frame_id:
            raise ValueError('a positive image timestamp and frame id are required')
        if self._last_stamp_ns is not None and stamp_ns == self._last_stamp_ns:
            raise ValueError('duplicate image timestamp')
        if self._last_stamp_ns is not None and stamp_ns < self._last_stamp_ns:
            self._tracks.clear()
            self._epoch += 1
        if self._last_stamp_ns is not None and stamp_ns - self._last_stamp_ns > self.max_missed_ns:
            self._tracks.clear()
            self._epoch += 1
        valid = [item for detection in detections
                 if (item := self._valid_detection(detection)) is not None]
        pairs = []
        for track_id, track in self._tracks.items():
            if stamp_ns - track['stamp_ns'] <= self.max_missed_ns:
                predicted = self._predicted_box(track, stamp_ns)
                pairs.extend((self._iou(predicted, item['bbox']), track_id, index)
                             for index, item in enumerate(valid))
        matches = {}
        used_tracks, used_detections = set(), set()
        for overlap, track_id, index in sorted(pairs, reverse=True):
            if overlap < self.iou_threshold:
                break
            if track_id not in used_tracks and index not in used_detections:
                matches[index] = track_id
                used_tracks.add(track_id)
                used_detections.add(index)
        result = []
        observed_track_ids = set()
        for index, detection in enumerate(valid):
            track_id = matches.get(index)
            previous = self._tracks.get(track_id) if track_id else None
            if previous is None:
                track_id = f'vision-e{self._epoch}-{self._next_id}'
                self._next_id += 1
                velocity = (0., 0., 0., 0.)
            else:
                dt = (stamp_ns - previous['stamp_ns']) / 1e9
                velocity = tuple((b - a) / dt for a, b in zip(previous['bbox'], detection['bbox']))
            current = {**detection, 'stamp_ns': stamp_ns, 'velocity': velocity,
                       'frame_id': frame_id}
            self._tracks[track_id] = current
            observed_track_ids.add(track_id)
            result.append(PersonTrack(track_id, current['bbox'], current['confidence'],
                                      'OBSERVED', stamp_ns, frame_id,
                                      distance_valid=current['distance_valid'],
                                      distance_m=current['distance_m']))
        for track_id, track in list(self._tracks.items()):
            if stamp_ns - track['stamp_ns'] > self.max_missed_ns:
                del self._tracks[track_id]
            elif track_id not in observed_track_ids:
                result.append(PersonTrack(track_id, self._predicted_box(track, stamp_ns),
                                          track['confidence'], 'TEMPORARILY_LOST',
                                          track['stamp_ns'], track['frame_id'],
                                          distance_valid=False))
        self._last_stamp_ns = stamp_ns
        return result
