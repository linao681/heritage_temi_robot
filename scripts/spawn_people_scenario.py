"""Spawn real Gazebo collision models for phase 2 perception scenarios."""
import argparse
import json
import math
from pathlib import Path
import time

import rclpy
from gazebo_msgs.msg import EntityState
from gazebo_msgs.srv import DeleteEntity, SetEntityState, SpawnEntity
from geometry_msgs.msg import Pose
from nav_msgs.msg import Odometry
from rclpy.node import Node

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'phase2_person_'


class PeopleScenario(Node):
    def __init__(self):
        super().__init__('phase2_people_scenario')
        self._spawn = self.create_client(SpawnEntity, '/spawn_entity')
        self._delete = self.create_client(DeleteEntity, '/delete_entity')
        self._set_state = self.create_client(SetEntityState, '/gazebo/set_entity_state')
        self._odom = None
        self.create_subscription(Odometry, '/odom', self._on_odom, 10)

    def _on_odom(self, message):
        self._odom = message

    def current_pose(self):
        deadline = time.monotonic() + 5.0
        while rclpy.ok() and self._odom is None and time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)
        if self._odom is None:
            raise RuntimeError('等待 Gazebo /odom 超时，未生成人员模型')
        pose = self._odom.pose.pose
        q = pose.orientation
        yaw = math.atan2(2.0 * (q.w * q.z + q.x * q.y),
                         1.0 - 2.0 * (q.y * q.y + q.z * q.z))
        return {'x': pose.position.x, 'y': pose.position.y, 'yaw': yaw}

    def _call(self, client, request):
        if not client.wait_for_service(timeout_sec=10.0):
            raise RuntimeError('Gazebo service unavailable')
        future = client.call_async(request)
        rclpy.spin_until_future_complete(self, future, timeout_sec=10.0)
        if not future.done() or future.exception():
            raise RuntimeError('Gazebo service call failed')
        response = future.result()
        if not response.success:
            raise RuntimeError(response.status_message)
        return response

    def clear_existing(self):
        if not self._delete.wait_for_service(timeout_sec=10.0):
            raise RuntimeError('Gazebo delete_entity 服务不可用')
        removed = []
        for index in range(1, 4):
            name = f'{PREFIX}{index:02d}'
            future = self._delete.call_async(DeleteEntity.Request(name=name))
            rclpy.spin_until_future_complete(self, future, timeout_sec=10.0)
            if future.done() and not future.exception() and future.result().success:
                removed.append(name)
        return removed

    def spawn(self, name, x, y, yaw):
        sdf = (ROOT / 'simulation/models/person_mannequin/model.sdf').read_text()
        sdf = sdf.replace('name="person_mannequin"', f'name="{name}"', 1)
        materials = ROOT / 'simulation/models/person_mannequin/materials'
        sdf = sdf.replace('__VISITOR_MATERIALS_URI__', (materials / 'scripts').resolve().as_uri())
        sdf = sdf.replace('__VISITOR_TEXTURES_URI__', (materials / 'textures').resolve().as_uri())
        pose = Pose()
        pose.position.x, pose.position.y = x, y
        pose.orientation.z, pose.orientation.w = math.sin(yaw / 2), math.cos(yaw / 2)
        request = SpawnEntity.Request(name=name, xml=sdf, initial_pose=pose, reference_frame='world')
        self._call(self._spawn, request)
        return {'name': name, 'x': x, 'y': y, 'yaw': yaw}

    def move(self, name, x, y, yaw):
        state = EntityState()
        state.name = name
        state.reference_frame = 'world'
        state.pose.position.x, state.pose.position.y = x, y
        state.pose.orientation.z, state.pose.orientation.w = math.sin(yaw / 2), math.cos(yaw / 2)
        self._call(self._set_state, SetEntityState.Request(state=state))


def scene_positions(scenario, wait):
    x, y = wait['x'], wait['y']
    yaw = wait.get('yaw', 0.0)
    forward_x, forward_y = math.cos(yaw), math.sin(yaw)
    left_x, left_y = -forward_y, forward_x
    if scenario == 'single':
        return [(x + 3.0 * forward_x, y + 3.0 * forward_y, yaw + math.pi)]
    if scenario == 'group':
        return [(x + 3.2 * forward_x + dy * left_x,
                 y + 3.2 * forward_y + dy * left_y, yaw + math.pi)
                for dy in (-0.75, 0.0, 0.75)]
    if scenario == 'near':
        return [(x + 1.05 * forward_x, y + 1.05 * forward_y, yaw + math.pi)]
    if scenario == 'crossing':
        return [(x + 2.4 * forward_x - 1.2 * left_x,
                 y + 2.4 * forward_y - 1.2 * left_y, yaw + math.pi / 2)]
    return []


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--layout', choices=('official', 'adaptive'), default='official')
    parser.add_argument('--scenario', choices=('empty', 'single', 'group', 'near', 'crossing', 'clear'), required=True)
    parser.add_argument('--duration-sec', type=float, default=8.0)
    parser.add_argument('--truth-output', type=Path)
    args = parser.parse_args()
    if not math.isfinite(args.duration_sec) or args.duration_sec <= 0:
        parser.error('--duration-sec must be a finite positive number')

    goals = json.loads((ROOT / 'simulation/generated' / f'{args.layout}_goals.json').read_text())['goals']
    wait = goals['wait']
    rclpy.init(args=None)
    node = PeopleScenario()
    timestamp = time.strftime('%Y%m%d-%H%M%S')
    output = args.truth_output or ROOT / 'docs/runs/phase2-20261121' / f'person_scenario_{args.scenario}_{timestamp}.json'
    started = time.time()
    try:
        removed = node.clear_existing()
        robot_pose = node.current_pose()
        positions = scene_positions(args.scenario, robot_pose)
        models = [node.spawn(f'{PREFIX}{index + 1:02d}', *pose)
                  for index, pose in enumerate(positions)]
        path = []
        if args.scenario == 'crossing' and models:
            model = models[0]
            end = time.monotonic() + args.duration_sec
            while time.monotonic() < end:
                progress = 1.0 - (end - time.monotonic()) / args.duration_sec
                x = model['x'] - 2.4 * math.sin(robot_pose['yaw']) * progress
                y = model['y'] + 2.4 * math.cos(robot_pose['yaw']) * progress
                node.move(model['name'], x, y, model['yaw'])
                path.append({'elapsed_sec': time.time() - started, 'x': x, 'y': y})
                time.sleep(0.2)
        record = {
            'scenario': args.scenario, 'layout': args.layout, 'source': 'gazebo_spawn_entity_and_set_entity_state',
            'started_unix_sec': started, 'duration_sec': time.time() - started,
            'removed_previous_models': removed, 'commanded_model_poses_world': models,
            'robot_pose_world_at_spawn': robot_pose,
            'crossing_pose_samples': path,
            'model_asset': 'simulation/models/person_mannequin/model.sdf',
            'ground_truth_note': '记录 Gazebo 世界坐标中的模型中心指令位置；不是 YOLOX 检测结果。',
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps(record, ensure_ascii=False))
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
