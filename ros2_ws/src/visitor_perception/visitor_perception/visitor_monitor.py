"""无 ROS2 依赖的稳定人数及团队事件判断。"""

from dataclasses import dataclass
import math
import time

import yaml


@dataclass(frozen=True)
class VisitorConfig:
    stable_samples: int = 3
    stale_timeout_sec: float = 2.0
    count_source: str = 'mock'

    def __post_init__(self):
        if type(self.stable_samples) is not int or self.stable_samples < 1:
            raise ValueError('stable_samples 必须为正整数')
        if (type(self.stale_timeout_sec) not in (int, float) or
                not math.isfinite(self.stale_timeout_sec) or self.stale_timeout_sec <= 0):
            raise ValueError('stale_timeout_sec 必须为有限正数')
        if self.count_source not in ('mock', 'offline_video', 'camera'):
            raise ValueError('count_source 仅支持 mock、offline_video 或 camera')

    @classmethod
    def from_yaml(cls, path):
        with open(path, encoding='utf-8') as file:
            return cls(**yaml.safe_load(file)['visitor_perception'])


class VisitorMonitor:
    """按调用方提供的单调时间去抖，未知观测不等于无人。"""

    def __init__(self, config: VisitorConfig):
        self.config = config
        self._last_sample = None
        self._candidate = None
        self._consecutive = 0
        self._stable_count = None
        self._last_confirmed = None
        self._stable_fresh = False
        self._valid = False
        self._stale = False
        self._expected = 0
        self._group_lost = None

    def snapshot(self, now: float | None = None) -> dict:
        now = time.monotonic() if now is None else now
        if self._expected == 0:
            group = 'untracked'
        elif not self._valid or self._group_lost is None:
            group = 'unknown'
        else:
            group = 'lost' if self._group_lost else 'following'
        return {'valid': self._valid,
                'people_count': self._stable_count if self._valid else None,
                'expected_count': self._expected, 'group_state': group, 'source': self.config.count_source,
                'stable': self._valid and self._stable_fresh and
                          self._consecutive >= self.config.stable_samples,
                'stable_fresh': self._valid and self._stable_fresh,
                'sample_timestamp_monotonic_sec': self._last_confirmed,
                'sample_age_sec': (max(0.0, now - self._last_confirmed)
                                   if self._last_confirmed is not None else None)}

    def _reset_candidate(self):
        self._candidate = None
        self._consecutive = 0

    def tick(self, now: float) -> list[str]:
        """断流时保留历史比较基准，禁止以零人数替代未知数据。"""
        if (self._last_confirmed is not None and
                now - self._last_confirmed > self.config.stale_timeout_sec):
            self._stable_fresh = False
        if (self._last_sample is not None and not self._stale and
                now - self._last_sample > self.config.stale_timeout_sec):
            self._valid = False
            self._stale = True
            self._reset_candidate()
            return ['data_stale']
        return []

    def set_expected_count(self, count: int, now: float) -> list[str]:
        """由上层显式设置预期人数；同值不重复开启团队。"""
        events = self.tick(now)
        if type(count) is int and count >= 0 and count != self._expected:
            self._expected = count
            self._group_lost = None
        return events

    def observe(self, count: int, now: float) -> list[str]:
        """仅稳定合法人数变化产生事件，负数观测不续期。"""
        events = self.tick(now)
        if type(count) is not int or count < 0:
            self._reset_candidate()
            return events
        if (self._last_sample is not None and
                now - self._last_sample > self.config.stale_timeout_sec):
            self._reset_candidate()
        self._last_sample = now
        if count != self._candidate:
            self._candidate, self._consecutive = count, 1
        else:
            self._consecutive = min(self._consecutive + 1, self.config.stable_samples)
        if self._consecutive < self.config.stable_samples:
            return events

        previous = self._stable_count
        self._stable_count = count
        self._last_confirmed = now
        self._stable_fresh = True
        self._valid = True
        if self._stale:
            self._stale = False
            events.append('data_restored')
        if (previous is None or previous == 0) and count > 0:
            events.append('arrival')
        elif previous is not None and previous > 0 and count == 0:
            events.append('departure')

        if self._expected > 0:
            lost = count < self._expected
            if lost and self._group_lost is not True:
                events.append('visitor_lost')
            elif not lost and self._group_lost is True:
                events.append('regrouped')
            self._group_lost = lost
        return events
