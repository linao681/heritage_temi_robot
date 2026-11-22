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
        self._seen_task_ids = set()
        self._stop_task = None
        self._speed_lock = asyncio.Lock()
        self._speed_transactions = set()
        self._stop_generation = 0

    async def connect(self):
        loop = asyncio.get_running_loop()
        deadline = loop.time() + 5.0
        while not self.transport.ready():
            if loop.time() >= deadline:
                return TaskResult(False, 'Nav2 未就绪')
            await asyncio.sleep(0.1)
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
        loop = asyncio.get_running_loop()
        started = loop.time()
        epoch = self.epoch
        stop_generation = self._stop_generation
        try:
            await asyncio.wait_for(self._speed_lock.acquire(), timeout_sec)
        except asyncio.TimeoutError:
            return TaskResult(False, '上一调速事务尚未结算')
        try:
            timeout_sec -= loop.time() - started
            if (timeout_sec <= 0 or not self.connected or epoch != self.epoch or
                    stop_generation != self._stop_generation or
                    not self.transport.ready() or self.active or self.stopping):
                return TaskResult(False, '导航未就绪、已有活动导航或正在停止')
            if task_id in self._seen_task_ids:
                return TaskResult(False, '拒绝重放已处理的导航任务')
            set_session = getattr(self.transport, 'set_navigation_session_id', None)
            if set_session is not None:
                try:
                    set_session(task_id)
                except (RuntimeError, ValueError) as error:
                    return TaskResult(False, f'导航会话未建立：{error}')
            self.active = True
            self._seen_task_ids.add(task_id)
            self.navigation_task_id = task_id
            self.interrupted = False
        finally:
            self._speed_lock.release()

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
                stopped = (await self.stop()).success
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
            stopped = (await self.stop()).success
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
                not command_id.strip() or not control_reason.strip()):
            return TaskResult(False, 'Nav2 拒绝无效或过期的导航速度命令')
        # ROS parameter calls cannot be recalled just because the local waiter
        # was canceled. The transaction owns the lock until writes and rollback
        # settle, then checks the same navigation session again.
        transaction = asyncio.create_task(self._set_speed_transaction(
            target_speed_mps, navigation_session_id))
        self._speed_transactions.add(transaction)
        transaction.add_done_callback(self._speed_transactions.discard)
        return await asyncio.shield(transaction)

    async def _set_speed_transaction(self, target_speed_mps, navigation_session_id):
        async with self._speed_lock:
            epoch = self.epoch
            def current():
                return (self.connected and self.epoch == epoch and self.active and
                        not self.stopping and not self.interrupted and
                        navigation_session_id == self.navigation_task_id)

            if not current():
                return TaskResult(False, 'Nav2 拒绝无效或过期的导航速度命令')
            try:
                accepted = await self.transport.set_speed(target_speed_mps)
            except Exception as error:
                return TaskResult(False, f'Nav2 限速参数更新失败: {error}')
            accepted = bool(accepted) and current()
            return TaskResult(accepted, 'Nav2 目标速度上限已更新' if accepted else 'Nav2 限速参数未确认或会话已失效')

    async def stop(self):
        if not self.connected:
            return TaskResult(False, '未连接')
        if self._stop_task is None:
            self._stop_generation += 1
            self.stopping = True
            self.interrupted = True
            self._stop_task = asyncio.create_task(self._confirm_stop())
        return await asyncio.shield(self._stop_task)

    async def _confirm_stop(self):
        try:
            success = await self.transport.stop()
            return TaskResult(success, '停车已确认' if success else '停车未确认')
        finally:
            self.stopping = False
            self._stop_task = None

    async def speak(self, text, *, task_id, feedback=None):
        if not self.connected or not text.strip() or not task_id:
            return TaskResult(False, '模拟播报请求无效')
        return TaskResult(True, '模拟播报完成（无真实音频）')

    def get_status(self):
        ready = self.connected and self.transport.ready()
        snapshot = self.transport.snapshot() if ready else None
        ready = ready and snapshot is not None
        snapshot = snapshot or {}
        return RobotSnapshot(connected=ready, battery_percentage=100.0 if ready else -1.0,
                             x=snapshot.get('x', 0.0), y=snapshot.get('y', 0.0),
                             yaw=snapshot.get('yaw', 0.0), is_moving=snapshot.get('moving', False),
                             current_location=self.current_location, frame_id='map' if ready else '',
                             navigation_status='moving' if self.active else 'idle', connection_epoch=self.epoch)
