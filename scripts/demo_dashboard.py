"""独立本机 Mock 导览与实际 Tk 界面，截取本程序窗口（不是桌面）。"""

from datetime import datetime
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time
import tkinter as tk

import rclpy
from std_msgs.msg import Int32
import yaml
from heritage_dashboard.main import DashboardWindow
from heritage_dashboard.ros_dashboard import DashboardNode

ROOT = Path(__file__).resolve().parents[1]


def main():
    run_dir = ROOT/'docs/runs'/datetime.now().strftime('dashboard-%Y%m%d-%H%M%S-%f')
    run_dir.mkdir(parents=True)
    os.environ.update(ROS_LOCALHOST_ONLY='1', ROS_DOMAIN_ID='226', ROS_LOG_DIR=str(run_dir/'ros-logs'))
    handles, processes = [], []
    snapshots, failures = {}, []
    root = dashboard = publisher_node = None

    def launch(args, name):
        handle = (run_dir/name).open('w', encoding='utf-8'); handles.append(handle)
        child = subprocess.Popen([str(arg) for arg in args], cwd=ROOT, stdout=handle, stderr=subprocess.STDOUT)
        processes.append(child); return child

    def capture(name, snapshot):
        root.update_idletasks()
        with tempfile.TemporaryDirectory(prefix='heritage-dashboard-') as directory:
            dump = Path(directory)/'window.xwd'
            subprocess.run(['xwd','-silent','-id',str(root.winfo_id()),'-out',str(dump)],check=True, timeout=5)
            subprocess.run(['ffmpeg','-loglevel','error','-i',str(dump),'-frames:v','1',str(run_dir/f'{name}.png')],check=True,timeout=10)
        snapshots[name] = snapshot

    try:
        config = yaml.safe_load((ROOT/'config/system.yaml').read_text())
        exhibits = yaml.safe_load((ROOT/'config/exhibits.yaml').read_text())['exhibits']
        visitor = launch([ROOT/'ros2_ws/install/visitor_perception/lib/visitor_perception/visitor_perception',
                          '--config',ROOT/'config/system.yaml'],'visitor.log')
        demo = launch(['python3',ROOT/'scripts/demo_mock_tour.py','--question','潮剧用什么语言'],'mock_tour.log')
        rclpy.init(args=[])
        dashboard = DashboardNode(controls=True)
        publisher_node = rclpy.create_node('dashboard_demo_mock_visitor')
        publisher = publisher_node.create_publisher(Int32,'heritage/visitor/count',10)
        root = tk.Tk(); DashboardWindow(root,dashboard,exhibits,config['mock']['locations'])
        # 仅演示窗口前置并定位在屏幕内；避免 XWD 截图被其他窗口遮挡。
        root.geometry('1120x760+80+80')
        root.attributes('-topmost', True)
        root.lift()
        deadline = time.monotonic()+90

        def tick():
            try:
                publisher.publish(Int32(data=3))
                state = dashboard.model.snapshot(time.monotonic())
                tour, robot, visitor_state = state['tour'], state['robot'], state['visitor']
                if tour and robot and visitor_state and visitor_state['valid']:
                    if 'navigation' not in snapshots and tour['state']=='NAVIGATING' and len(tour['visited'])>=2:
                        capture('navigation',state)
                    if 'qa' not in snapshots and (tour.get('qa_result') or {}).get('spoken'):
                        capture('qa',state)
                if demo.poll() is not None:
                    if demo.returncode!=0: failures.append('Mock 导览失败')
                    root.destroy(); return
                if time.monotonic()>=deadline or visitor.poll() is not None:
                    failures.append('演示超时或感知节点退出'); root.destroy(); return
                root.after(100,tick)
            except Exception as error:
                failures.append(str(error)); root.destroy()

        root.after(100,tick); root.mainloop()
        success = not failures and demo.poll()==0 and {'navigation','qa'}<=snapshots.keys()
        report = {'success':success,'snapshots':snapshots,'errors':failures,'demo_exit':demo.poll(),
                  'note':'只启动本机 Mock 测试；未连接或控制实体机器人。'}
        (run_dir/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(f'监控台演示 {"通过" if success else "失败"}：{run_dir}',flush=True)
        return 0 if success else 1
    finally:
        if publisher_node is not None: publisher_node.destroy_node()
        if dashboard is not None: dashboard.destroy_node()
        if rclpy.ok(): rclpy.try_shutdown()
        for child in reversed(processes):
            if child.poll() is None:
                child.send_signal(signal.SIGINT)
                try: child.wait(timeout=12)
                except subprocess.TimeoutExpired: child.kill(); child.wait(timeout=3)
        for handle in handles: handle.close()


if __name__=='__main__':
    raise SystemExit(main())
