import json
import os
import signal
import subprocess
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_mock_configuration_is_isolated():
    from scripts.start_mock_system import mock_config
    config = {'gateway': {'backend': 'websocket'}, 'tour': {'visitor_assist_enabled': True},
              'visitor_perception': {'count_source': 'offline_video'}}
    result = mock_config(config)
    assert result['gateway']['backend'] == 'mock'
    assert result['tour']['visitor_assist_enabled'] is False
    assert result['visitor_perception']['count_source'] == 'mock'
    assert config['gateway']['backend'] == 'websocket'
    assert config['tour']['visitor_assist_enabled'] is True


def test_terminal_round_rejects_stale_or_inconsistent_snapshot():
    from scripts.start_mock_system import valid_round
    route = ['entrance', 'exit']
    tour = {'state': 'COMPLETED', 'outcome': 'completed', 'visited': route, 'error_count': 0,
            'qa_result': {'spoken': True, 'found': True, 'source': {'url': 'https://example.com'}}}
    robot = {'connected': True, 'moving': False, 'location': 'exit', 'frame': 'mock_map'}
    visitor = {'valid': True, 'source': 'mock', 'people_count': 3, 'stable_fresh': True}
    assert valid_round(tour, robot, visitor, route)
    assert not valid_round(tour, {**robot, 'connected': False}, visitor, route)
    assert not valid_round(tour, {**robot, 'frame': 'unknown'}, visitor, route)
    assert not valid_round(tour, {**robot, 'location': 'entrance'}, visitor, route)
    assert not valid_round(tour, robot, {**visitor, 'valid': False}, route)
    assert not valid_round(tour, robot, {**visitor, 'stable_fresh': False}, route)
    assert not valid_round(tour, robot, {**visitor, 'people_count': 2}, route)


def test_one_command_mock_demo():
    result = subprocess.run(
        ['bash', str(ROOT / 'scripts/start_mock_system.sh'), '--headless', '--demo', '--domain', '218'],
        cwd=ROOT, capture_output=True, text=True, timeout=150)
    assert result.returncode == 0, result.stdout + result.stderr
    report_path = next(line.split('运行报告: ', 1)[1] for line in result.stdout.splitlines()
                       if line.startswith('运行报告: '))
    report = json.loads(Path(report_path).read_text())
    assert report['success']
    assert report['tour']['state'] == 'COMPLETED'
    assert len(report['tour']['visited']) == 8
    assert report['tour']['qa_result']['spoken']
    assert report['visitor']['valid']
    assert all(item['exit_code'] == 0 and not item['forced'] for item in report['children'])


def test_multiple_rounds_same_processes():
    result = subprocess.run(
        ['bash', str(ROOT / 'scripts/start_mock_system.sh'), '--headless', '--demo',
         '--rounds', '2', '--domain', '215'],
        cwd=ROOT, capture_output=True, text=True, timeout=150)
    assert result.returncode == 0, result.stdout + result.stderr
    path = next(line.split('运行报告: ', 1)[1] for line in result.stdout.splitlines()
                if line.startswith('运行报告: '))
    report = json.loads(Path(path).read_text())
    assert report['success'] and len(report['rounds']) == 2
    assert len(report['children']) == 5
    for index, round_result in enumerate(report['rounds'], 1):
        assert round_result['round'] == index
        assert round_result['tour']['state'] == 'COMPLETED'
        assert len(round_result['tour']['visited']) == 8
        assert round_result['tour']['error_count'] == 0
        assert round_result['tour']['qa_result']['spoken']
        assert not round_result['robot']['moving']
    assert all(item['exit_code'] == 0 and not item['forced'] for item in report['children'])


def test_rounds_requires_demo():
    result = subprocess.run(
        ['bash', str(ROOT / 'scripts/start_mock_system.sh'), '--headless', '--rounds', '2'],
        cwd=ROOT, capture_output=True, text=True, timeout=10)
    assert result.returncode == 2
    assert '--rounds 需要 --demo' in result.stderr


def test_default_idle_shutdown(tmp_path):
    output = tmp_path / 'startup.log'
    with output.open('w') as handle:
        child = subprocess.Popen(
            ['bash', str(ROOT / 'scripts/start_mock_system.sh'), '--headless', '--domain', '216'],
            cwd=ROOT, stdout=handle, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + 40
            while '待机中' not in output.read_text():
                assert child.poll() is None, output.read_text()
                assert time.monotonic() < deadline, output.read_text()
                time.sleep(0.1)
        finally:
            if child.poll() is None:
                child.send_signal(signal.SIGTERM)
            child.wait(timeout=60)
    assert child.returncode == 0, output.read_text()
    path = next(line.split('运行报告: ', 1)[1] for line in output.read_text().splitlines()
                if line.startswith('运行报告: '))
    report = json.loads(Path(path).read_text())
    assert report['success'] and report['mode'] == 'idle'
    assert report['tour']['state'] == 'IDLE'
    assert report['tour']['visited'] == []
    assert not report['visitor']['valid']
    assert not report['robot']['moving']
    assert all(item['exit_code'] == 0 and not item['forced'] for item in report['children'])


def test_gateway_exit_during_tour_and_fresh_restart(tmp_path):
    command = ['bash', str(ROOT / 'scripts/start_mock_system.sh'), '--headless', '--domain', '214']
    output = tmp_path / 'interrupted.log'
    with output.open('w') as handle:
        supervisor = subprocess.Popen(command + ['--demo'], cwd=ROOT,
                                      stdout=handle, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + 40
            while '系统就绪' not in output.read_text():
                assert supervisor.poll() is None, output.read_text()
                assert time.monotonic() < deadline, output.read_text()
                time.sleep(0.1)
            # Linux：仅选择本测试监督进程直接创建的 Mock Gateway。
            children = Path(f'/proc/{supervisor.pid}/task/{supervisor.pid}/children').read_text().split()
            gateway = None
            for pid in children:
                args = Path(f'/proc/{pid}/cmdline').read_bytes().decode().split('\0')
                if any(arg.endswith('/temi_bridge/temi_gateway') for arg in args):
                    assert args[args.index('--backend') + 1] == 'mock'
                    gateway = int(pid)
                    run_dir = Path(args[args.index('--config') + 1]).parent
                    break
            assert gateway is not None
            while 'NAVIGATING: 前往潮绣' not in (run_dir / 'tour_manager.log').read_text():
                assert supervisor.poll() is None, output.read_text()
                assert time.monotonic() < deadline
                time.sleep(0.05)
            os.kill(gateway, signal.SIGTERM)
            assert supervisor.wait(timeout=40) != 0
        finally:
            if supervisor.poll() is None:
                supervisor.send_signal(signal.SIGTERM)
                supervisor.wait(timeout=60)
    failed = json.loads((run_dir / 'report.json').read_text())
    assert not failed['success']
    assert 'temi_gateway 提前退出' in failed['error']
    assert not failed['rounds']
    assert len(failed['children']) == 5
    assert all(item['exit_code'] == 0 and not item['forced'] for item in failed['children'])

    # 重新启动由操作员明确发起；默认参数不能重放旧导览。
    restarted = tmp_path / 'restarted.log'
    with restarted.open('w') as handle:
        supervisor = subprocess.Popen(command, cwd=ROOT, stdout=handle, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + 40
            while '待机中' not in restarted.read_text():
                assert supervisor.poll() is None, restarted.read_text()
                assert time.monotonic() < deadline
                time.sleep(0.1)
            time.sleep(1)
        finally:
            if supervisor.poll() is None:
                supervisor.send_signal(signal.SIGTERM)
            supervisor.wait(timeout=60)
    assert supervisor.returncode == 0, restarted.read_text()
    path = next(line.split('运行报告: ', 1)[1] for line in restarted.read_text().splitlines()
                if line.startswith('运行报告: '))
    report = json.loads(Path(path).read_text())
    assert report['success'] and report['tour']['state'] == 'IDLE'
    assert report['tour']['visited'] == [] and not report['rounds']
    assert report['robot']['location'] == 'entrance' and not report['robot']['moving']
