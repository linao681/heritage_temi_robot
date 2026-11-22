#!/usr/bin/env python3
"""Counterfactual policy replay over recorded E03 sensor/odom samples (not a Gazebo rerun)."""
import argparse
import csv
import math
from pathlib import Path
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ros2_ws/src/temi_speed_controller'))
from temi_speed_controller.speed_policy import SpeedConfig, SpeedController, SpeedInputs


DEFAULT_INPUT = (ROOT / 'docs/experiments/phase2_5/dynamic_people/approaching/'
                 '20261122-0008-late-stop-fix-delay8/segment.csv')
DEFAULT_CONFIG = ROOT / 'ros2_ws/src/temi_speed_controller/config/speed_config.yaml'
FIELDS = ('row', 'relative_time_sec', 'navigation_session_id', 'person_observation_state',
          'person_distance_valid', 'nearest_person_m', 'robot_odom_speed_mps',
          'sample_age_sec', 'approach_speed_mps', 'dynamic_stop_distance_m',
          'policy_state', 'policy_reason', 'counterfactual_target_speed_mps',
          'counterfactual_stop_requested', 'recorded_gt_center_distance_m',
          'recorded_gt_surface_proxy_m')


def load_config(path):
    with path.open(encoding='utf-8') as source:
        document = yaml.safe_load(source)
    values = document['speed_controller']['ros__parameters']
    defaults = SpeedConfig()
    return SpeedConfig(**{name: values.get(name, getattr(defaults, name))
                          for name in vars(defaults)})


def replay(input_path, config, start_after_sec, end_after_sec=None):
    with input_path.open(newline='', encoding='utf-8') as source:
        records = list(csv.DictReader(source))
    if not records:
        raise ValueError('E03 输入记录为空')
    origin = float(records[0]['time_monotonic_sec'])
    selected = [(index, row) for index, row in enumerate(records, 1)
                if float(row['time_monotonic_sec']) - origin >= start_after_sec and
                (end_after_sec is None or
                 float(row['time_monotonic_sec']) - origin <= end_after_sec)]
    if not selected:
        raise ValueError('所选 E03 时间范围没有记录')
    controller = SpeedController(config)
    session_id = next((row['navigation_session_id'] for _, row in selected
                       if row['navigation_session_id']), 'e03-offline-replay')
    output = []
    for index, row in selected:
        now = float(row['time_monotonic_sec'])
        relative = now - origin
        age = float(row['perception_age_sec'] or 0.0)
        observation = row['person_observation_state']
        raw_distance = row['nearest_person_m']
        valid = row['fusion_valid'].lower() == 'true'
        distance_valid = bool(valid and observation == 'PERSON_DISTANCE_VALID' and raw_distance)
        distance = float(raw_distance) if distance_valid else None
        obstacle = float(row['obstacle_distance_m']) if row['obstacle_distance_m'] else None
        robot_speed = abs(float(row['odom_linear_x']))
        inputs = SpeedInputs(
            now=now, nearest_person_m=distance, crowd_density=None,
            obstacle_distance_m=obstacle, group_state='following', navigating=True,
            explaining=False, navigation_error=False, safety_stop=False,
            position_valid=True, communication_valid=True, stop_confirmed=False,
            navigation_session_id=session_id, sample_age_sec=age,
            source_allowed=True, people_valid=valid,
            person_distance_valid=distance_valid, crowd_density_valid=False,
            obstacle_distance_valid=bool(valid and obstacle is not None),
            safety_stop_valid=valid, person_observation_state=observation,
            person_distance_timestamp_sec=(now - age if distance_valid else None),
            current_speed_mps=robot_speed, current_speed_valid=True)
        decision = controller.update(inputs, now)
        output.append({
            'row': index, 'relative_time_sec': f'{relative:.3f}',
            'navigation_session_id': session_id,
            'person_observation_state': observation,
            'person_distance_valid': distance_valid,
            'nearest_person_m': '' if distance is None else f'{distance:.4f}',
            'robot_odom_speed_mps': f'{robot_speed:.4f}',
            'sample_age_sec': f'{age:.4f}',
            'approach_speed_mps': f'{decision.approach_speed_mps:.4f}',
            'dynamic_stop_distance_m': f'{decision.dynamic_stop_distance_m:.4f}',
            'policy_state': decision.state, 'policy_reason': decision.reason,
            'counterfactual_target_speed_mps': (
                '' if decision.target_speed_mps is None else f'{decision.target_speed_mps:.4f}'),
            'counterfactual_stop_requested': decision.stop_requested,
            'recorded_gt_center_distance_m': row['gazebo_ground_truth_center_distance_m'],
            'recorded_gt_surface_proxy_m': row['gazebo_ground_truth_distance_m'],
        })
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=DEFAULT_INPUT)
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    parser.add_argument('--start-after-sec', type=float, default=11.1)
    parser.add_argument('--end-after-sec', type=float, default=13.4)
    parser.add_argument('--output', type=Path,
                        default=ROOT / 'docs/phase2_6_overnight/stopping_distance.csv')
    args = parser.parse_args()
    if (not math.isfinite(args.start_after_sec) or args.start_after_sec < 0 or
            not math.isfinite(args.end_after_sec) or args.end_after_sec < args.start_after_sec):
        parser.error('时间范围必须是有限非负数，且结束时间不得早于开始时间')
    rows = replay(args.input, load_config(args.config), args.start_after_sec, args.end_after_sec)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('w', newline='', encoding='utf-8') as destination:
        writer = csv.DictWriter(destination, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    stop = next((row for row in rows if row['counterfactual_stop_requested']), None)
    print(f'rows={len(rows)}; first_counterfactual_stop={stop}; output={args.output}')


if __name__ == '__main__':
    main()
