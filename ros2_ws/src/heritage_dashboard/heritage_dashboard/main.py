"""本机 Tk 监控界面，不创建网络控制端口。"""

import argparse
import os
from pathlib import Path
import signal
import time
import tkinter as tk
from tkinter import ttk

import rclpy
from rclpy.signals import SignalHandlerOptions
import yaml

from .ros_dashboard import DashboardNode


class DashboardWindow:
    def __init__(self, root, node, exhibits, locations):
        self.root, self.node, self.locations = root, node, locations
        self.exhibits = exhibits
        root.title('潮汕非遗 · 导览监控台')
        root.geometry('1120x760')
        root.minsize(900, 650)
        root.configure(bg='#eef2f2')
        style = ttk.Style(root)
        style.theme_use('clam')
        style.configure('TFrame', background='#eef2f2')
        style.configure('TLabel', background='#eef2f2', foreground='#193b3a', font=('Sans', 11))
        style.configure('Title.TLabel', font=('Sans', 22, 'bold'))
        style.configure('Section.TLabel', font=('Sans', 13, 'bold'))
        shell = ttk.Frame(root, padding=18); shell.pack(fill='both', expand=True)
        ttk.Label(shell, text='潮汕非遗 | 智能导览监控台', style='Title.TLabel').pack(anchor='w')
        ttk.Label(shell, text='本机 ROS2 · MOCK 虚拟地图 · 真实设备未验收').pack(anchor='w', pady=(2,12))
        self.metrics = ttk.Label(shell, text='', font=('Sans', 13, 'bold')); self.metrics.pack(anchor='w', pady=(0,12))
        body = ttk.Frame(shell); body.pack(fill='both', expand=True)
        left = ttk.Frame(body); left.pack(side='left', fill='both', expand=True, padx=(0,12))
        right = ttk.Frame(body); right.pack(side='right', fill='both', expand=True)
        ttk.Label(left, text='虚拟展厅路线', style='Section.TLabel').pack(anchor='w')
        self.canvas = tk.Canvas(left, width=470, height=370, bg='#ffffff', highlightthickness=1, highlightbackground='#d0deda')
        self.canvas.pack(fill='both', expand=True, pady=8)
        self.progress = ttk.Label(left, text=''); self.progress.pack(anchor='w')
        ttk.Label(right, text='任务状态与问答', style='Section.TLabel').pack(anchor='w')
        self.detail = tk.Text(right, width=44, height=16, wrap='word', font=('Sans',11), bg='#ffffff', fg='#193b3a', relief='flat', padx=10, pady=10)
        self.detail.pack(fill='both', expand=True, pady=8); self.detail.configure(state='disabled')
        ttk.Label(shell, text='人工控制（仅显式开启的 Mock 环境）', style='Section.TLabel').pack(anchor='w', pady=(8,4))
        bar = ttk.Frame(shell); bar.pack(fill='x')
        self.buttons = {}
        for name, label in [('pause','暂停'),('resume','继续'),('cancel','取消导览'),('manual_takeover','人工接管')]:
            button = ttk.Button(bar, text=label, command=lambda name=name: self.node.request(name))
            button.pack(side='left', padx=(0,8)); self.buttons[name] = button
        self.result = ttk.Label(shell, text=''); self.result.pack(anchor='w', pady=(6,0))
        self.refresh()

    def draw(self, robot, tour):
        c = self.canvas; c.delete('all')
        width, height = max(c.winfo_width(), 380), max(c.winfo_height(), 300)
        points = list(self.locations.values())
        if not points:
            return
        xs, ys = zip(*points)
        scale = min((width-100)/max(max(xs)-min(xs), 1), (height-85)/max(max(ys)-min(ys),1))
        def project(x,y): return (50+(x-min(xs))*scale, height-45-(y-min(ys))*scale)
        order = [item['temi_location'] for item in self.exhibits if item['temi_location'] in self.locations]
        visited = (tour or {}).get('visited', [])
        for a,b in zip(order, order[1:]):
            c.create_line(*project(*self.locations[a]), *project(*self.locations[b]), fill='#9fb8b0', width=3, arrow='last')
        for index, item in enumerate(self.exhibits):
            loc = item['temi_location']
            if loc not in self.locations: continue
            x,y = project(*self.locations[loc]); fill = '#2c786b' if loc in visited else '#cbd9d4'
            c.create_oval(x-13,y-13,x+13,y+13,fill=fill,outline='')
            c.create_text(x,y,text=str(index+1),fill='white' if loc in visited else '#193b3a',font=('Sans',10,'bold'))
            c.create_text(x,y-24,text=item['name'],fill='#193b3a',font=('Sans',10))
        if robot and robot['connected'] and robot['frame_id']=='mock_map':
            x,y=project(robot['x'],robot['y']); c.create_oval(x-9,y-9,x+9,y+9,fill='#e9a23b',outline='#734710',width=2)

    def refresh(self):
        for _ in range(6): rclpy.spin_once(self.node, timeout_sec=0)
        self.node.poll_control()
        now = time.monotonic(); data = self.node.model.snapshot(now); robot,tour,visitor=data['robot'],data['tour'],data['visitor']
        battery = robot['battery_percentage'] if robot else -1
        connection = '未知/过期' if not robot else '已连接' if robot['connected'] else '断开'
        count = str(visitor['people_count']) if visitor and visitor['valid'] and visitor.get('stable_fresh') else '未知'
        self.metrics.configure(text=f'连接：{connection}    |    电量：{battery:.1f}%' if 0<=battery<=100 else f'连接：{connection}    |    电量：未知')
        self.metrics.configure(text=self.metrics.cget('text')+f'    |    匿名人数：{count}    |    状态：{(tour or {}).get("state","未知") }')
        self.draw(robot,tour)
        self.progress.configure(text=f'已访问 {(len(tour["visited"]) if tour else 0)}/8 站（状态失效时不显示进度）' if tour else '导览进度：未知')
        lines = [f'运行结果：{(tour or {}).get("outcome","未知")}', f'目标：{(tour or {}).get("target","未知")}',
                 f'原因：{(tour or {}).get("reason","未知")}', f'耗时：{(tour or {}).get("elapsed_sec","未知")} 秒',
                 f'异常数：{(tour or {}).get("error_count","未知")}', f'机器人告警：{(robot or {}).get("error_message") or ("无" if robot else "未知")}',
                 f'游客来源：{(visitor or {}).get("source","未知")}', '']
        nav = data['navigation'] or {}
        lines.extend([f'近期导航事件：{nav.get("status", "未知/过期")} {nav.get("description", "")}', ''])
        qa = (tour or {}).get('qa_result') or {}
        lines.extend(['问答：'+str(qa.get('answer','暂无')), '来源：'+str((qa.get('source') or {}).get('url','—')), '', '最近状态：'])
        for entry in (tour or {}).get('history', [])[-6:]:
            if isinstance(entry,dict): lines.append(f'{entry.get("elapsed_sec", "")}s  {entry.get("state", "")}  {entry.get("reason", "")}')
        self.detail.configure(state='normal'); self.detail.delete('1.0','end'); self.detail.insert('1.0','\n'.join(lines)); self.detail.configure(state='disabled')
        allowed = self.node.model.commands(now) if self.node.pending is None else set()
        for name, button in self.buttons.items(): button.configure(state='normal' if name in allowed else 'disabled')
        self.result.configure(text=self.node.control_message)
        self.root.after(120, self.refresh)


def main():
    parser = argparse.ArgumentParser(description='本机导览监控台')
    parser.add_argument('--config',default='config/system.yaml')
    parser.add_argument('--exhibits',default='config/exhibits.yaml')
    parser.add_argument('--enable-mock-controls',action='store_true')
    args, ros_args = parser.parse_known_args()
    domain=os.environ.get('ROS_DOMAIN_ID','')
    if args.enable_mock_controls and (os.environ.get('ROS_LOCALHOST_ONLY')!='1' or not domain.isdecimal() or not 0<=int(domain)<=232):
        parser.error('Mock 控制要求显式本机 ROS_DOMAIN_ID 与 ROS_LOCALHOST_ONLY=1')
    os.environ['ROS_LOCALHOST_ONLY'] = '1'
    config = yaml.safe_load(Path(args.config).read_text(encoding='utf-8'))
    exhibits = yaml.safe_load(Path(args.exhibits).read_text(encoding='utf-8'))['exhibits']
    root = tk.Tk()
    rclpy.init(args=ros_args, signal_handler_options=SignalHandlerOptions.NO)
    node = DashboardNode(controls=args.enable_mock_controls)
    def stop(_signum, _frame):
        root.quit()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    root.protocol('WM_DELETE_WINDOW', root.quit)
    try:
        DashboardWindow(root,node,exhibits,config['mock']['locations'])
        root.mainloop()
    finally:
        root.destroy()
        node.destroy_node(); rclpy.try_shutdown()
    return 0
