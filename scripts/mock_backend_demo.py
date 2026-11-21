"""独立运行一次虚拟导航和播报，用于观察实时位置与反馈。"""

import asyncio
from pathlib import Path

from temi_bridge.mock_backend import MockConfig, MockTemiBackend


async def main() -> int:
    """使用项目默认 Mock 配置；不连接 ROS2、Android 或实体 temi。"""
    config = MockConfig.from_yaml(Path(__file__).resolve().parents[1] / 'config/system.yaml')
    backend = MockTemiBackend(config)
    await backend.connect()
    clock = asyncio.get_running_loop().time
    started = clock()

    def log_navigation(event):
        print(f'{clock() - started:.2f}s navigation={event.status} id={event.task_id}', flush=True)

    def log_position():
        status = backend.get_status()
        print(f'{clock() - started:.2f}s x={status.x:.3f} y={status.y:.3f} '
              f'yaw={status.yaw:.3f} battery={status.battery_percentage:.2f}% '
              f'moving={status.is_moving}', flush=True)

    try:
        log_position()
        navigation = asyncio.create_task(backend.navigate_to(
            'exhibit_01', 15.0, task_id='demo_nav', feedback=log_navigation,
        ))
        while not navigation.done():
            await asyncio.sleep(0.25)
            log_position()
        result = await navigation
        print(f'导航结果：{result.success} / {result.message}')
        if not result.success:
            return 1
        speech = await backend.speak(
            '欢迎来到潮汕非遗文化展厅', task_id='demo_speech',
            feedback=lambda event: print(f'speech={event.status} id={event.task_id}', flush=True),
        )
        print(f'语音结果：{speech.success} / {speech.message}')
        return 0 if speech.success else 1
    finally:
        await backend.disconnect()


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
