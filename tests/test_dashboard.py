import pytest
from heritage_dashboard.model import DashboardModel


def robot(frame='mock_map', connected=True, moving=False):
    return {'connected': connected, 'frame_id': frame, 'is_moving': moving,
            'battery_percentage': 80, 'x': 1.0, 'y': 2.0, 'current_location': 'entrance'}


def tour(state='NAVIGATING', **extra):
    return {'state': state, 'outcome': 'running', 'visited': ['entrance'], 'target': 'exhibit_01', **extra}


def test_stale_and_missing_data_not_presented_as_current():
    m = DashboardModel(timeout=1)
    assert m.snapshot(0)['robot'] is None
    m.update('robot', robot(), 1)
    assert m.snapshot(1.5)['robot']['battery_percentage'] == 80
    assert m.snapshot(2.1)['robot'] is None


def test_default_read_only_and_explicit_mock_control():
    m = DashboardModel()
    m.update('robot', robot(), 1)
    m.update('tour', tour(), 1)
    assert m.commands(1) == set()
    m = DashboardModel(controls=True)
    m.update('robot', robot(), 1)
    m.update('tour', tour(), 1)
    assert m.commands(1) == {'pause', 'cancel', 'manual_takeover'}
    assert not m.commands(5)


@pytest.mark.parametrize('data',[robot(frame='temi_sdk_unverified'),robot(connected=False), {'connected':True}, robot(frame='')])
def test_unknown_or_real_robot_cannot_control(data):
    m = DashboardModel(controls=True)
    m.update('robot', data, 1)
    m.update('tour', tour(), 1)
    assert not m.commands(1)


def test_paused_resume_requires_stationary_and_assist_guard():
    m = DashboardModel(controls=True)
    m.update('robot', robot(), 1)
    m.update('tour', tour('PAUSED',visitor_assist={'active':True,'can_resume':False}), 1)
    assert 'resume' not in m.commands(1)
    m.update('tour', tour('PAUSED',visitor_assist={'active':True,'can_resume':True}), 1)
    assert 'resume' in m.commands(1)
    m.update('robot', robot(moving=True), 1)
    assert 'resume' not in m.commands(1)


def test_invalid_topic_does_not_keep_previous_fresh_state():
    m = DashboardModel(controls=True)
    m.update('robot', robot(), 1)
    m.update('tour', tour(), 1)
    m.update('tour', {'state': 'NAVIGATING'}, 1.1)
    assert m.snapshot(1.1)['tour'] is None and not m.commands(1.1)


@pytest.mark.parametrize('data',[tour(state=[]),tour(history=None),tour(qa_result='invalid'),tour(qa_result={'source':[]} )])
def test_malformed_tour_values_do_not_crash_dashboard(data):
    m=DashboardModel(controls=True)
    m.update('tour',data,1)
    assert m.snapshot(1)['tour'] is None
