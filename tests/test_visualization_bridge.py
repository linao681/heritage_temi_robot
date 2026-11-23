import math
import pytest


def test_ros_to_threejs_position_and_heading():
    from scripts.visualization_bridge import convert_pose
    assert convert_pose(2, 3, 0) == pytest.approx({'x': 2, 'z': -3, 'yaw': math.pi/2})
    assert convert_pose(-1, 4, math.pi/2) == pytest.approx({'x': -1, 'z': -4, 'yaw': math.pi})


def test_live_visitors_use_gazebo_model_poses():
    from geometry_msgs.msg import Pose
    from scripts.visualization_bridge import visitor_poses
    pose = Pose()
    pose.position.x, pose.position.y, pose.orientation.w = 2.0, 3.0, 1.0
    result = visitor_poses(['heritage_robot', 'phase25_person_01'], [pose, pose])
    assert len(result) == 1
    assert result[0]['id'] == 'phase25_person_01'
    assert {k: result[0][k] for k in ('x', 'z', 'yaw')} == pytest.approx({'x': 2, 'z': -3, 'yaw': math.pi/2})


def test_interaction_action_is_bounded_and_requires_question():
    from scripts.visualization_bridge import interaction_request
    assert interaction_request({'action': 'accept'}) == ('accept', None, 'basic')
    action, question, level = interaction_request({'action': 'ask', 'question': '  潮州音乐有哪些？  '})
    assert action == 'ask' and question == '潮州音乐有哪些？' and level == 'basic'
    assert interaction_request({'action': 'ask', 'question': '潮剧怎么唱',
                                'level': 'child'}) == ('ask', '潮剧怎么唱', 'child')
    for payload in ({'action': 'resume_safety'}, {'action': 'ask', 'question': ''},
                    {'action': 'ask', 'question': 'x' * 501},
                    {'action': 'ask', 'question': '潮剧怎么唱', 'level': 'unknown'}):
        with pytest.raises(ValueError):
            interaction_request(payload)


def test_only_business_script_resume_uses_scripted_team_gate():
    from scripts.visualization_bridge import resume_requires_scripted_gather
    assert resume_requires_scripted_gather('business_script') is True
    assert resume_requires_scripted_gather('vision_conservative') is False


def test_vision_mode_controls_do_not_use_gazebo_truth_as_resume_gate():
    from pathlib import Path
    source = Path(__file__).resolve().parents[1] / 'visualization/ros_hall/ros-live.js'
    live = source.read_text()
    assert "data.team_decision_mode==='business_script'" in live
    assert "data.team_decision_mode==='vision_conservative'" in live


def test_tour_status_keeps_real_state_history_for_event_timeline():
    from pathlib import Path
    source = Path(__file__).resolve().parents[1] / 'scripts/visualization_bridge.py'
    bridge = source.read_text()
    live = (source.parents[1] / 'visualization/ros_hall/ros-live.js').read_text()
    assert "'history'" in bridge
    assert "'team_recovery_required'" in bridge
    assert "'team_resume_confirmed'" in bridge
    assert "'recovery_ack_id'" in bridge
    assert 'ROS状态机事件时间线' in live


def test_nav2_limit_summary_reports_parameters_without_claiming_full_effective_speed():
    from scripts.visualization_bridge import summarize_nav2_speed_limits
    values = summarize_nav2_speed_limits(0.4, 0.45, [0.5, 1.0, 1.2])
    assert values['valid'] is True
    assert values['controller_followpath_max_vel_x_mps'] == 0.4
    assert values['controller_followpath_max_speed_xy_mps'] == 0.45
    assert values['velocity_smoother_max_velocity_x_mps'] == 0.5
    assert 'effective_speed_limit_mps' not in values
    assert summarize_nav2_speed_limits(float('nan'), 0.45, [0.5])['valid'] is False
