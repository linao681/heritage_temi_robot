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
    assert interaction_request({'action': 'accept'}) == ('accept', None)
    action, question = interaction_request({'action': 'ask', 'question': '  潮州音乐有哪些？  '})
    assert action == 'ask' and question == '潮州音乐有哪些？'
    for payload in ({'action': 'resume_safety'}, {'action': 'ask', 'question': ''}, {'action': 'ask', 'question': 'x' * 501}):
        with pytest.raises(ValueError):
            interaction_request(payload)
