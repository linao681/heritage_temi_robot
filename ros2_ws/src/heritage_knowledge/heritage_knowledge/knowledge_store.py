from pathlib import Path
from urllib.parse import urlparse
import yaml


def load(path):
    data = yaml.safe_load(Path(path).read_text(encoding='utf-8'))
    ids, exhibits = set(), set()
    for topic in data['topics']:
        exhibit = topic['exhibit']
        if exhibit not in {f'exhibit_{i:02d}' for i in range(1, 6)} or exhibit in exhibits:
            raise ValueError('无效或重复展区')
        exhibits.add(exhibit)
        source = topic['source']
        if not source['name'] or not source['checked'] or urlparse(source['url']).scheme != 'https' or not urlparse(source['url']).netloc:
            raise ValueError('无效来源')
        aliases = topic['aliases']
        if not aliases or not all(isinstance(x, str) and x.strip() for x in aliases):
            raise ValueError('无效主题别名')
        for entry in topic['entries']:
            if entry['id'] in ids or not all(isinstance(entry[k], str) and entry[k].strip() for k in ('id','basic','child','advanced')):
                raise ValueError('无效或重复条目')
            ids.add(entry['id'])
            if not entry['keywords'] or not all(isinstance(x,str) and x.strip() for x in entry['keywords']):
                raise ValueError('无效关键词')
    if len(exhibits) != 5 or not data['version']:
        raise ValueError('知识库缺少展区或版本')
    return data
