import math
import pytest
from scripts.visitor_trail import VisitorTrail, advance


def test_turn_follows_history_instead_of_cutting_corner():
    trail = VisitorTrail()
    for xy in [(0, 0), (.5, 0), (1, 0), (1, .5), (1, 1)]:
        trail.append(*xy)
    assert trail.sample(.75) == pytest.approx((.75, 0, 0))
    assert trail.sample(1.25) == pytest.approx((1, .25, math.pi/2))
    assert advance(1, 2, .5, .1) == pytest.approx(1.05)
    assert advance(1, .5, .5, .1) == 1
    assert advance(1, 2, .5, 10) == pytest.approx(1.1)


def test_teleport_or_invalid_pose_is_rejected():
    trail = VisitorTrail()
    trail.append(0, 0)
    with pytest.raises(ValueError):
        trail.append(2, 0)
    with pytest.raises(ValueError):
        trail.append(float('nan'), 0)


def test_entrance_turn_target_stays_outside_robot_clearance():
    from scripts.visitor_trail import following_target
    trail = VisitorTrail()
    for i in range(13):
        trail.append(6-i*.5, 0)
    for y in (.5, 1, 1.5):
        trail.append(0, y)
    robot = {'x': 0, 'y': 1.5}
    target = following_target(trail, 3, 2.4, robot)
    x, y, _ = trail.sample(target)
    assert target < trail.length-2.4
    assert math.hypot(x, y-1.5) >= 2.05
    assert following_target(trail, 3, 2.4, robot, predecessor=4.2) <= 3.2


def test_target_keeps_grid_margin_from_actual_peer_position():
    from scripts.visitor_trail import following_target
    trail = VisitorTrail()
    for i in range(13):
        trail.append(i*.5, 0)
    target = following_target(trail, 1, 2.4, {'x': 6, 'y': 0}, others=[{'x': 3.9, 'y': 0}])
    x, y, _ = trail.sample(target)
    assert math.hypot(x-3.9, y) >= 1.15
    assert target >= 1
