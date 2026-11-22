"""Three visitors follow Gazebo robot history; this is scripted actor behavior.

An explicit scripted reception path forms the initial queue. Subsequent trail
points come from robot history. No camera observations are synthesized.
"""
import argparse
from functools import lru_cache
import heapq
import json
import math
import os
from pathlib import Path
import time

import rclpy
from std_msgs.msg import String
from std_srvs.srv import Trigger
from spawn_people_scenario import PeopleScenario, ROOT
from visitor_trail import VisitorTrail, advance, following_target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--duration-sec', type=float, default=1200)
    args = parser.parse_args()
    if os.environ.get('ROS_LOCALHOST_ONLY') != '1':
        parser.error('requires ROS_LOCALHOST_ONLY=1')
    if not math.isfinite(args.duration_sec) or not 0 < args.duration_sec <= 3600:
        parser.error('duration must be in (0,3600]')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    rclpy.init()
    node = PeopleScenario()
    trail = VisitorTrail()
    members = []
    tour = {}
    slow = False
    pause_sent = False
    pause_future = None
    publisher = node.create_publisher(String, 'heritage/simulation/team_status', 10)
    lost = node.create_client(Trigger, 'heritage/tour/visitor_lost')

    def receive(message):
        nonlocal tour
        tour = json.loads(message.data)
    node.create_subscription(String, 'heritage/tour/status', receive, 10)

    def straggle(request, response):
        nonlocal slow
        slow = True
        response.success = bool(members)
        response.message = '队尾游客放慢脚步' if members else '等待队伍形成'
        return response

    def gather(request, response):
        nonlocal slow
        slow = False
        response.success = bool(members)
        response.message = '游客追赶队伍，机器人仍需人工确认继续'
        return response
    node.create_service(Trigger, 'heritage/simulation/team/straggle', straggle)
    node.create_service(Trigger, 'heritage/simulation/team/gather', gather)
    # Static collision map is used for every actor step, including corners.
    import yaml
    from PIL import Image
    metadata = yaml.safe_load((ROOT/'simulation/generated/official.yaml').read_text())
    image = Image.open(ROOT/'simulation/generated'/metadata['image']).convert('L')
    resolution = metadata['resolution']
    ox, oy, _ = metadata['origin']

    @lru_cache(maxsize=50000)
    def free_cell(cx, cy):
        radius = math.ceil(.35/resolution)
        for dx in range(-radius, radius+1):
            for dy in range(-radius, radius+1):
                if dx*dx+dy*dy > radius*radius:
                    continue
                px, py = cx+dx, cy+dy
                if not (0 <= px < image.width and 0 <= py < image.height) or image.getpixel((px, py)) < 250:
                    return False
        return True

    def free(x, y):
        return free_cell(int((x-ox)/resolution), image.height-1-int((y-oy)/resolution))

    def walking_step(start, target, distance, robot, others, member):
        # Grid search handles reception joining around fixtures; final movement
        # remains bounded by each visitor's independent walking speed.
        step = .2
        def cell(x, y):
            return round((x-ox)/step), round((y-oy)/step)
        def point(c):
            return ox+c[0]*step, oy+c[1]*step
        begin, end = cell(start['x'], start['y']), cell(*target[:2])
        start_clearance = math.hypot(start['x']-robot['x'], start['y']-robot['y'])
        def allowed(c):
            x, y = point(c)
            return (free(x, y) and math.hypot(x-robot['x'], y-robot['y']) >= min(1.8, start_clearance) and
                    all(p is not None and math.hypot(x-p['x'], y-p['y']) >= .9 for p in others))
        path = member.get('joining_path', [])
        if path:
            while path and math.hypot(path[0][0]-start['x'], path[0][1]-start['y']) < .04:
                path.pop(0)
            if path and allowed(cell(*path[0])):
                x, y = path[0]
                dx, dy = x-start['x'], y-start['y']
                length = math.hypot(dx, dy)
                ratio = min(1, distance/length)
                return start['x']+ratio*dx, start['y']+ratio*dy, math.atan2(dy, dx)
            member['joining_path'] = []
        queue, costs, parents = [(0, begin)], {begin: 0}, {}
        found = None
        for _ in range(6000):
            if not queue:
                break
            _, current = heapq.heappop(queue)
            if current == end:
                found = current
                break
            for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
                nxt = current[0]+dx, current[1]+dy
                cost = costs[current]+1
                cx, cy = point(current)
                nx, ny = point(nxt)
                current_clearance = math.hypot(cx-robot['x'], cy-robot['y'])
                if current_clearance < 1.8 and math.hypot(nx-robot['x'], ny-robot['y']) < current_clearance:
                    continue
                if cost >= costs.get(nxt, math.inf) or not allowed(nxt):
                    continue
                parents[nxt], costs[nxt] = current, cost
                heapq.heappush(queue, (cost+abs(nxt[0]-end[0])+abs(nxt[1]-end[1]), nxt))
        if found is None:
            return None
        path = [target[:2]]
        waypoint = found
        while waypoint != begin:
            path.append(point(waypoint))
            waypoint = parents[waypoint]
        member['joining_path'] = list(reversed(path))
        while parents.get(found) not in (None, begin):
            found = parents[found]
        x, y = target[:2] if found == end else point(found)
        dx, dy = x-start['x'], y-start['y']
        length = math.hypot(dx, dy)
        if length < .01:
            return start['x'], start['y'], target[2]
        ratio = min(1, distance/length)
        return start['x']+ratio*dx, start['y']+ratio*dy, math.atan2(dy, dx)

    started, previous = time.monotonic(), time.monotonic()
    try:
        with args.output.open('x', encoding='utf-8') as evidence:
            while rclpy.ok() and time.monotonic()-started < args.duration_sec:
                rclpy.spin_once(node, timeout_sec=.05)
                now = time.monotonic()
                dt, previous = min(now-previous, .2), now
                robot = node.model_pose('heritage_robot')
                if robot is None:
                    publisher.publish(String(data=json.dumps({'valid': False, 'state': 'STALE'})))
                    continue
                if not trail.points:
                    # Reception formation path ends at the waiting robot. This
                    # prefix is scripted staging, not recorded robot travel.
                    for i in range(13):
                        trail.append(robot['x']+6.0-i*.5, robot['y'])
                trail.append(robot['x'], robot['y'])
                if not members:
                    poses = [(robot['x']+3.2, robot['y']+offset, math.pi) for offset in (-1.1, 0, 1.1)]
                    if not all(free(x, y) for x, y, _ in poses):
                        continue
                    names = [f'phase25_person_{i:02d}' for i in (6, 7, 8)]
                    if any(node.model_pose(name) is not None for name in names):
                        raise RuntimeError('team model names already in use')
                    for name, gap, pose in zip(names, (2.4, 3.5, 4.6), poses):
                        node.spawn(name, *pose)
                        members.append({'id': name, 'progress': trail.length-gap, 'gap': gap, 'joined': False})
                blocked = False
                for index, member in enumerate(members):
                    if tour.get('state') not in ('IDLE', 'WAITING_CONSENT', 'NAVIGATING', 'RETURNING', 'PAUSED', 'EXPLAINING', 'QA'):
                        continue
                    # At a tight turn arc distance alone can place a nominal
                    # following target inside the robot's clearance circle.
                    others = [node.model_pose(m['id']) for m in members if m is not member]
                    target = following_target(trail, member['progress'], member['gap'], robot,
                                              members[index-1]['progress'] if index else None, others)
                    member['target_progress'] = target
                    next_progress = advance(member['progress'], target, .04 if slow and index == 2 else .85, dt)
                    pose = trail.sample(next_progress)
                    observed = node.wait_for_model_pose(member['id'], timeout_sec=2.0)
                    others = [node.model_pose(m['id']) for m in members if m is not member]
                    clearance = math.hypot(observed['x']-robot['x'], observed['y']-robot['y'])
                    if member.get('yielding') or clearance < 1.8:
                        member['yielding'] = clearance < 2.2
                        if member['yielding']:
                            blocked = True
                            candidates = []
                            away = math.atan2(observed['y']-robot['y'], observed['x']-robot['x'])
                            for offset in (0, .35, -.35, .7, -.7, 1.05, -1.05, 1.4, -1.4):
                                yaw = away+offset
                                x, y = observed['x']+.85*dt*math.cos(yaw), observed['y']+.85*dt*math.sin(yaw)
                                if (free(x,y) and math.hypot(x-robot['x'], y-robot['y']) > clearance and
                                        all(p is not None and math.hypot(x-p['x'], y-p['y']) >= .9 for p in others)):
                                    candidates.append((math.hypot(x-robot['x'], y-robot['y']), x,y,yaw))
                            if candidates:
                                _, x,y,yaw = max(candidates)
                                node.move(member['id'],x,y,yaw)
                                member['detouring'] = True
                                member['joining_path'] = []
                            continue
                    if not member['joined']:
                        if target < 0:
                            continue
                        formation = trail.sample(member['progress'])
                        pose = walking_step(observed, formation, .85*dt, robot, others, member)
                        if pose is None:
                            blocked = True
                            continue
                        robot = node.current_pose()
                        if math.hypot(pose[0]-robot['x'], pose[1]-robot['y']) < 1.8:
                            blocked = True
                            continue
                        node.move(member['id'], *pose)
                        member['joined'] = math.hypot(pose[0]-formation[0], pose[1]-formation[1]) < .12
                        if member['joined']:
                            member['joining_path'] = []
                        continue
                    if (member.get('detouring') or math.hypot(pose[0]-observed['x'],pose[1]-observed['y']) > .85*dt+.025 or
                            not free(*pose[:2]) or math.hypot(pose[0]-robot['x'], pose[1]-robot['y']) < 1.8 or
                            any(p is None or math.hypot(pose[0]-p['x'], pose[1]-p['y']) < .9 for p in others)):
                        blocked = True
                        member['detouring'] = True
                        destination = trail.sample(max(member['progress'], target))
                        detour = walking_step(observed, destination, .85*dt, robot, others, member)
                        if detour is not None:
                            robot = node.current_pose()
                            clearance = math.hypot(observed['x']-robot['x'], observed['y']-robot['y'])
                            if math.hypot(detour[0]-robot['x'], detour[1]-robot['y']) >= min(1.8, clearance):
                                node.move(member['id'], *detour)
                                if math.hypot(detour[0]-destination[0], detour[1]-destination[1]) < .12:
                                    member['progress'] = max(member['progress'], target)
                                    member['joining_path'] = []
                                    member['detouring'] = False
                        continue
                    node.move(member['id'], *pose)
                    member['progress'] = next_progress
                lag = max((max(0, m.get('target_progress', m['progress'])-m['progress']) for m in members), default=0)
                joined = bool(members) and all(m['joined'] for m in members)
                if joined and lag > 1.5 and not pause_sent and lost.service_is_ready():
                    pause_future = lost.call_async(Trigger.Request())
                    pause_sent = True
                if pause_future is not None and pause_future.done():
                    if not pause_future.result().success:
                        pause_sent = False
                    pause_future = None
                actual = [node.model_pose(m['id']) for m in members]
                safe_hold = (joined and all(p is not None and 1.8 <= math.hypot(p['x']-robot['x'],p['y']-robot['y']) <= 7 for p in actual) and
                             all(math.hypot(a['x']-b['x'],a['y']-b['y']) >= .9 for i,a in enumerate(actual) for b in actual[i+1:]))
                gathered = joined and lag < .35 and not slow and (not blocked or safe_hold)
                if gathered and tour.get('state') in ('NAVIGATING', 'RETURNING'):
                    pause_sent = False
                status = {'valid': True, 'source': 'gazebo_scripted_actors',
                          'state': 'RECEPTION' if not joined else 'LOST' if lag > 1.5 else 'GATHERED' if gathered else 'FOLLOWING',
                          'count': len(members), 'lag_m': lag, 'gathered': gathered,
                          'blocked': blocked, 'members': [dict(m) for m in members],
                          'safe_hold': safe_hold,
                          'tour_state': tour.get('state'), 'time_monotonic_sec': now}
                publisher.publish(String(data=json.dumps(status)))
                evidence.write(json.dumps(status)+'\n')
                evidence.flush()
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
