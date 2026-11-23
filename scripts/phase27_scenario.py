"""Pure phase 2.7 actor-motion and conservative swept-geometry helpers."""

import math
from pathlib import Path
import xml.etree.ElementTree as ET


def _finite_number(value, name, minimum=None, strict_minimum=False):
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f'{name} must be a finite number') from error
    if not math.isfinite(number):
        raise ValueError(f'{name} must be a finite number')
    if minimum is not None and (number <= minimum if strict_minimum else number < minimum):
        relation = 'greater than' if strict_minimum else 'at least'
        raise ValueError(f'{name} must be {relation} {minimum}')
    return number


def _anchor_pose(anchor):
    if isinstance(anchor, dict):
        pose = (anchor.get('x'), anchor.get('y'), anchor.get('yaw', 0.0))
    else:
        pose = tuple(anchor)
    if len(pose) != 3:
        raise ValueError('anchor must contain x, y, yaw')
    return tuple(_finite_number(value, f'anchor[{index}]')
                 for index, value in enumerate(pose))


def actor_step(config, elapsed_sec, anchor):
    """Return one actor phase and world pose; inputs are seconds and metres.

    The anchor is fixed at approach start. Robot stop state is deliberately not
    an input, so an operator stop event cannot silently freeze the actor path.
    """
    elapsed = _finite_number(elapsed_sec, 'elapsed_sec', 0.0)
    x, y, yaw = _anchor_pose(anchor)
    speed = _finite_number(config.get('speed_mps'), 'speed_mps', 0.0, True)
    start_distance = _finite_number(config.get('start_distance_m', 4.5),
                                    'start_distance_m', 0.0, True)
    target_distance = _finite_number(config.get('target_distance_m', 0.6),
                                     'target_distance_m', 0.0)
    if target_distance >= start_distance:
        raise ValueError('target_distance_m must be less than start_distance_m')
    hold_target = _finite_number(config.get('hold_at_target_sec', 0.0),
                                 'hold_at_target_sec', 0.0)
    leave_enabled = bool(config.get('leave_after_hold', False))
    leave_direction = config.get('leave_direction', 'forward')
    if leave_direction not in ('forward', 'left', 'right'):
        raise ValueError('leave_direction must be forward, left, or right')
    leave_distance = _finite_number(config.get('leave_distance_m', 0.0),
                                    'leave_distance_m', 0.0)
    hold_clear = _finite_number(config.get('hold_clear_sec', 0.0),
                                'hold_clear_sec', 0.0)

    forward_x, forward_y = math.cos(yaw), math.sin(yaw)
    left_x, left_y = -forward_y, forward_x
    approach_distance = start_distance - target_distance
    approach_duration = approach_distance / speed
    lateral_distance = 0.0
    if elapsed < approach_duration:
        distance = start_distance - speed * elapsed
        phase = 'APPROACH'
        finished = False
    else:
        since_target = elapsed - approach_duration
        if since_target < hold_target:
            distance = target_distance
            phase = 'HOLD_TARGET'
            finished = False
        elif not leave_enabled:
            distance = target_distance
            phase = 'HOLD_TARGET'
            finished = since_target >= hold_target
        else:
            since_leave = since_target - hold_target
            leave_duration = leave_distance / speed if leave_distance else 0.0
            if since_leave < leave_duration:
                travelled = speed * since_leave
                if leave_direction == 'forward':
                    distance = target_distance + travelled
                else:
                    distance = target_distance
                    lateral_distance = travelled * (1.0 if leave_direction == 'left' else -1.0)
                phase = 'LEAVE'
                finished = False
            else:
                if leave_direction == 'forward':
                    distance = target_distance + leave_distance
                else:
                    distance = target_distance
                    lateral_distance = leave_distance * (1.0 if leave_direction == 'left' else -1.0)
                phase = 'HOLD_CLEAR'
                finished = since_leave - leave_duration >= hold_clear

    pose = (x + forward_x * distance + left_x * lateral_distance,
            y + forward_y * distance + left_y * lateral_distance, yaw + math.pi)
    return {'phase': phase, 'pose': pose, 'finished': finished}


def crossing_step(config, elapsed_sec, anchor):
    """Move a crossing actor on a time-based path independent of robot stop state."""
    elapsed = _finite_number(elapsed_sec, 'elapsed_sec', 0.0)
    x, y, yaw = _anchor_pose(anchor)
    speed = _finite_number(config.get('speed_mps'), 'speed_mps', 0.0, True)
    forward_distance = _finite_number(config.get('forward_distance_m'),
                                       'forward_distance_m', 0.0, True)
    start_lateral = _finite_number(config.get('start_lateral_m'), 'start_lateral_m')
    end_lateral = _finite_number(config.get('end_lateral_m'), 'end_lateral_m')
    if math.isclose(start_lateral, end_lateral, abs_tol=1e-9):
        raise ValueError('crossing path must have non-zero lateral distance')
    hold_clear = _finite_number(config.get('hold_clear_sec', 0.0),
                                'hold_clear_sec', 0.0)
    distance = abs(end_lateral - start_lateral)
    duration = distance / speed
    progress = min(1.0, elapsed / duration)
    lateral = start_lateral + (end_lateral - start_lateral) * progress
    forward_x, forward_y = math.cos(yaw), math.sin(yaw)
    left_x, left_y = -forward_y, forward_x
    pose = (x + forward_x * forward_distance + left_x * lateral,
            y + forward_y * forward_distance + left_y * lateral,
            yaw + math.pi)
    finished = elapsed >= duration + hold_clear
    return {'phase': 'CROSSING' if progress < 1.0 else 'HOLD_CLEAR',
            'pose': pose, 'finished': finished}


def _xy(pose):
    if isinstance(pose, dict):
        x, y = pose.get('x'), pose.get('y')
    else:
        x, y = pose[0], pose[1]
    return (_finite_number(x, 'pose.x'), _finite_number(y, 'pose.y'))


def swept_gap(previous_pose, next_pose, robot_pose, envelope):
    """Conservative swept circle gap in metres for actor/robot motion.

    Collision shapes are enclosed by circumscribed circles. `robot_pose` can be
    one pose or {'previous': pose, 'current': pose}; linear relative motion
    between sampled endpoints is checked. This is a risk bound, not contact
    sensing or a physical collision certification.
    """
    actor_before = _xy(previous_pose)
    actor_after = _xy(next_pose)
    if isinstance(robot_pose, dict) and 'previous' in robot_pose:
        robot_before = _xy(robot_pose['previous'])
        robot_after = _xy(robot_pose.get('current', robot_pose['previous']))
    else:
        robot_before = robot_after = _xy(robot_pose)
    robot_radius = _finite_number(envelope.get('robot_radius_m'),
                                  'robot_radius_m', 0.0)
    actor_radius = _finite_number(envelope.get('actor_radius_m'),
                                  'actor_radius_m', 0.0)
    margin = _finite_number(envelope.get('margin_m', 0.0), 'margin_m', 0.0)

    relative_before = (actor_before[0] - robot_before[0], actor_before[1] - robot_before[1])
    relative_after = (actor_after[0] - robot_after[0], actor_after[1] - robot_after[1])
    delta = (relative_after[0] - relative_before[0],
             relative_after[1] - relative_before[1])
    length_squared = delta[0] ** 2 + delta[1] ** 2
    progress = 0.0 if length_squared == 0.0 else max(
        0.0, min(1.0, -(relative_before[0] * delta[0] +
                        relative_before[1] * delta[1]) / length_squared))
    closest = (relative_before[0] + progress * delta[0],
               relative_before[1] + progress * delta[1])
    return math.hypot(*closest) - robot_radius - actor_radius - margin


def _shape_radius(geometry, kind):
    if kind == 'urdf':
        box = geometry.find('box')
        sphere = geometry.find('sphere')
        cylinder = geometry.find('cylinder')
        if box is not None:
            x, y, _ = map(float, box.attrib['size'].split())
            return math.hypot(x / 2.0, y / 2.0)
        if sphere is not None:
            return float(sphere.attrib['radius'])
        if cylinder is not None:
            return max(float(cylinder.attrib['radius']), float(cylinder.attrib['length']) / 2.0)
    else:
        box = geometry.find('box/size')
        sphere = geometry.find('sphere/radius')
        cylinder = geometry.find('cylinder')
        if box is not None:
            x, y, _ = map(float, (box.text or '').split())
            return math.hypot(x / 2.0, y / 2.0)
        if sphere is not None:
            return float(sphere.text)
        if cylinder is not None:
            return max(float(cylinder.findtext('radius')),
                       float(cylinder.findtext('length')) / 2.0)
    raise ValueError('unsupported collision geometry; cannot derive a conservative envelope')


def _translation_xy(text):
    if not text:
        return 0.0
    values = tuple(map(float, text.split()))
    return math.hypot(values[0], values[1])


def collision_envelopes(robot_urdf, actor_sdf):
    """Read collision geometry and derive conservative XY circumscribed radii."""
    robot_path = Path(robot_urdf).resolve()
    actor_path = Path(actor_sdf).resolve()
    robot_root = ET.parse(robot_path).getroot()
    actor_root = ET.parse(actor_path).getroot()

    link_offsets = {'base_link': 0.0}
    joints = list(robot_root.findall('joint'))
    changed = True
    while changed:
        changed = False
        for joint in joints:
            parent = joint.find('parent')
            child = joint.find('child')
            origin = joint.find('origin')
            if parent is None or child is None or parent.attrib['link'] not in link_offsets:
                continue
            child_name = child.attrib['link']
            candidate = (link_offsets[parent.attrib['link']] +
                         _translation_xy(None if origin is None else origin.attrib.get('xyz')))
            if candidate < link_offsets.get(child_name, math.inf):
                link_offsets[child_name] = candidate
                changed = True

    robot_radius = 0.0
    for link in robot_root.findall('link'):
        link_radius = link_offsets.get(link.attrib['name'])
        if link_radius is None:
            continue
        for collision in link.findall('collision'):
            origin = collision.find('origin')
            offset = 0.0 if origin is None else _translation_xy(origin.attrib.get('xyz'))
            geometry = collision.find('geometry')
            if geometry is None:
                raise ValueError('URDF collision has no geometry')
            robot_radius = max(robot_radius, link_radius + offset +
                               _shape_radius(geometry, 'urdf'))

    actor_radius = 0.0
    for collision in actor_root.findall('.//collision'):
        geometry = collision.find('geometry')
        pose = collision.findtext('pose')
        offset = _translation_xy(None if not pose else ' '.join(pose.split()[:2]))
        if geometry is None:
            raise ValueError('SDF collision has no geometry')
        actor_radius = max(actor_radius, offset + _shape_radius(geometry, 'sdf'))

    if robot_radius <= 0.0 or actor_radius <= 0.0:
        raise ValueError('collision envelope could not be derived from URDF/SDF')
    source = {
        'robot': str(robot_path),
        'actor': str(actor_path),
        'assumption': 'XY circumscribed collision circles; conservative geometry proxy, not contact sensing',
    }
    return robot_radius, actor_radius, source
