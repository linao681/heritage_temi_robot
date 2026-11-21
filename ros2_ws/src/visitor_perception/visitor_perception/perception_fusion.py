"""Validate and fuse visitor, person-depth, laser, robot and tour snapshots."""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class FusionConfig:
    max_sample_age_sec: float = 1.0
    front_half_angle_rad: float = math.pi / 3
    scan_min_valid_samples: int = 1
    simulation_mode: bool = False

    def __post_init__(self):
        if not math.isfinite(self.max_sample_age_sec) or self.max_sample_age_sec <= 0:
            raise ValueError('max_sample_age_sec 必须为有限正数')
        if not math.isfinite(self.front_half_angle_rad) or not 0 < self.front_half_angle_rad <= math.pi:
            raise ValueError('front_half_angle_rad 必须在 0 到 π 之间')
        if type(self.scan_min_valid_samples) is not int or self.scan_min_valid_samples < 1:
            raise ValueError('scan_min_valid_samples 必须为正整数')


class PerceptionFusion:
    """Fusion state uses one local monotonic clock and fails closed on missing inputs."""

    def __init__(self, max_sample_age_sec=1.0, front_half_angle_rad=math.pi / 3,
                 scan_min_valid_samples=1, simulation_mode=False):
        self.config = FusionConfig(max_sample_age_sec, front_half_angle_rad,
                                   scan_min_valid_samples, simulation_mode)
        self._visitor = None
        self._people = None
        self._scan_at = None
        self.obstacle_distance_m = None
        self._robot = None
        self._tour = None
        self._navigation = None
        self._safety_stop = None

    @staticmethod
    def _finite(value):
        return type(value) in (int, float) and math.isfinite(value)

    def update_visitor(self, value, now):
        source = value.get('source') if isinstance(value, dict) else None
        count = value.get('people_count') if isinstance(value, dict) else None
        producer_age = value.get('sample_age_sec', 0.0) if isinstance(value, dict) else None
        received_at = now - producer_age if self._finite(producer_age) and producer_age >= 0 else now
        valid = (source in ('camera', 'temi_camera', 'mock', 'offline_video') and
                 type(value.get('valid')) is bool and value['valid'] and
                 type(value.get('stable')) is bool and value['stable'] and
                 type(value.get('stable_fresh')) is bool and value['stable_fresh'] and
                 type(count) is int and count >= 0 and
                 type(value.get('expected_count')) is int and value['expected_count'] >= 0 and
                 value.get('group_state') in ('following', 'lost', 'unknown', 'untracked'))
        self._visitor = {'source': source, 'valid': valid, 'people_count': count if valid else None,
                         'expected_count': value.get('expected_count') if valid else None,
                         'group_state': value.get('group_state') if valid else 'unknown', 'at': received_at}

    def update_people(self, value, now):
        value = value if isinstance(value, dict) else {}
        source = value.get('source')
        distance = value.get('nearest_person_m')
        density = value.get('crowd_density')
        distance_valid = (value.get('valid') is True and value.get('person_distance_valid') is True and
                          self._finite(distance) and distance >= 0 and
                          source in ('temi_rgbd', 'gazebo_rgbd', 'mock', 'offline_video'))
        density_valid = (value.get('valid') is True and value.get('crowd_density_valid') is True and
                         self._finite(density) and 0 <= density <= 1 and
                         source in ('temi_rgbd', 'gazebo_rgbd', 'mock', 'offline_video'))
        producer_age = value.get('sample_age_sec', 0.0)
        received_at = now - producer_age if self._finite(producer_age) and producer_age >= 0 else now
        self._people = {'source': source, 'distance_valid': distance_valid,
                        'nearest_person_m': float(distance) if distance_valid else None,
                        'density_valid': density_valid,
                        'crowd_density': float(density) if density_valid else None, 'at': received_at}

    def update_scan(self, ranges, angle_min, angle_increment, range_min, range_max, now):
        self._scan_at = now
        self.obstacle_distance_m = None
        values = (angle_min, angle_increment, range_min, range_max)
        try:
            ranges = list(ranges)
        except TypeError:
            return
        if (not ranges or not all(self._finite(value) for value in values) or angle_increment == 0 or
                range_min < 0 or range_max <= range_min):
            return
        samples = []
        for index, distance in enumerate(ranges):
            angle = angle_min + index * angle_increment
            if abs(math.atan2(math.sin(angle), math.cos(angle))) > self.config.front_half_angle_rad:
                continue
            if self._finite(distance) and range_min <= distance <= range_max:
                samples.append(float(distance))
        if len(samples) >= self.config.scan_min_valid_samples:
            self.obstacle_distance_m = min(samples)

    def update_robot(self, value, now):
        value = value if isinstance(value, dict) else {}
        self._robot = {
            'connected': value.get('connected') is True,
            'frame_id': value.get('frame_id') if isinstance(value.get('frame_id'), str) else '',
            'position_valid': all(self._finite(value.get(key)) for key in ('x', 'y', 'yaw')),
            'error_message': value.get('error_message', ''),
            'at': now,
        }

    def update_tour(self, state, now):
        self._tour = {'state': state if isinstance(state, str) else '', 'at': now}

    def update_navigation(self, status, task_id, now):
        if not isinstance(status, str) or not isinstance(task_id, str):
            return
        active = status in ('start', 'calculating', 'going', 'reposing')
        failed = status in ('aborted', 'timeout', 'failed')
        if active:
            self._navigation = {'task_id': task_id, 'active': True, 'failed': False, 'at': now}
        elif self._navigation is None or self._navigation['task_id'] == task_id:
            self._navigation = {'task_id': '', 'active': False, 'failed': failed, 'at': now}

    def update_safety_stop(self, active, now):
        self._safety_stop = {'active': active, 'valid': type(active) is bool, 'at': now}

    def snapshot(self, now):
        cfg = self.config
        ages = []
        for sample in (self._visitor, self._people):
            if sample is not None:
                ages.append(max(0.0, now - sample['at']))
        if self._scan_at is not None:
            ages.append(max(0.0, now - self._scan_at))
        age = max(ages, default=cfg.max_sample_age_sec + 1.0)
        scan_fresh = self._scan_at is not None and now >= self._scan_at and now - self._scan_at <= cfg.max_sample_age_sec
        visitor_fresh = self._visitor is not None and now >= self._visitor['at'] and now - self._visitor['at'] <= cfg.max_sample_age_sec
        people_fresh = self._people is not None and now >= self._people['at'] and now - self._people['at'] <= cfg.max_sample_age_sec
        robot_fresh = self._robot is not None and now >= self._robot['at'] and now - self._robot['at'] <= cfg.max_sample_age_sec
        tour_fresh = self._tour is not None and now >= self._tour['at'] and now - self._tour['at'] <= cfg.max_sample_age_sec
        safety_fresh = self._safety_stop is not None and now >= self._safety_stop['at'] and now - self._safety_stop['at'] <= cfg.max_sample_age_sec

        visitor_source = self._visitor['source'] if self._visitor else ''
        people_source = self._people['source'] if self._people else ''
        sources_allowed = (visitor_source in ('camera', 'temi_camera') and
                           people_source == 'temi_rgbd')
        if cfg.simulation_mode:
            sources_allowed = (visitor_source in ('camera', 'temi_camera', 'mock', 'offline_video') and
                               people_source in ('temi_rgbd', 'gazebo_rgbd', 'mock', 'offline_video'))

        visitor_valid = visitor_fresh and self._visitor['valid']
        people_distance_valid = people_fresh and self._people['distance_valid']
        density_valid = people_fresh and self._people['density_valid']
        scan_valid = scan_fresh and self.obstacle_distance_m is not None
        communication_valid = robot_fresh and self._robot['connected']
        position_valid = communication_valid and bool(self._robot['frame_id']) and self._robot['position_valid']
        safety_valid = safety_fresh and self._safety_stop['valid']
        safety_stop = not safety_valid or self._safety_stop['active']
        tour_state = self._tour['state'] if tour_fresh else ''
        navigating = tour_state in ('NAVIGATING', 'RETURNING')
        explaining = tour_state == 'EXPLAINING'
        nav = self._navigation or {'task_id': '', 'active': False, 'failed': False}
        navigation_session_id = nav['task_id'] if navigating and nav['active'] else ''
        navigation_error = bool(nav['failed']) or bool(self._robot and communication_valid and self._robot.get('error_message'))

        errors = []
        warnings = []
        if not sources_allowed:
            errors.append('感知数据来源不允许用于当前运行模式')
        if not visitor_valid:
            errors.append('稳定游客人数数据无效、过期或断流')
        elif visitor_source not in ('camera', 'temi_camera') and not cfg.simulation_mode:
            errors.append('真实摄像头人数数据不可用')
        if not people_distance_valid:
            errors.append('人员距离无效；未使用检测框估算距离')
        if not density_valid:
            warnings.append('人群密度尚未标定；速度策略将按拥挤速度保守限速')
        if not scan_valid:
            errors.append('激光雷达前向数据无效、过期或断流')
        if not communication_valid:
            errors.append('机器人通信状态无效或过期')
        if not position_valid:
            errors.append('机器人定位状态无效')
        if not tour_fresh:
            errors.append('导览状态无效或过期')
        if not safety_valid:
            errors.append('安全停车状态未确认')
        if navigating and not navigation_session_id:
            errors.append('当前导航会话 ID 未确认')
        if navigation_error:
            errors.append('导航或机器人状态报告故障')

        age = min(max(age, 0.0), 1e6) if math.isfinite(age) else 1e6
        sample_timestamp = max(0.0, now - age) if ages else 0.0
        valid = not errors
        return {
            'source': 'gazebo_sensor_fusion' if cfg.simulation_mode else 'temi_sensor_fusion',
            'data_sources': [source for source in (visitor_source, people_source,
                'gazebo_lidar' if cfg.simulation_mode else 'temi_lidar') if source],
            'sample_timestamp_monotonic_sec': sample_timestamp,
            'sample_age_sec': age, 'valid': valid, 'error': '; '.join(dict.fromkeys(errors)),
            'warning': '; '.join(dict.fromkeys(warnings)),
            'people_count': self._visitor['people_count'] if visitor_valid else None,
            'expected_count': self._visitor['expected_count'] if visitor_valid else None,
            'group_state': self._visitor['group_state'] if visitor_valid else 'unknown',
            'nearest_person_m': self._people['nearest_person_m'] if people_distance_valid else None,
            'person_distance_valid': people_distance_valid,
            'crowd_density': self._people['crowd_density'] if density_valid else None,
            'crowd_density_valid': density_valid,
            'obstacle_distance_m': self.obstacle_distance_m if scan_valid else None,
            'obstacle_distance_valid': scan_valid,
            'people_valid': visitor_valid, 'position_valid': position_valid,
            'communication_valid': communication_valid, 'safety_stop_valid': safety_valid,
            'safety_stop': safety_stop, 'navigating': navigating, 'explaining': explaining,
            'navigation_error': navigation_error,
            'navigation_session_id': navigation_session_id,
        }
