"""独立监控快照和 Mock 控制门槛；未知或过期数据不视作当前状态。"""

from copy import deepcopy
import math


ACTIVE = {'IDLE', 'GREETING', 'WAITING_CONSENT', 'PLANNING', 'NAVIGATING', 'EXPLAINING', 'QA', 'PAUSED', 'RETURNING'}


def finite(value):
    return type(value) in (float, int) and math.isfinite(value)


class DashboardModel:
    def __init__(self, timeout=2.0, controls=False):
        self.timeout = timeout
        self.controls = controls
        self._data = {key: None for key in ('robot', 'tour', 'visitor', 'navigation')}

    def _valid(self, key, value):
        if not isinstance(value, dict):
            return False
        if key == 'robot':
            return (type(value.get('connected')) is bool and type(value.get('is_moving')) is bool and
                    isinstance(value.get('frame_id'), str) and isinstance(value.get('current_location'), str) and
                    all(finite(value.get(k)) for k in ('x', 'y', 'battery_percentage')))
        if key == 'tour':
            qa = value.get('qa_result')
            return (isinstance(value.get('state'), str) and value['state'] in ACTIVE | {'COMPLETED', 'ERROR'} and
                    isinstance(value.get('outcome'), str) and isinstance(value.get('target'), str) and
                    isinstance(value.get('visited'), list) and all(isinstance(x, str) for x in value['visited']) and
                    isinstance(value.get('history', []), list) and
                    (qa is None or (isinstance(qa, dict) and isinstance(qa.get('source', {}), dict))))
        if key == 'visitor':
            count = value.get('people_count')
            return (type(value.get('valid')) is bool and value.get('source') in ('mock', 'offline_video') and
                    ((type(count) is int and count >= 0) if value['valid'] else count is None))
        return all(isinstance(value.get(k), str) for k in ('target', 'status', 'description'))

    def update(self, key, value, now):
        self._data[key] = (now, deepcopy(value)) if self._valid(key, value) else None

    def snapshot(self, now):
        return {key: deepcopy(item[1]) if item is not None and now - item[0] <= self.timeout else None
                for key, item in self._data.items()}

    def commands(self, now):
        if not self.controls:
            return set()
        data = self.snapshot(now)
        robot, tour = data['robot'], data['tour']
        if (not robot or not tour or not robot['connected'] or robot['frame_id'] != 'mock_map' or
                tour['outcome'] != 'running' or tour['state'] not in ACTIVE):
            return set()
        result = {'cancel', 'manual_takeover'}
        if tour['state'] == 'PAUSED':
            assist = tour.get('visitor_assist', {})
            if not robot['is_moving'] and isinstance(assist, dict) and (not assist.get('active') or assist.get('can_resume') is True):
                result.add('resume')
        else:
            result.add('pause')
        return result
