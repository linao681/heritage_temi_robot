"""Explicit local demonstration: simulate consent and end QA at the fifth zone."""
import json
import os
from pathlib import Path
import signal
import time

import rclpy
from std_msgs.msg import String
from std_srvs.srv import Trigger
from temi_interfaces.srv import SubmitQuestion

ROOT = Path(__file__).resolve().parents[1]


def main():
    if os.environ.get('ROS_LOCALHOST_ONLY') != '1' or os.environ.get('ROS_DOMAIN_ID') != '211':
        raise RuntimeError('仅限本机模拟域 211')
    from rclpy.signals import SignalHandlerOptions
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    node = rclpy.create_node('submission_tour_check')
    latest = {}
    def receive(msg):
        latest.clear()
        latest.update(json.loads(msg.data))
    node.create_subscription(String, 'heritage/tour/status', receive, 50)
    clients = {name: node.create_client(Trigger, 'heritage/tour/'+name)
               for name in ('start', 'accept', 'finish_qa', 'cancel')}
    question = node.create_client(SubmitQuestion, 'heritage/tour/ask')
    report = {'success': False, 'simulated_consent': True, 'speech': '模拟事件，无真实音频'}
    def wait(predicate, timeout):
        end = time.monotonic()+timeout
        while not predicate():
            if time.monotonic() > end:
                raise TimeoutError('等待导览状态超时')
            rclpy.spin_once(node, timeout_sec=0.05)
    def call(name):
        future = clients[name].call_async(Trigger.Request())
        wait(future.done, 8)
        if not future.result().success:
            raise RuntimeError(future.result().message)
    try:
        wait(lambda: all(c.service_is_ready() for c in clients.values()) and
             question.service_is_ready() and latest.get('connected'), 30)
        call('start')
        wait(lambda: latest.get('state') == 'WAITING_CONSENT', 30)
        call('accept')
        wait(lambda: latest.get('qa_waiting') or latest.get('state') == 'ERROR', 1500)
        if not latest.get('qa_waiting'):
            raise RuntimeError('互动区前导览异常')
        future = question.call_async(SubmitQuestion.Request(question='潮剧用什么语言', level='basic'))
        wait(future.done, 8)
        if not future.result().accepted:
            raise RuntimeError(future.result().message)
        wait(lambda: latest.get('state') in ('COMPLETED', 'ERROR'), 400)
        report['tour'] = dict(latest)
        report['success'] = bool(latest.get('state') == 'COMPLETED' and latest.get('outcome') == 'completed' and
                             latest.get('visited') == ['wait', 'zone_1', 'zone_2', 'zone_3', 'zone_4', 'zone_5', 'exit'] and
                             latest.get('error_count') == 0 and not latest.get('is_moving') and
                             (latest.get('qa_result') or {}).get('found') and
                             (latest.get('qa_result') or {}).get('spoken') and
                             (latest.get('qa_result') or {}).get('source', {}).get('url'))
    except (Exception, KeyboardInterrupt) as error:
        report['error'] = str(error) or '验收中断'
        report['tour'] = dict(latest)
        if clients['cancel'].service_is_ready():
            try:
                call('cancel')
            except Exception:
                pass
    finally:
        path = ROOT/'docs/acceptance/gazebo/submission_tour.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
        print(json.dumps(report, ensure_ascii=False), flush=True)
        node.destroy_node()
        rclpy.shutdown()
    return 0 if report['success'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
