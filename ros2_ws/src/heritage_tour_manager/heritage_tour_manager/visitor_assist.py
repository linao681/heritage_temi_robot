"""一次性 Mock 游客协作策略，全部方法由导览 asyncio loop 串行调用。"""

import time
from typing import Callable

from .tour_manager import TourManager, TourState


class VisitorAssist:
    def __init__(self, manager: TourManager, publish_expected: Callable[[int], None], timeout: float):
        self.manager = manager
        self._publish_expected = publish_expected
        self._timeout = timeout
        self.armed = False
        self.observed_empty = False
        self.active = False
        self.expected_count = 0
        self._visitor = None
        self._received = None
        self._frame = ''

    @staticmethod
    def _valid_schema(value):
        if not isinstance(value, dict) or value.get('source') != 'mock':
            return False
        if any(type(value.get(key)) is not bool for key in ('valid', 'stable', 'stable_fresh')):
            return False
        count, expected = value.get('people_count'), value.get('expected_count')
        if type(expected) is not int or expected < 0:
            return False
        if value['valid']:
            if type(count) is not int or count < 0:
                return False
        elif count is not None or value['stable'] or value['stable_fresh']:
            return False
        group = value.get('group_state')
        return (group in ('untracked', 'unknown', 'following', 'lost') and
                ((expected == 0) == (group == 'untracked')) and
                (not value['stable'] or value['stable_fresh']))

    def _current(self):
        if self._received is not None and time.monotonic() - self._received <= self._timeout:
            return self._visitor
        return None

    def _robot_ready(self):
        return (self._frame == 'mock_map' and self.manager.connected and
                self.manager.battery_percentage > self.manager.config.low_battery_threshold)

    def _group_reliable(self, value):
        return (value is not None and value['valid'] and value['stable_fresh'] and
                value['expected_count'] == self.expected_count and
                value['group_state'] == 'following' and value['people_count'] >= self.expected_count)

    def ready(self):
        """同意与恢复必须是最新且稳定的人数确认，而非事件重放。"""
        value = self._current()
        return bool(self.active and self._robot_ready() and not self.manager.is_moving and
                    self._group_reliable(value) and value['stable'])

    def disarm(self):
        self.armed = self.observed_empty = False

    def sync_terminal(self):
        if self.active and self.manager.outcome != 'running':
            self.active = False
            self.expected_count = 0
            self.disarm()
            self._publish_expected(0)

    def can_arm(self):
        value = self._current()
        return (not self.active and not self.armed and not self.manager.running and self._robot_ready() and
                not self.manager.is_moving and value is not None and value['expected_count'] == 0)

    def arm(self):
        self.sync_terminal()
        if not self.can_arm():
            return False
        self.armed = True
        self.observed_empty = False
        return True

    def manual_start(self):
        self.sync_terminal()
        self.disarm()
        return self.manager.start()

    def cancel(self):
        armed = self.armed
        self.disarm()
        return self.manager.cancel() or armed

    def manual_takeover(self):
        armed = self.armed
        self.disarm()
        return self.manager.manual_takeover() or armed

    def robot_frame(self, frame):
        self._frame = frame
        self.tick()

    def tick(self):
        self.sync_terminal()
        if self.armed:
            value = self._current()
            if not self._robot_ready() or self.manager.is_moving or value is None:
                self.disarm()
            elif not value['valid'] or not value['stable_fresh']:
                self.observed_empty = False
        if self.active:
            if not self.ready():
                self.manager.invalidate_visitor_resume()
            if self._frame != 'mock_map':
                self.manager.visitor_source_lost()
            elif (self.manager.consent_accepted and not self.manager.returning_low and
                  not self._group_reliable(self._current())):
                self.manager.visitor_lost()

    def observe(self, value):
        self._visitor = value if self._valid_schema(value) else None
        self._received = time.monotonic()
        self.tick()
        if not self.armed or self._visitor is None:
            return
        value = self._visitor
        if value['expected_count'] != 0:
            self.disarm()
            return
        if not (value['valid'] and value['stable'] and value['stable_fresh']):
            return
        if value['people_count'] == 0:
            self.observed_empty = True
        elif self.observed_empty:
            self.disarm()
            self.active = True
            self.expected_count = value['people_count']
            if self.manager.start(visitor_guard=self.ready):
                self._publish_expected(self.expected_count)
            else:
                self.active = False
                self.expected_count = 0

    def snapshot(self):
        ready = self.ready()
        if self.armed:
            waiting = '等待游客到来' if self.observed_empty else '等待稳定空场'
        elif self.active:
            waiting = ('等待人工确认' if ready else '等待有效稳定队伍或机器人停止') if (
                self.manager.state in (TourState.WAITING_CONSENT, TourState.PAUSED)) else ''
        else:
            waiting = '未启用本次协作'
        return {'armed': self.armed, 'observed_empty': self.observed_empty,
                'active': self.active, 'expected_count': self.expected_count,
                'can_arm': self.can_arm(),
                'can_accept': ready and self.manager.state is TourState.WAITING_CONSENT,
                'can_resume': ready and self.manager.state is TourState.PAUSED,
                'waiting_reason': waiting}
