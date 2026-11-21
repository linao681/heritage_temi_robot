from scripts.route_status import fresh_status


def test_route_status_expiry_and_validation():
    value = {'state': 'NAVIGATING', 'name': '非遗概览', 'index': 1, 'total': 6, 'extra': 'ignored'}
    assert fresh_status(value, 10, 12) == {
        'state': 'NAVIGATING', 'name': '非遗概览', 'index': 1, 'total': 6, 'error': None}
    assert fresh_status(value, 10, 14) is None
    assert fresh_status({'state': 'unknown'}, 10, 11) is None
