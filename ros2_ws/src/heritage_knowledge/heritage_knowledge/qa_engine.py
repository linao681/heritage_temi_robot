import re
import unicodedata


def normalize(text):
    return re.sub(r'[\W_]+', '', unicodedata.normalize('NFKC', text)).lower()


def answer(kb, question, exhibit='', level='basic'):
    refusal = {'found': False, 'entry_id': '', 'answer': '暂未找到可靠资料，请向工作人员咨询或明确非遗主题。', 'source': {}}
    if not isinstance(question, str) or len(question) > 256 or level not in ('basic','child','advanced'):
        return refusal
    query = normalize(question)
    if not query or any(w in query for w in ('多少钱','价格','天气','机器人','门票','地址','电话号码')):
        return refusal
    topics = [t for t in kb['topics'] if any(normalize(a) in query for a in t['aliases'])]
    if len(topics) > 1 or (topics and exhibit and topics[0]['exhibit'] != exhibit):
        return refusal
    if not topics and exhibit:
        topics = [t for t in kb['topics'] if t['exhibit'] == exhibit]
    if len(topics) != 1:
        return refusal
    topic = topics[0]
    matches = [e for e in topic['entries'] if any(normalize(k) in query for k in e['keywords'])]
    if len(matches) != 1:
        return refusal
    entry = matches[0]
    return {'found': True, 'entry_id': entry['id'], 'answer': entry[level], 'source': dict(topic['source'])}
