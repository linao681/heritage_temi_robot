def test_five_zones_in_submission_order_then_exit():
    from scripts.check_nav2 import route_keys, ZONE_NAMES
    assert route_keys(True) == ['zone_1', 'zone_2', 'zone_3', 'zone_4', 'zone_5', 'exit']
    assert route_keys(False) == ['zone_1']
    assert ZONE_NAMES == ['非遗概览', '传统工艺', '代表作品', '传承故事', '互动体验']
