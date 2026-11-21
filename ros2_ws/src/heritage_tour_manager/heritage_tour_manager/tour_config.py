"""展区和导览运行参数；只保存地点名称，不虚构真实地图坐标。"""

import math
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Exhibit:
    id: str
    name: str
    temi_location: str
    guide_content: str
    guide_level: str

    def __post_init__(self):
        if not all(isinstance(value, str) and value.strip() for value in (
                self.id, self.name, self.temi_location, self.guide_content, self.guide_level)):
            raise ValueError('展区字段必须为非空字符串')


@dataclass(frozen=True)
class TourConfig:
    route: tuple[Exhibit, ...]
    greeting_text: str = '您好，欢迎来到潮汕非遗文化展厅。您愿意参加导览吗？'
    navigation_timeout_sec: float = 45.0
    speech_timeout_sec: float = 15.0
    communication_timeout_sec: float = 3.0
    consent_timeout_sec: float = 30.0
    qa_timeout_sec: float = 20.0
    low_battery_threshold: float = 20.0
    safe_return_location: str = 'entrance'
    visitor_assist_enabled: bool = False
    visitor_status_timeout_sec: float = 1.0

    def __post_init__(self):
        expected = ['entrance', 'exhibit_01', 'exhibit_02', 'exhibit_03', 'exhibit_04',
                    'exhibit_05', 'interaction_zone', 'exit']
        submission = ['entrance', 'exhibit_01', 'exhibit_02', 'exhibit_03', 'exhibit_04',
                      'interaction_zone', 'exit']
        if [exhibit.id for exhibit in self.route] not in (expected, submission):
            raise ValueError('路线必须符合既有八站或初赛五区配置')
        locations = [exhibit.temi_location for exhibit in self.route]
        if len(set(locations)) != len(locations) or self.safe_return_location not in locations:
            raise ValueError('地点必须唯一，安全返回地点必须在配置中')
        if not self.greeting_text.strip():
            raise ValueError('迎宾文本不能为空')
        for name in ('navigation_timeout_sec', 'speech_timeout_sec', 'communication_timeout_sec',
                     'consent_timeout_sec', 'qa_timeout_sec'):
            value = getattr(self, name)
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f'{name} 必须是有限正数')
        if not 0.0 <= self.low_battery_threshold <= 100.0:
            raise ValueError('低电量阈值必须在 0~100 之间')
        if type(self.visitor_assist_enabled) is not bool:
            raise ValueError('visitor_assist_enabled 必须为布尔值')
        if (type(self.visitor_status_timeout_sec) not in (int, float) or
                not math.isfinite(self.visitor_status_timeout_sec) or self.visitor_status_timeout_sec <= 0):
            raise ValueError('visitor_status_timeout_sec 必须为有限正数')

    @classmethod
    def from_yaml(cls, exhibits_path: str | Path, system_path: str | Path) -> 'TourConfig':
        """读取固定路线及可调运行参数。"""
        with Path(exhibits_path).open(encoding='utf-8') as file:
            route = tuple(Exhibit(**entry) for entry in yaml.safe_load(file)['exhibits'])
        with Path(system_path).open(encoding='utf-8') as file:
            settings = yaml.safe_load(file)['tour']
        return cls(route=route, **settings)
