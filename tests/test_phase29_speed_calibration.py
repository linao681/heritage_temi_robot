from scripts.analyze_phase29_experiment import analyze_speed_window


def sample(stamp, *, odom=0.3, command=0.3, angular=0.0, age=0.02,
           speed_limit=0.6, experiment='CAL-03'):
    return {
        'time_monotonic_sec': str(stamp),
        'experiment_id': experiment,
        'odom_linear_x': str(odom),
        'odom_angular_z': str(angular),
        'odom_sample_age_sec': str(age),
        'odom_message_age_sec': str(age),
        'odom_sample_valid': 'true',
        'cmd_vel_linear_x': str(command),
        'cmd_vel_sample_age_sec': str(age),
        'cmd_vel_sample_valid': 'true',
        'speed_limit_controller_max_vel_x_mps': str(speed_limit),
        'speed_limit_controller_max_speed_xy_mps': str(speed_limit),
        'speed_limit_smoother_max_velocity_x_mps': str(speed_limit),
        'speed_limit_valid': 'true',
    }


def stable_samples(count=22):
    return [sample(index * 0.1) for index in range(count)]


def test_stable_forward_window_passes_using_fresh_odom_and_parameter_readback():
    result = analyze_speed_window(stable_samples(), target_mps=0.3)

    assert result['status'] == 'PASS'
    assert result['valid_sample_count'] == 22
    assert result['window_duration_sec'] == 2.1
    assert result['median_odom_speed_mps'] == 0.3
    assert result['median_cmd_vel_mps'] == 0.3
    assert result['max_sample_gap_sec'] == 0.1
    assert result['speed_limit_readback_valid'] is True


def test_empty_recording_is_not_run():
    result = analyze_speed_window([], target_mps=0.3)

    assert result['status'] == 'NOT_RUN'
    assert result['reason'] == 'no_samples'


def test_stationary_or_zero_command_rows_cannot_form_calibration_window():
    result = analyze_speed_window(
        [sample(index * 0.1, odom=0.0, command=0.0) for index in range(22)],
        target_mps=0.3)

    assert result['status'] == 'FAIL'
    assert result['reason'] == 'no_continuous_motion_command'


def test_stale_odom_and_command_rows_are_rejected():
    result = analyze_speed_window(
        [sample(index * 0.1, age=0.25) for index in range(22)], target_mps=0.3)

    assert result['status'] == 'FAIL'
    assert result['reason'] == 'no_fresh_samples'


def test_short_window_does_not_pass_even_when_speed_matches():
    result = analyze_speed_window(stable_samples(count=19), target_mps=0.3)

    assert result['status'] == 'FAIL'
    assert result['reason'] == 'insufficient_stable_window'
    assert result['valid_sample_count'] == 19


def test_long_gaps_split_a_window_instead_of_being_interpolated():
    samples = [sample(index * 0.1) for index in range(12)]
    samples.extend(sample(2.0 + index * 0.1) for index in range(12))

    result = analyze_speed_window(samples, target_mps=0.3)

    assert result['status'] == 'FAIL'
    assert result['reason'] == 'insufficient_stable_window'
    assert result['valid_sample_count'] == 12


def test_speed_mismatch_is_reported_from_odom_not_configuration():
    result = analyze_speed_window(
        [sample(index * 0.1, odom=0.18) for index in range(22)], target_mps=0.3)

    assert result['status'] == 'FAIL'
    assert result['reason'] == 'speed_outside_tolerance'
    assert result['median_odom_speed_mps'] == 0.18
    assert result['speed_error_mps'] == 0.12


def test_missing_independent_speed_limit_readback_cannot_pass():
    rows = stable_samples()
    for row in rows:
        row['speed_limit_valid'] = 'false'

    result = analyze_speed_window(rows, target_mps=0.3)

    assert result['status'] == 'FAIL'
    assert result['reason'] == 'no_valid_speed_limit_readback'


def test_mixed_run_ids_and_nonmonotonic_time_are_rejected():
    rows = stable_samples()
    rows[-1]['experiment_id'] = 'OTHER-RUN'
    mixed = analyze_speed_window(rows, target_mps=0.3)
    assert mixed['status'] == 'FAIL'
    assert mixed['reason'] == 'mixed_experiment_ids'

    rows = stable_samples()
    rows[5]['time_monotonic_sec'] = rows[4]['time_monotonic_sec']
    unordered = analyze_speed_window(rows, target_mps=0.3)
    assert unordered['status'] == 'FAIL'
    assert unordered['reason'] == 'nonmonotonic_timestamps'
