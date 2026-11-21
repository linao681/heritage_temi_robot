from pathlib import Path
import pytest
from heritage_knowledge.knowledge_store import load
from heritage_knowledge.qa_engine import answer

ROOT = Path(__file__).resolve().parents[1]

@pytest.fixture
def kb():
    return load(ROOT / 'config/knowledge.yaml')

@pytest.mark.parametrize('question,expected',[('潮绣有什么特点','embroidery_features'),('潮州木雕用在哪里','wood_usage'),('工夫茶用什么茶','tea_leaf'),('潮剧用什么语言','opera_language'),('潮州音乐有哪些类型','music_types')])
def test_known(kb, question, expected):
    result = answer(kb, question)
    assert result['found'] and result['entry_id'] == expected and result['source']['url'].startswith('https://')

@pytest.mark.parametrize('question',['今天下雨吗','潮绣多少钱','潮剧和潮绣有什么特点','','潮剧什么时候发明机器人'])
def test_refusal(kb,question):
    assert not answer(kb,question)['found']

def test_context_and_level(kb):
    assert answer(kb,'有什么特点','exhibit_01')['found']
    assert answer(kb,'潮绣有什么特点',level='advanced')['found']
    assert not answer(kb,'潮绣有什么特点','exhibit_02')['found']
    assert not answer(kb,'潮绣有什么特点',level='invalid')['found']

@pytest.mark.parametrize('question,expected', [
    ('潮州刺绣发源地','embroidery_region'),('潮绣哪年入选','embroidery_list'),
    ('潮州木雕的历史','wood_history'),('潮州木雕的构图','wood_composition'),
    ('功夫茶怎么泡','tea_steps'),('工夫茶国家级非遗名录','tea_list'),
    ('潮州戏的起源','opera_origin'),('潮音戏有哪些剧目','opera_works'),
    ('潮汕音乐的历史','music_origin'),('潮州音乐哪年入选','music_list')])
def test_other_intents(kb,question,expected):
    assert answer(kb,question)['entry_id']==expected

def test_service_roundtrip(monkeypatch, tmp_path):
    import json
    import os
    import subprocess
    import time
    import rclpy
    from temi_interfaces.srv import AskHeritage
    monkeypatch.setenv('ROS_LOCALHOST_ONLY','1')
    monkeypatch.setenv('ROS_DOMAIN_ID','219')
    monkeypatch.setenv('ROS_LOG_DIR',str(tmp_path))
    exe=ROOT/'ros2_ws/install/heritage_knowledge/lib/heritage_knowledge/knowledge_node'
    with (tmp_path/'node.log').open('w') as log:
        proc=subprocess.Popen([str(exe),'--config',str(ROOT/'config/knowledge.yaml')], stdout=log, stderr=subprocess.STDOUT,env=os.environ.copy())
        rclpy.init(args=[])
        node=rclpy.create_node('qa_test_client')
        client=node.create_client(AskHeritage,'heritage/knowledge/ask')
        try:
            assert client.wait_for_service(timeout_sec=5)
            for question,found in [('潮剧用什么语言',True),('明天的天气',False)]:
                future=client.call_async(AskHeritage.Request(question=question,level='basic'))
                rclpy.spin_until_future_complete(node,future,timeout_sec=5)
                result=future.result()
                assert result is not None and result.found==found
                assert bool(json.loads(result.source_json))==found
        finally:
            node.destroy_node()
            rclpy.try_shutdown()
            proc.terminate()
            proc.wait(timeout=5)
