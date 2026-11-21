"""可单测的解释型导览速度策略；本模块不直接控制电机。"""
from dataclasses import dataclass
import math
import uuid


@dataclass(frozen=True)
class SpeedConfig:
    min_navigation_speed: float = 0.3
    max_navigation_speed: float = 0.8
    default_speed: float = 0.5
    crowded_speed: float = 0.3
    open_area_speed: float = 0.7
    crowded_density: float = 0.5
    slow_person_distance_m: float = 2.0
    stop_person_distance_m: float = 0.65
    slow_obstacle_distance_m: float = 1.5
    stop_obstacle_distance_m: float = 0.55
    clear_distance_hysteresis_m: float = 0.25
    lost_group_stop_sec: float = 8.0
    recovery_hold_sec: float = 2.0
    input_timeout_sec: float = 1.0
    acceleration_limit_mps2: float = 0.2
    deceleration_limit_mps2: float = 0.5
    min_speed_delta_mps: float = 0.05
    command_interval_sec: float = 0.5

    def __post_init__(self):
        values = vars(self)
        if any(type(v) not in (int, float) or not math.isfinite(v) for v in values.values()):
            raise ValueError('速度策略参数必须为有限数值')
        if not (0.3 <= self.min_navigation_speed <= self.default_speed <= self.max_navigation_speed <= 0.8):
            raise ValueError('导航速度须处于 0.3~0.8 m/s 且最小值≤默认值≤最大值')
        if not self.min_navigation_speed <= self.crowded_speed <= self.max_navigation_speed:
            raise ValueError('crowded_speed 超出限速')
        for name in ('slow_person_distance_m', 'stop_person_distance_m',
                     'slow_obstacle_distance_m', 'stop_obstacle_distance_m',
                     'lost_group_stop_sec', 'recovery_hold_sec', 'input_timeout_sec',
                     'acceleration_limit_mps2', 'deceleration_limit_mps2', 'command_interval_sec'):
            if getattr(self, name) <= 0:
                raise ValueError(f'{name} 必须为正数')
        if self.stop_person_distance_m >= self.slow_person_distance_m or self.stop_obstacle_distance_m >= self.slow_obstacle_distance_m:
            raise ValueError('停止距离必须小于减速距离')
        if self.clear_distance_hysteresis_m < 0 or self.min_speed_delta_mps < 0 or not 0 <= self.crowded_density <= 1:
            raise ValueError('滞回、最小变化量或人群阈值无效')


@dataclass(frozen=True)
class SpeedInputs:
    now: float
    nearest_person_m: float | None
    crowd_density: float | None
    obstacle_distance_m: float | None
    group_state: str
    navigating: bool
    explaining: bool
    navigation_error: bool
    safety_stop: bool
    position_valid: bool
    communication_valid: bool
    stop_confirmed: bool
    navigation_session_id: str = ''
    manual_stop: bool = False
    sample_age_sec: float = 0.0


@dataclass(frozen=True)
class SpeedDecision:
    state: str
    target_speed_mps: float | None
    send_speed: bool
    stop_requested: bool
    reason: str
    navigation_session_id: str
    command_id: str = ''
    resume_requested: bool = False


class SpeedController:
    """单调时间控制；目标速度、停车请求和机器人实测速度保持分离。"""
    def __init__(self, config: SpeedConfig | None = None):
        self.config = config or SpeedConfig()
        self.state = 'IDLE'
        self.reason = '待命'
        self._error_latched = False
        self._manual_latched = False
        self._lost_since = None
        self._clear_since = None
        self._last_speed = None
        self._last_command_at = -math.inf
        self._last_session = ''
        self._stop_sent = False
        self._last_update = None
        self._resume_sent = False

    def report_stop_result(self, success: bool):
        """停车接口失败时锁存错误，不能把尚未确认的停车当作完成。"""
        if not success:
            self._error_latched = True
            self._stop_sent = True
            self.state, self.reason = 'ERROR', '停车请求未成功确认'

    def report_speed_result(self, success: bool):
        if not success:
            self._error_latched = True
            self.state, self.reason = 'ERROR', '调速命令执行失败或 SDK 拒绝'

    def reset_error(self):
        """仅由显式人工复位调用，ERROR 不自行恢复。"""
        self._error_latched = False
        self._manual_latched = False
        self._stop_sent = False
        self._last_speed = None
        self._last_command_at = -math.inf
        self._last_session = ''
        self.state = 'IDLE'
        self.reason = '人工复位'

    def update(self, inputs: SpeedInputs, now: float) -> SpeedDecision:
        cfg = self.config
        dt = 0.0 if self._last_update is None else max(0.0, now - self._last_update)
        self._last_update = now
        new_session = bool(inputs.navigation_session_id and inputs.navigation_session_id != self._last_session)
        if new_session:
            self._last_session = inputs.navigation_session_id
            self._last_speed = None
            self._last_command_at = -math.inf
            self._stop_sent = False
            self._resume_sent = False
            recovering = self.state == 'RECOVERING'
            if recovering:
                self._last_speed = self.config.crowded_speed
            else:
                self.state = 'NORMAL'
            self._lost_since = None
            self._clear_since = None
            if not self._error_latched and not recovering:
                self.state = 'NORMAL'

        if inputs.manual_stop:
            self._manual_latched = True
        if (not inputs.navigating and self.state not in ('STOPPED', 'WAITING', 'STOPPING', 'RECOVERING', 'ERROR') and
                not inputs.explaining and not inputs.safety_stop and not self._manual_latched):
            self.state, self.reason = 'IDLE', '当前无导航任务'
            return self._decision(None, False, False, inputs, now)
        if inputs.navigating and not inputs.navigation_session_id.strip():
            self._error_latched = True
            self.state, self.reason = 'ERROR', '活动导航会话 ID 缺失'
        if self._error_latched and self.reason == '活动导航会话 ID 缺失':
            stop = not inputs.stop_confirmed and not self._stop_sent
            if stop: self._stop_sent = True
            return self._decision(None, False, stop, inputs, now)
        if self._manual_latched or not inputs.communication_valid or not inputs.position_valid or inputs.navigation_error:
            self._error_latched = True
            self.state, self.reason = 'ERROR', ('人工停止' if self._manual_latched else
                '通信异常' if not inputs.communication_valid else '定位异常' if not inputs.position_valid else '导航异常')
            stop = not inputs.stop_confirmed and not self._stop_sent
            if stop: self._stop_sent = True
            return self._decision(None, False, stop, inputs, now)
        if self._error_latched:
            self.state, self.reason = 'ERROR', '故障锁存，等待人工复位'
            stop = not inputs.stop_confirmed and not self._stop_sent
            if stop: self._stop_sent = True
            return self._decision(None, False, stop, inputs, now)

        sensor_values = (inputs.nearest_person_m, inputs.crowd_density, inputs.obstacle_distance_m)
        sensors_valid = (type(inputs.sample_age_sec) in (int, float) and math.isfinite(inputs.sample_age_sec) and
                         inputs.sample_age_sec >= 0 and inputs.sample_age_sec + max(0.0, now - inputs.now) <= cfg.input_timeout_sec and now >= inputs.now and
                         all(v is not None and type(v) in (int, float) and math.isfinite(v) and v >= 0 for v in sensor_values) and
                         inputs.crowd_density <= 1.0)
        if not sensors_valid:
            self.state, self.reason = 'STOPPING', '感知数据无效或过期'
            stop = not self._stop_sent and not inputs.stop_confirmed
            if stop: self._stop_sent = True
            if inputs.stop_confirmed: self.state = 'STOPPED'
            return self._decision(None, False, stop, inputs, now)

        if inputs.stop_confirmed and self.state == 'STOPPING':
            self.state, self.reason = 'STOPPED', '已收到导航停车确认'
            self._stop_sent = True
            return self._decision(None, False, False, inputs, now)
        if self.state == 'STOPPED':
            self.state, self.reason = 'WAITING', '停车已确认，等待恢复条件'
        if not inputs.navigating:
            if self.state == 'RECOVERING':
                return self._decision(None, False, False, inputs, now)
            if self.state == 'STOPPING' and not inputs.stop_confirmed:
                return self._decision(None, False, False, inputs, now)
            if self.state != 'WAITING':
                self.state, self.reason = 'IDLE', '当前无导航任务'
                return self._decision(None, False, False, inputs, now)

        hard_stop = (inputs.safety_stop or inputs.explaining or
                     inputs.nearest_person_m <= cfg.stop_person_distance_m or
                     inputs.obstacle_distance_m <= cfg.stop_obstacle_distance_m)
        if inputs.group_state == 'lost':
            self._lost_since = now if self._lost_since is None else self._lost_since
        else:
            self._lost_since = None
        group_wait = self._lost_since is not None and now - self._lost_since >= cfg.lost_group_stop_sec
        if hard_stop or group_wait:
            self.state, self.reason = ('STOPPED' if inputs.stop_confirmed else 'STOPPING'), ('安全停车条件' if inputs.safety_stop else
                '讲解期间停车' if inputs.explaining else '近距离危险停车' if hard_stop else '游客掉队等待')
            stop = not self._stop_sent and not inputs.stop_confirmed
            if stop: self._stop_sent = True
            if inputs.stop_confirmed:
                self.state = 'STOPPED'
                self._clear_since = None
            return self._decision(None, False, stop, inputs, now)

        if self.state in ('STOPPED', 'WAITING', 'STOPPING'):
            clear = (inputs.nearest_person_m > cfg.stop_person_distance_m + cfg.clear_distance_hysteresis_m and
                     inputs.obstacle_distance_m > cfg.stop_obstacle_distance_m + cfg.clear_distance_hysteresis_m and
                     inputs.group_state != 'lost' and not inputs.safety_stop and not inputs.explaining)
            if not clear:
                self._clear_since = None
                self.state, self.reason = 'WAITING', '等待安全条件持续恢复'
                return self._decision(None, False, False, inputs, now)
            self._clear_since = now if self._clear_since is None else self._clear_since
            if now - self._clear_since < cfg.recovery_hold_sec:
                self.state, self.reason = 'WAITING', '安全条件恢复确认中'
                return self._decision(None, False, False, inputs, now)
            self.state, self.reason = 'RECOVERING', '安全条件恢复；请求导览状态机重新导航'
            self._stop_sent = False
            self._resume_sent = True
            return self._decision(None, False, False, inputs, now, resume=True)

        if inputs.group_state not in ('following', 'untracked'):
            base, reason = cfg.crowded_speed, '团队状态未知，保守降速'
        elif inputs.crowd_density >= cfg.crowded_density:
            base, reason = cfg.crowded_speed, '人群密度较高'
        elif inputs.nearest_person_m <= cfg.slow_person_distance_m:
            ratio = ((inputs.nearest_person_m - cfg.stop_person_distance_m) /
                     (cfg.slow_person_distance_m - cfg.stop_person_distance_m))
            base = cfg.crowded_speed + max(0.0, min(1.0, ratio)) * (cfg.default_speed - cfg.crowded_speed)
            reason = '接近游客，按距离减速'
        elif inputs.obstacle_distance_m <= cfg.slow_obstacle_distance_m:
            ratio = ((inputs.obstacle_distance_m - cfg.stop_obstacle_distance_m) /
                     (cfg.slow_obstacle_distance_m - cfg.stop_obstacle_distance_m))
            base = cfg.crowded_speed + max(0.0, min(1.0, ratio)) * (cfg.default_speed - cfg.crowded_speed)
            reason = '前方障碍，按距离减速'
        elif inputs.crowd_density <= 0.2 and inputs.nearest_person_m > cfg.slow_person_distance_m * 1.5:
            base, reason = cfg.open_area_speed, '空旷区域'
        else:
            base, reason = cfg.default_speed, '正常导览'
        if self.state == 'RECOVERING':
            base = min(base, cfg.crowded_speed)
            reason = '恢复导览，低速重新起步'
        target = max(cfg.min_navigation_speed, min(cfg.max_navigation_speed, base))
        if self._last_speed is not None and dt > 0:
            limit = cfg.acceleration_limit_mps2 if target > self._last_speed else cfg.deceleration_limit_mps2
            delta = limit * dt
            target = min(self._last_speed + delta, max(self._last_speed - delta, target))
        self.state = 'SLOW' if reason not in ('正常导览', '空旷区域') else 'NORMAL'
        if reason.startswith('恢复导览'):
            self.state = 'RECOVERING'
        self.reason = reason
        return self._decision(target, True, False, inputs, now)

    def _decision(self, target, eligible, stop, inputs, now, resume=False):
        changed_session = inputs.navigation_session_id != self._last_session
        delta = math.inf if self._last_speed is None or changed_session else abs(target - self._last_speed) if target is not None and self._last_speed is not None else 0
        send = bool(eligible and target is not None and inputs.navigation_session_id and
                    (self._last_speed is None or changed_session or delta >= self.config.min_speed_delta_mps) and
                    now - self._last_command_at >= self.config.command_interval_sec)
        command_id = uuid.uuid4().hex if send else ''
        if send:
            self._last_speed, self._last_command_at = target, now
        return SpeedDecision(self.state, target, send, stop, self.reason,
                             inputs.navigation_session_id, command_id, resume)
