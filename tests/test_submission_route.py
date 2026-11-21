from pathlib import Path
import asyncio
import json

from heritage_tour_manager.tour_config import TourConfig

ROOT = Path(__file__).resolve().parents[1]


def test_submitted_five_zone_route_has_single_interaction_stop():
    config = TourConfig.from_yaml(ROOT / 'config/submission_exhibits.yaml', ROOT / 'config/submission_system.yaml')
    assert [item.temi_location for item in config.route] == [
        'wait', 'zone_1', 'zone_2', 'zone_3', 'zone_4', 'zone_5', 'exit']
    assert [item.name for item in config.route[1:-1]] == [
        '非遗概览', '传统工艺', '代表作品', '传承故事', '互动体验']
    assert config.route[-2].id == 'interaction_zone'
    assert config.safe_return_location == 'wait'
    for layout in ('official', 'adaptive'):
        goals = json.loads((ROOT / 'simulation/generated' / f'{layout}_goals.json').read_text())['goals']
        assert all(item.temi_location in goals for item in config.route)


def test_five_zone_manager_waits_for_consent_and_qa_before_exit():
    from heritage_tour_manager.tour_manager import TourManager, OperationResult

    class Robot:
        def __init__(self):
            self.visited = []
        async def navigate(self, location, timeout_sec):
            self.visited.append(location)
            return OperationResult(True, 'arrived')
        async def speak(self, text):
            return OperationResult(True, 'simulated')
        async def stop(self):
            return OperationResult(True, 'stopped')

    async def scenario():
        config = TourConfig.from_yaml(ROOT / 'config/submission_exhibits.yaml', ROOT / 'config/submission_system.yaml')
        robot = Robot()
        manager = TourManager(robot, config)
        manager.update_robot_status(connected=True, battery_percentage=100, current_location='wait', is_moving=False)
        assert manager.start()
        async def until(predicate):
            for _ in range(1000):
                if predicate():
                    return
                await asyncio.sleep(0.001)
            raise AssertionError(manager.status())
        await until(lambda: manager.status()['state'] == 'WAITING_CONSENT')
        assert robot.visited == []
        assert manager.consent(True)
        await until(lambda: manager.status()['qa_waiting'])
        assert robot.visited == ['wait', 'zone_1', 'zone_2', 'zone_3', 'zone_4', 'zone_5']
        assert manager.finish_qa()
        await until(lambda: manager.status()['state'] == 'COMPLETED')
        assert robot.visited[-1] == 'exit'
        await manager.shutdown()
    asyncio.run(scenario())
