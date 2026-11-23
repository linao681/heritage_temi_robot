"""Analyze recorded speed calibration samples without connecting to ROS."""
import argparse
import csv
import json
import math
from pathlib import Path
from statistics import median, pstdev


MIN_STABLE_DURATION_SEC = 2.0
MIN_STABLE_SAMPLES = 20
MAX_SAMPLE_AGE_SEC = 0.2
MAX_SAMPLE_GAP_SEC = 0.2
MAX_ANGULAR_SPEED_RAD_S = 0.05
MIN_COMMAND_SPEED_MPS = 0.05
SPEED_TOLERANCE_MPS = 0.05


def _number(row, name):
    try:
        value = float(row.get(name, ''))
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _is_true(value):
    return value is True or (isinstance(value, str) and value.strip().lower() == 'true')


def _result(status, reason, target_mps, **values):
    return {
        'status': status,
        'reason': reason,
        'target_speed_mps': float(target_mps),
        'speed_limit_readback_valid': False,
        **values,
    }


def _sample_is_eligible(row, target_mps):
    if not _is_true(row.get('odom_sample_valid')) or not _is_true(
            row.get('cmd_vel_sample_valid')):
        return False, 'no_fresh_samples'
    odom_age = _number(row, 'odom_sample_age_sec')
    odom_message_age = _number(row, 'odom_message_age_sec')
    command_age = _number(row, 'cmd_vel_sample_age_sec')
    if (odom_age is None or odom_message_age is None or command_age is None or
            odom_age < 0 or odom_message_age < 0 or command_age < 0 or
            odom_age > MAX_SAMPLE_AGE_SEC or odom_message_age > MAX_SAMPLE_AGE_SEC or
            command_age > MAX_SAMPLE_AGE_SEC):
        return False, 'no_fresh_samples'

    odom_speed = _number(row, 'odom_linear_x')
    angular_speed = _number(row, 'odom_angular_z')
    command_speed = _number(row, 'cmd_vel_linear_x')
    if odom_speed is None or angular_speed is None or command_speed is None:
        return False, 'invalid_motion_sample'
    if angular_speed < -MAX_ANGULAR_SPEED_RAD_S or angular_speed > MAX_ANGULAR_SPEED_RAD_S:
        return False, 'turning_or_angular_motion'
    if command_speed < MIN_COMMAND_SPEED_MPS:
        return False, 'no_continuous_motion_command'

    if not _is_true(row.get('speed_limit_valid')):
        return False, 'no_valid_speed_limit_readback'
    limits = (
        _number(row, 'speed_limit_controller_max_vel_x_mps'),
        _number(row, 'speed_limit_controller_max_speed_xy_mps'),
        _number(row, 'speed_limit_smoother_max_velocity_x_mps'),
    )
    if any(value is None or value <= 0 for value in limits):
        return False, 'no_valid_speed_limit_readback'
    if min(limits) < target_mps:
        return False, 'speed_limit_below_target'
    return True, ''


def analyze_speed_window(samples, target_mps):
    """Measure one contiguous straight-motion window from recorded rows.

    A passing result requires fresh odometry and cmd_vel, independent Nav2
    controller/smoother parameter readback, at least 20 samples over 2 seconds,
    no sample gap above 0.2 seconds, low angular speed, and median odom speed
    within 0.05 m/s of the requested target. Missing data never gets filled in.
    """
    if (not isinstance(target_mps, (int, float)) or not math.isfinite(target_mps) or
            target_mps <= 0):
        raise ValueError('target_mps must be finite and positive')
    rows = list(samples)
    if not rows:
        return _result('NOT_RUN', 'no_samples', target_mps)

    experiment_ids = {str(row.get('experiment_id', '')).strip() for row in rows}
    if len(experiment_ids) != 1 or not next(iter(experiment_ids)):
        return _result('FAIL', 'mixed_experiment_ids', target_mps)

    times = [_number(row, 'time_monotonic_sec') for row in rows]
    if any(value is None for value in times):
        return _result('FAIL', 'invalid_timestamps', target_mps)
    if any(current <= previous for previous, current in zip(times, times[1:])):
        return _result('FAIL', 'nonmonotonic_timestamps', target_mps)

    runs = []
    current_run = []
    rejected_reasons = set()
    eligible_sample_count = 0
    for row, stamp in zip(rows, times):
        eligible, reason = _sample_is_eligible(row, float(target_mps))
        if not eligible:
            rejected_reasons.add(reason)
            if current_run:
                runs.append(current_run)
                current_run = []
            continue
        eligible_sample_count += 1
        if current_run and stamp - current_run[-1][0] > MAX_SAMPLE_GAP_SEC:
            runs.append(current_run)
            current_run = []
        current_run.append((stamp, row))
    if current_run:
        runs.append(current_run)

    longest = max(runs, key=lambda run: (run[-1][0] - run[0][0], len(run)), default=[])
    if not longest:
        priority = (
            'no_valid_speed_limit_readback', 'speed_limit_below_target',
            'no_fresh_samples', 'no_continuous_motion_command',
            'turning_or_angular_motion', 'invalid_motion_sample')
        reason = next((item for item in priority if item in rejected_reasons), 'no_stable_window')
        return _result('FAIL', reason, target_mps, eligible_sample_count=0,
                       valid_sample_count=0)

    start, end = longest[0][0], longest[-1][0]
    duration = end - start
    max_gap = max((current[0] - previous[0]
                   for previous, current in zip(longest, longest[1:])), default=0.0)
    odom_values = [_number(row, 'odom_linear_x') for _, row in longest]
    command_values = [_number(row, 'cmd_vel_linear_x') for _, row in longest]
    median_odom = median(odom_values)
    median_command = median(command_values)
    error = abs(median_odom - float(target_mps))
    result_values = {
        'experiment_id': next(iter(experiment_ids)),
        'window_start_monotonic_sec': round(start, 6),
        'window_end_monotonic_sec': round(end, 6),
        'window_duration_sec': round(duration, 6),
        'max_sample_gap_sec': round(max_gap, 6),
        'valid_sample_count': len(longest),
        'eligible_sample_count': eligible_sample_count,
        'median_odom_speed_mps': round(median_odom, 6),
        'median_cmd_vel_mps': round(median_command, 6),
        'odom_speed_stddev_mps': round(pstdev(odom_values), 6),
        'speed_error_mps': round(error, 6),
        'speed_limit_readback_valid': True,
    }
    if (len(longest) < MIN_STABLE_SAMPLES or duration < MIN_STABLE_DURATION_SEC or
            max_gap > MAX_SAMPLE_GAP_SEC):
        return _result('FAIL', 'insufficient_stable_window', target_mps, **result_values)
    if error > SPEED_TOLERANCE_MPS:
        return _result('FAIL', 'speed_outside_tolerance', target_mps, **result_values)
    return _result('PASS', 'stable_odom_window_within_tolerance', target_mps, **result_values)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, type=Path, help='phase2 recorder CSV')
    parser.add_argument('--target-speed', required=True, type=float)
    args = parser.parse_args()
    with args.input.open(newline='', encoding='utf-8') as stream:
        result = analyze_speed_window(csv.DictReader(stream), args.target_speed)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
