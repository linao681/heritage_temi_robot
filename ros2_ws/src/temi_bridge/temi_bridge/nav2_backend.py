"""Nav2 适配核心；实际 ROS transport 必须提供导航终态和停车确认。"""
import asyncio
import math

from .backend import NavigationFeedback, RobotSnapshot, TaskResult, TemiBackend


class Nav2Backend(TemiBackend):
    def __init__(self, transport, goals, waypoints=None):
        self.transport = transport
        self.goals = goals
        self.waypoints = waypoints or {}
        self.connected = False
        self.epoch = 0
        self.active = False
        self.stopping = False
        self.interrupted = False
        self.current_location = ''
        self.navigation_task_id = ''

    async def connect(self):
        if not self.transport.ready():
            return TaskResult(False, 'Nav2 未就绪')
        self.connected = True
        self.epoch += 1
        return TaskResult(True, '已连接仿真导航')

    async def disconnect(self):
        result = await self.stop() if self.active else TaskResult(True, '无活动导航')
        self.connected = False
        self.epoch += 1
        return result

    async def navigate_to(self, location, timeout_sec, *, task_id, feedback=None):
        if (not self.connected or not self.transport.ready() or not task_id or
                location not in self.goals or not math.isfinite(timeout_sec) or timeout_sec <= 0):
            return TaskResult(False, '导航未就绪或地点无效')
        if self.active or self.stopping:
            return TaskResult(False, '已有活动导航或正在停止')
        set_session = getattr(self.transport, 'set_navigation_session_id', None)
        if set_session is not None:
            try:
                set_session(task_id)
            except (RuntimeError, ValueError) as error:
                return TaskResult(False, f'导航会话未建立：{error}')
        self.active = True
        self.navigation_task_id = task_id
        self.interrupted = False

        def report(status, description):
            if feedback is not None:
                feedback(NavigationFeedback(task_id, location, status, description))

        try:
            report('start', '开始 Nav2 导航')

            async def follow_route():
                points = [*self.waypoints.get((self.current_location, location), []), self.goals[location]]
                for index, point in enumerate(points):
                    report('calculating', '提交 Nav2 导航目标')
                    if self.interrupted or not await self.transport.navigate(
                            point, on_active=lambda: report('going', 'Nav2 已接受导航目标')):
                        return False
                    if index + 1 < len(points):
                        report('reposing', '到达路径中间点，继续导航')
                return True
            task = asyncio.create_task(follow_route())
            done, _ = await asyncio.wait({task}, timeout=timeout_sec)
            if not done:
                self.interrupted = True
                stopped = await self.transport.stop()
                if not task.done():
                    task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                report('timeout', 'Nav2 导航超时')
                return TaskResult(False, '导航超时' if stopped else '导航超时，停车未确认')
            success = task.result() and not self.interrupted
            if success:
                self.current_location = location
                report('complete', 'Nav2 已到达目标')
            elif not self.interrupted:
                report('aborted', 'Nav2 导航失败')
            return TaskResult(success, '导航到达' if success else '导航失败或已停止')
        except asyncio.CancelledError:
            self.interrupted = True
            stopped = await self.transport.stop()
            if 'task' in locals() and not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            if not stopped:
                report('aborted', '导航取消后未能确认停车')
                raise RuntimeError('导航取消时停车未确认')
            report('cancelled', 'Nav2 导航已取消并确认停车')
            raise
        finally:
            self.active = False
            self.navigation_task_id = ''

    async def set_navigation_speed(self, target_speed_mps: float, *, command_id: str,
                                   navigation_session_id: str, control_reason: str) -> TaskResult:
        if (not math.isfinite(target_speed_mps) or not 0.3 <= target_speed_mps <= 0.8 or
                not self.active or navigation_session_id != self.navigation_task_id or
                not command_id.strip() or not control_reason.strip()):
            return TaskResult(False, 'Nav2 拒绝无效或过期的导航速度命令')
        try:
            accepted = await self.transport.set_speed(target_speed_mps)
        except Exception as error:
            return TaskResult(False, f'Nav2 限速参数更新失败: {error}')
        return TaskResult(bool(accepted), 'Nav2 目标速度上限已更新' if accepted else 'Nav2 限速参数未确认')

    async def stop(self):
        if not self.connected or self.stopping:
            return TaskResult(False, '未连接或正在停止')
        self.stopping = True
        self.interrupted = True
        try:
            success = await self.transport.stop()
            return TaskResult(success, '停车已确认' if success else '停车未确认')
        finally:
            self.stopping = False

    async def speak(self, text, *, task_id, feedback=None):
        if not self.connected or not text.strip() or not task_id:
            return TaskResult(False, '模拟播报请求无效')
        return TaskResult(True, '模拟播报完成（无真实音频）')

    def get_status(self):
        ready = self.connected and self.transport.ready()
        snapshot = self.transport.snapshot() if ready else {}
        return RobotSnapshot(connected=ready, battery_percentage=100.0 if ready else -1.0,
                             x=snapshot.get('x', 0.0), y=snapshot.get('y', 0.0),
                             yaw=snapshot.get('yaw', 0.0), is_moving=snapshot.get('moving', False),
                             current_location=self.current_location, frame_id='map' if ready else '',
                             navigation_status='moving' if self.active else 'idle', connection_epoch=self.epoch)
