import argparse
import json
from .knowledge_store import load
from .qa_engine import answer


def cli():
    parser = argparse.ArgumentParser()
    parser.add_argument('question')
    parser.add_argument('--config', default='config/knowledge.yaml')
    parser.add_argument('--exhibit', default='')
    parser.add_argument('--level', default='basic')
    args = parser.parse_args()
    print(json.dumps(answer(load(args.config), args.question, args.exhibit, args.level), ensure_ascii=False))


def main():
    import rclpy
    from rclpy.node import Node
    from temi_interfaces.srv import AskHeritage
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default='config/knowledge.yaml')
    args, ros_args = parser.parse_known_args()
    kb = load(args.config)
    rclpy.init(args=ros_args)
    node = Node('heritage_knowledge')

    def callback(request, response):
        result = answer(kb, request.question, request.exhibit, request.level or 'basic')
        response.found = result['found']
        response.entry_id = result['entry_id']
        response.answer = result['answer']
        response.source_json = json.dumps(result['source'], ensure_ascii=False)
        return response

    node.create_service(AskHeritage, 'heritage/knowledge/ask', callback)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()
