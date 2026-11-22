#!/usr/bin/env python3
"""Analyze one phase 2.7 report, actor truth record, and topic CSV."""

import argparse
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import statistics


def _number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _first_event(events, predicate):
    selected = [event for event in events
                if _number(event.get('time_monotonic_sec')) is not None and predicate(event)]
    return min(selected, key=lambda event: event['time_monotonic_sec']) if selected else None


def _sample_near(samples, timestamp, max_age_sec=0.5):
    timestamp = _number(timestamp)
    if timestamp is None:
        return None
    timestamped = [sample for sample in samples
                   if _number(sample.get('time_monotonic_sec')) is not None]
    if not timestamped:
        return None
    selected = min(timestamped,
                   key=lambda sample: abs(sample['time_monotonic_sec'] - timestamp))
    return selected if abs(selected['time_monotonic_sec'] - timestamp) <= max_age_sec else None


def _stage(sample, recovery_status):
    phase = sample.get('actor_phase')
    if phase == 'LEAVE':
        return 'ACTOR_LEAVING'
    if phase == 'HOLD_CLEAR':
        return 'RECOVERED' if recovery_status in {'PASS', 'PASS_WITH_RISK'} else 'HOLD_CLEAR'
    if (phase == 'HOLD_TARGET' and sample.get('safety_state') == 'STOP_CONFIRMED' and
            sample.get('navigation_session_id')):
        return 'STOP_CONFIRMED_HOLD'
    if sample.get('safety_state') in {'STOP_REQUESTED', 'STOP_COMMAND_ACCEPTED',
                                      'STOPPING', 'STOP_FAILED'}:
        return 'BRAKING'
    return 'MOVING'


def analyze_experiment(truth, report, csv_rows, target_robot_speed_mps):
    """Return event, distance, speed calibration, and timeline metrics without inference."""
    target = _number(target_robot_speed_mps)
    if target is None or target <= 0.0:
        raise ValueError('target_robot_speed_mps must be finite and positive')
    samples = truth.get('gazebo_model_state_samples', [])
    samples = sorted((dict(sample) for sample in samples
                      if _number(sample.get('time_monotonic_sec')) is not None),
                     key=lambda sample: sample['time_monotonic_sec'])
    movement_start = _number(truth.get('movement_started_monotonic_sec'))
    movement_end = _number(truth.get('movement_ended_monotonic_sec'))
    stops = sorted(report.get('stop_status_events', []),
                   key=lambda event: _number(event.get('time_monotonic_sec'))
                   if _number(event.get('time_monotonic_sec')) is not None else math.inf)
    perception = report.get('perception_events', [])
    speed_events = report.get('speed_controller_events', [])

    def in_actor_window(event):
        timestamp = _number(event.get('time_monotonic_sec'))
        return (timestamp is not None and
                (movement_start is None or timestamp >= movement_start) and
                (movement_end is None or timestamp <= movement_end))

    first_detection = _first_event(perception, lambda event: (
        in_actor_window(event) and (
            (event.get('person_observation_valid') is True and
             (_number(event.get('people_count')) or 0) > 0) or
            str(event.get('person_observation_state', '')).startswith('PERSONS_DETECTED'))))
    first_rgbd = _first_event(perception, lambda event: (
        in_actor_window(event) and
        event.get('person_distance_valid') is True and
        _number(event.get('nearest_person_m')) is not None))
    first_slow = _first_event(speed_events, lambda event: (
        in_actor_window(event) and
        (event.get('status') or {}).get('state') == 'SLOW' and
        any(word in str((event.get('status') or {}).get('reason', '')).lower()
            for word in ('person', 'visitor', '人员', '游客'))))
    stop_request = _first_event(stops, lambda event: (
        in_actor_window(event) and event.get('state') == 'STOP_REQUESTED' and
        bool(event.get('navigation_session_id'))))
    if stop_request is None:
        speed_request = _first_event(speed_events, lambda event: (
            in_actor_window(event) and
            (event.get('status') or {}).get('stop_requested') is True and
            bool((event.get('status') or {}).get('navigation_session_id'))))
        if speed_request:
            status = speed_request.get('status') or {}
            stop_request = {
                'time_monotonic_sec': speed_request['time_monotonic_sec'],
                'state': 'STOP_REQUESTED',
                'navigation_session_id': status['navigation_session_id'],
                'source': 'speed_controller',
                'valid': status.get('input_valid') is not False,
            }
    matching_confirm = None
    response_sec = None
    confirmed_sample = None
    failure_reason = None
    if stop_request:
        request_time = _number(stop_request.get('time_monotonic_sec'))
        session_id = stop_request.get('navigation_session_id')
        matching_confirm = _first_event(stops, lambda event: (
            event.get('state') == 'STOP_CONFIRMED' and event.get('valid') is True and
            event.get('navigation_session_id') == session_id and
            _number(event.get('time_monotonic_sec')) is not None and
            _number(event.get('time_monotonic_sec')) >= request_time))
        if matching_confirm:
            confirm_time = _number(matching_confirm.get('time_monotonic_sec'))
            response_sec = confirm_time - request_time
            confirmed_sample = _sample_near(samples, confirm_time)
        else:
            failure_reason = 'matching stop confirmation not observed'
    else:
        failure_reason = 'STOP_REQUESTED not observed'

    request_sample = (_sample_near(samples, stop_request.get('time_monotonic_sec'))
                      if stop_request else None)
    minima = {}
    for sample in samples:
        phase = sample.get('actor_phase') or 'UNKNOWN'
        center = _number(sample.get('center_distance_m'))
        gap = _number(sample.get('geometry_gap_m'))
        slot = minima.setdefault(phase, {'minimum_center_distance_m': None,
                                         'minimum_geometry_gap_m': None,
                                         'sample_count': 0})
        slot['sample_count'] += 1
        if center is not None:
            slot['minimum_center_distance_m'] = (
                center if slot['minimum_center_distance_m'] is None else
                min(slot['minimum_center_distance_m'], center))
        if gap is not None:
            slot['minimum_geometry_gap_m'] = (
                gap if slot['minimum_geometry_gap_m'] is None else
                min(slot['minimum_geometry_gap_m'], gap))

    unique_times = {timestamp for row in csv_rows
                    if (timestamp := _number(row.get('time_monotonic_sec'))) is not None}
    pre_window = []
    if movement_start is not None:
        pre_window = [(timestamp, _number(row.get('current_robot_speed_mps')))
                      for row in csv_rows
                      if (timestamp := _number(row.get('time_monotonic_sec'))) is not None and
                      movement_start - 2.0 <= timestamp < movement_start and
                      _number(row.get('current_robot_speed_mps')) is not None]
    speeds = [speed for _, speed in pre_window]
    median_speed = statistics.median(speeds) if speeds else None
    coverage = ((max(timestamp for timestamp, _ in pre_window) -
                 min(timestamp for timestamp, _ in pre_window)) if len(pre_window) > 1 else 0.0)
    tolerance = max(target * 0.10, 0.05)
    speed_met = (median_speed is not None and len(pre_window) >= 4 and coverage >= 1.5 and
                 abs(median_speed - target) <= tolerance)

    timeline = []
    recovery_status = (report.get('dynamic_scenario', {}).get('recovery_evidence') or {}).get('status')
    for sample in samples:
        timeline.append({
            'time_monotonic_sec': sample['time_monotonic_sec'],
            'stage': _stage(sample, recovery_status),
            'actor_phase': sample.get('actor_phase'),
            'center_distance_m': _number(sample.get('center_distance_m')),
            'geometry_gap_m': _number(sample.get('geometry_gap_m')),
            'robot_speed_mps': _number(sample.get('odom_speed_mps')),
            'safety_state': sample.get('safety_state'),
            'navigation_session_id': sample.get('navigation_session_id'),
        })

    geometry_overlap = any(
        _number(sample.get('geometry_gap_m')) is not None and
        _number(sample.get('geometry_gap_m')) <= 0.0 for sample in samples)
    risk = truth.get('actor_motion', {}).get('geometry_risk')
    if not samples or truth.get('status') != 'PASS':
        status = 'FAIL'
    elif geometry_overlap or risk:
        status = 'FAIL'
    elif not speed_met or response_sec is None:
        status = 'PASS_WITH_RISK'
    else:
        status = 'PASS'

    response_minimum = min(
        (_number(sample.get('center_distance_m')) for sample in samples
         if _number(sample.get('center_distance_m')) is not None and
         (not matching_confirm or
          sample['time_monotonic_sec'] >= _number(matching_confirm.get('time_monotonic_sec')))),
        default=None)
    return {
        'analysis_status': status,
        'data_sources': {'positions': 'Gazebo /model_states readback',
                         'robot_speed': 'record_phase2_topics.csv current_robot_speed_mps',
                         'safety_events': 'TourEvidence stop_status_events'},
        'movement_started_monotonic_sec': movement_start,
        'movement_ended_monotonic_sec': _number(truth.get('movement_ended_monotonic_sec')),
        'first_visual_detection': first_detection,
        'first_rgbd_distance': first_rgbd,
        'first_person_slow': first_slow,
        'stop_request': stop_request,
        'stop_response': {
            'navigation_session_id': (stop_request or {}).get('navigation_session_id'),
            'response_sec': response_sec,
            'request_distance_m': (_number(request_sample.get('center_distance_m'))
                                   if request_sample else None),
            'confirmed_distance_m': (_number(confirmed_sample.get('center_distance_m'))
                                     if confirmed_sample else None),
            'minimum_center_distance_m': response_minimum,
            'failure_reason': failure_reason,
        },
        'speed_condition': {'target_mps': target, 'median_mps': median_speed,
                            'sample_count': len(pre_window), 'window_coverage_sec': coverage,
                            'tolerance_mps': tolerance, 'met': bool(speed_met)},
        'minimum_distances_by_actor_phase': minima,
        'unique_observation_timestamps': len(unique_times),
        'contact_observed': truth.get('actor_motion', {}).get('contact_observed'),
        'geometry_risk': risk,
        'timeline': timeline,
        'limitations': [
            'Circumscribed-circle geometry is a conservative proxy, not contact sensing.',
            'A missing STOP_CONFIRMED yields null response time; it is not inferred from zero cmd_vel.',
            'Repeated timestamps count as one observation for freshness analysis.',
        ],
        'analyzed_utc': datetime.now(timezone.utc).isoformat(),
    }


def _write_csv(path, rows, columns):
    with Path(path).open('w', newline='', encoding='utf-8') as output:
        writer = csv.DictWriter(output, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _svg_plot(path, timeline):
    valid = [sample for sample in timeline
             if sample['center_distance_m'] is not None and
             sample['robot_speed_mps'] is not None]
    width, height = 900, 520
    left, right, top, bottom = 80, 860, 45, 470
    if not valid:
        points = ''
        label = 'No aligned Gazebo distance and odometry samples'
    else:
        times = [sample['time_monotonic_sec'] for sample in valid]
        distances = [sample['center_distance_m'] for sample in valid]
        speeds = [sample['robot_speed_mps'] for sample in valid]
        t_min, t_max = min(times), max(times)
        d_min, d_max = min(0.0, min(distances)), max(distances)
        v_min, v_max = min(0.0, min(speeds)), max(speeds)
        t_span = max(t_max - t_min, 1e-9)
        d_span = max(d_max - d_min, 1e-9)
        v_span = max(v_max - v_min, 1e-9)
        distance_points = []
        speed_points = []
        for sample in valid:
            x = left + (sample['time_monotonic_sec'] - t_min) / t_span * (right - left)
            yd = bottom - (sample['center_distance_m'] - d_min) / d_span * (bottom - top)
            yv = bottom - (sample['robot_speed_mps'] - v_min) / v_span * (bottom - top)
            distance_points.append(f'{x:.1f},{yd:.1f}')
            speed_points.append(f'{x:.1f},{yv:.1f}')
        joined_distance = ' '.join(distance_points)
        joined_speed = ' '.join(speed_points)
        points = (f'<polyline fill=\"none\" stroke=\"#a45b25\" stroke-width=\"3\" '
                  f'points=\"{joined_distance}\"/>'
                  f'<polyline fill=\"none\" stroke=\"#1f6a5c\" stroke-width=\"3\" '
                  f'points=\"{joined_speed}\"/>')
        label = 'Gazebo center distance (brown) and odom speed (green)'
    svg = f'''<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"{width}\" height=\"{height}\" viewBox=\"0 0 {width} {height}\">
<rect width=\"100%\" height=\"100%\" fill=\"#fbfaf7\"/>
<text x=\"80\" y=\"28\" font-family=\"sans-serif\" font-size=\"18\">Phase 2.7 recorded distance and speed</text>
<rect x=\"{left}\" y=\"{top}\" width=\"{right-left}\" height=\"{bottom-top}\" fill=\"white\" stroke=\"#8f897d\"/>
<text x=\"{left}\" y=\"500\" font-family=\"sans-serif\" font-size=\"13\">Recorded monotonic time (s)</text>
<text x=\"90\" y=\"66\" font-family=\"sans-serif\" font-size=\"12\">Distance m / speed m/s</text>
{points}
<text x=\"80\" y=\"{height-12}\" font-family=\"sans-serif\" font-size=\"12\">{label}</text>
</svg>'''
    Path(path).write_text(svg, encoding='utf-8')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--truth', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--csv', type=Path, required=True)
    parser.add_argument('--target-robot-speed-mps', type=float, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args(argv)
    truth = json.loads(args.truth.read_text(encoding='utf-8'))
    report = json.loads(args.report.read_text(encoding='utf-8'))
    with args.csv.open(newline='', encoding='utf-8') as source:
        csv_rows = list(csv.DictReader(source))
    result = analyze_experiment(truth, report, csv_rows, args.target_robot_speed_mps)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / 'analysis.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    _write_csv(args.output_dir / 'phase_timeline.csv', result['timeline'], [
        'time_monotonic_sec', 'stage', 'actor_phase', 'center_distance_m',
        'geometry_gap_m', 'robot_speed_mps', 'safety_state', 'navigation_session_id'])
    _write_csv(args.output_dir / 'speed_comparison.csv', [{
        'target_robot_speed_mps': result['speed_condition']['target_mps'],
        'median_robot_speed_mps': result['speed_condition']['median_mps'],
        'speed_condition_met': result['speed_condition']['met'],
        'stop_response_sec': result['stop_response']['response_sec'],
        'minimum_center_distance_m': result['stop_response']['minimum_center_distance_m'],
        'analysis_status': result['analysis_status'],
    }], ['target_robot_speed_mps', 'median_robot_speed_mps', 'speed_condition_met',
         'stop_response_sec', 'minimum_center_distance_m', 'analysis_status'])
    _svg_plot(args.output_dir / 'distance_speed.svg', result['timeline'])
    print(json.dumps({'analysis_status': result['analysis_status'],
                      'analysis_file': str(args.output_dir / 'analysis.json')},
                     ensure_ascii=False))
    return 0 if result['analysis_status'] != 'FAIL' else 1


if __name__ == '__main__':
    raise SystemExit(main())
