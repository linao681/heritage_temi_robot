"""Plot live phase 2 topic recordings and summarize measured transitions."""
import argparse
import csv
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
from matplotlib import font_manager
import matplotlib.pyplot as plt

_cjk_font = Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')
if _cjk_font.exists():
    font_manager.fontManager.addfont(str(_cjk_font))
    plt.rcParams['font.family'] = 'Noto Sans CJK JP'
plt.rcParams['axes.unicode_minus'] = False


def number(value):
    try:
        parsed = float(value)
        return parsed if math.isfinite(parsed) else None
    except (TypeError, ValueError):
        return None


def boolean(value):
    return value == 'true' if isinstance(value, str) else value is True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv', type=Path)
    args = parser.parse_args()
    with args.csv.open(newline='', encoding='utf-8') as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise SystemExit('录制文件没有数据行，未生成曲线。')
    output = args.csv.parent
    t0 = number(rows[0].get('time_monotonic_sec')) or 0.0
    times = [(number(row.get('time_monotonic_sec')) or t0) - t0 for row in rows]

    fig, ax = plt.subplots(figsize=(12, 5.5), constrained_layout=True)
    for key, label in (('target_speed_mps', '目标速度'),
                       ('cmd_vel_linear_x', '底盘控制指令 /cmd_vel'),
                       ('odom_linear_x', 'Gazebo 里程计 /odom')):
        values = [number(row.get(key)) for row in rows]
        if any(value is not None for value in values):
            ax.plot(times, values, label=label, linewidth=1.4)
    ax.set(title='阶段2实际速度记录', xlabel='记录时间 (s)', ylabel='线速度 (m/s)')
    ax.grid(True, alpha=0.25)
    ax.legend(loc='best')
    fig.savefig(output / 'speed_curve.png', dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(12, 5.5), constrained_layout=True)
    for key, label in (('nearest_person_m', 'RGB-D 人员中心距离'),
                       ('gazebo_ground_truth_center_distance_m', 'Gazebo 人员中心真值'),
                       ('obstacle_distance_m', 'LaserScan 前向障碍距离')):
        values = [number(row.get(key)) for row in rows]
        if any(value is not None for value in values):
            ax.plot(times, values, label=label, linewidth=1.4)
    ax.set(title='阶段2实测距离记录', xlabel='记录时间 (s)', ylabel='距离 (m)')
    ax.grid(True, alpha=0.25)
    ax.legend(loc='best')
    fig.savefig(output / 'distance_curve.png', dpi=160)
    plt.close(fig)

    transitions = []
    last = {}
    stop_requested_at = None
    stop_latencies = []
    confirmations = 0
    absolute_errors = []
    fov_detection_samples = []
    people_count_errors = []
    person_distance_errors = []
    for index, row in enumerate(rows):
        for key in ('tour_state', 'speed_controller_state', 'navigation_session_id'):
            value = row.get(key, '')
            if value != last.get(key, ''):
                transitions.append({'time_sec': times[index], 'field': key,
                                    'from': last.get(key, ''), 'to': value})
                last[key] = value
        if boolean(row.get('stop_requested')):
            stop_requested_at = times[index] if stop_requested_at is None else stop_requested_at
        if boolean(row.get('stop_confirmed')):
            if index == 0 or not boolean(rows[index - 1].get('stop_confirmed')):
                confirmations += 1
                if stop_requested_at is not None:
                    stop_latencies.append(max(0.0, times[index] - stop_requested_at))
                stop_requested_at = None
        command, odom = number(row.get('cmd_vel_linear_x')), number(row.get('odom_linear_x'))
        if command is not None and odom is not None:
            absolute_errors.append(abs(command - odom))
        fov_count = number(row.get('gazebo_ground_truth_person_fov_count'))
        if fov_count is not None and fov_count > 0:
            observed_count = number(row.get('people_count'))
            if observed_count is not None:
                fov_detection_samples.append(observed_count > 0)
                people_count_errors.append(abs(observed_count - fov_count))
        estimated = number(row.get('nearest_person_m'))
        truth_camera_z = number(row.get('gazebo_ground_truth_fov_nearest_camera_z_m'))
        if estimated is not None and truth_camera_z is not None:
            person_distance_errors.append(abs(estimated - truth_camera_z))

    (output / 'state_transitions.json').write_text(
        json.dumps(transitions, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    elapsed = times[-1] if times else 0.0
    report = [
        '# 阶段2 ROS2 实测记录分析', '',
        f'- 输入文件：`{args.csv.name}`',
        f'- 采样行数：{len(rows)}',
        f'- 记录时长：{elapsed:.2f} s',
        f'- 状态变化数：{len(transitions)}',
        f'- 实测停车确认次数：{confirmations}',
        f'- 平均控制指令与里程计速度绝对差：{sum(absolute_errors) / len(absolute_errors):.3f} m/s' if absolute_errors else '- 速度跟踪误差：缺少有效 `/cmd_vel` 与 `/odom` 样本',
        f'- YOLOX 相机视场候选帧检出率：{sum(fov_detection_samples) / len(fov_detection_samples):.1%}（{sum(fov_detection_samples)}/{len(fov_detection_samples)}；只判定至少检出1人）' if fov_detection_samples else '- YOLOX 检出率：未测量；记录中没有相机视场候选真值，视场外 Gazebo 人物不计作漏检',
        f'- 相机视场候选人数 MAE：{sum(people_count_errors) / len(people_count_errors):.3f} 人（未建模遮挡）' if people_count_errors else '- 视场候选人数误差：未测量或无配对样本',
        f'- RGB-D 距离对 Gazebo 最近视场候选前向深度 MAE：{sum(person_distance_errors) / len(person_distance_errors):.3f} m（{len(person_distance_errors)} 对）' if person_distance_errors else '- RGB-D 距离误差：未测量或无配对样本',
        f'- 停车请求到确认平均耗时：{sum(stop_latencies) / len(stop_latencies):.3f} s' if stop_latencies else '- 停车确认耗时：本段记录未包含完整请求与确认过程',
        '',
        '图表直接来自 ROS2 `/cmd_vel`、`/odom`、融合感知与 `/gazebo/model_states`。相机候选按模型中心位于水平视场和深度范围估算，不包含垂直视场与遮挡；距离误差将 RGB-D 检测深度与最近候选模型的 Gazebo 前向深度配对。空值代表无配对样本，未插值或合成曲线。',
    ]
    (output / 'experiment_report.md').write_text('\n'.join(report) + '\n', encoding='utf-8')
    print(json.dumps({'rows': len(rows), 'elapsed_sec': elapsed,
                      'speed_curve': str(output / 'speed_curve.png'),
                      'distance_curve': str(output / 'distance_curve.png'),
                      'transitions': str(output / 'state_transitions.json')}))


if __name__ == '__main__':
    main()
