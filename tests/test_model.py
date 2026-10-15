"""Kiểm thử năm chức năng và đúng hai khác biệt cố ý giữa v0/v1."""

from dataclasses import FrozenInstanceError, fields

import pytest

from smartlock.model import (
    EVENTS, INITIAL_STATE, VERSIONS, InvalidEvent, State, labels, step, successors,
)


@pytest.fixture(params=VERSIONS)
def version(request):
    return request.param


def follow(events, version="v1"):
    state = INITIAL_STATE
    for event in events:
        state = step(state, event, version)
    return state


def test_state_has_exactly_six_fields_and_is_immutable():
    assert [field.name for field in fields(State)] == [
        "authenticated", "failed_attempts", "door_open", "alarm",
        "phase", "admin_authorized",
    ]
    assert State() == INITIAL_STATE
    with pytest.raises(FrozenInstanceError):
        INITIAL_STATE.door_open = True
    # Mỗi biến tham gia nhận diện, không cần tên s0/s1 để so sánh.
    distinct = [INITIAL_STATE, State(authenticated=True), State(failed_attempts=1),
                State(door_open=True), State(alarm=True), State(phase="resetting"),
                State(admin_authorized=True)]
    assert len(set(distinct)) == 7


@pytest.mark.parametrize("changes", [
    {"failed_attempts": -1}, {"failed_attempts": 4}, {"failed_attempts": True},
    {"failed_attempts": 1.5}, {"authenticated": 1}, {"door_open": "yes"},
    {"alarm": None}, {"admin_authorized": 0}, {"phase": "unknown"},
])
def test_state_rejects_values_outside_finite_domains(changes):
    with pytest.raises(ValueError):
        State(**changes)


def test_labels_do_not_hide_invalid_business_states():
    assert labels(INITIAL_STATE) == {"idle"}
    assert labels(State(phase="locked_out", failed_attempts=2)) == {"locked_out"}
    assert labels(State(failed_attempts=3)) == {"attempts_eq_3"}
    assert labels(State(phase="resetting")) == {"resetting"}
    assert labels(State(admin_authorized=True)) == {"admin_authorized"}
    assert labels(State(door_open=True, alarm=True)) == {"door_open", "alarm"}


def test_password_ok_authenticates_and_clears_failures(version):
    state = follow(["password_bad", "password_bad", "password_ok"], version)
    assert state.authenticated
    assert state.failed_attempts == 0
    assert state.phase == "normal"
    assert not state.admin_authorized


def test_third_consecutive_bad_password_causes_lockout(version):
    state = INITIAL_STATE
    for attempt in (1, 2, 3):
        state = step(state, "password_bad", version)
        assert state.failed_attempts == attempt
        assert not state.authenticated
        assert state.phase == ("locked_out" if attempt == 3 else "normal")
    assert {"locked_out", "attempts_eq_3"} <= labels(state)


def test_success_breaks_consecutive_failure_sequence(version):
    state = follow([
        "password_bad", "password_bad", "password_ok", "open_door",
        "close_door", "password_bad",
    ], version)
    assert state.failed_attempts == 1
    assert state.phase == "normal"


def test_wait_does_not_clear_consecutive_failures(version):
    state = follow(["password_bad", "wait", "password_bad", "wait", "password_bad"], version)
    assert state.failed_attempts == 3
    assert state.phase == "locked_out"


@pytest.mark.parametrize("event", ["password_ok", "password_bad", "open_door"])
def test_lockout_rejects_login_and_door_opening(version, event):
    locked = follow(["password_bad"] * 3, version)
    with pytest.raises(InvalidEvent):
        step(locked, event, version)
    assert locked.failed_attempts == 3
    assert not locked.door_open


def test_valid_door_cycle_ends_user_session(version):
    opened = follow(["password_ok", "open_door"], version)
    assert opened.door_open and opened.authenticated
    assert step(opened, "close_door", version) == INITIAL_STATE


def test_v1_rejects_unauthenticated_open():
    with pytest.raises(InvalidEvent):
        step(INITIAL_STATE, "open_door", "v1")
    assert not INITIAL_STATE.door_open


def test_v0_intentionally_opens_without_authentication():
    opened = step(INITIAL_STATE, "open_door", "v0")
    assert opened.door_open
    assert not opened.authenticated  # BUG-01 được giữ lại, không lọc khỏi BFS.


@pytest.mark.parametrize("event", ["password_ok", "password_bad"])
def test_existing_session_does_not_accept_another_password(version, event):
    state = follow(["password_ok"], version)
    with pytest.raises(InvalidEvent):
        step(state, event, version)


def test_tamper_closes_open_door_revokes_session_and_blocks_input(version):
    opened = follow(["password_ok", "open_door"], version)
    alarmed = step(opened, "tamper", version)
    assert alarmed.alarm
    assert not alarmed.door_open and not alarmed.authenticated
    for event in ("password_ok", "password_bad", "open_door"):
        with pytest.raises(InvalidEvent):
            step(alarmed, event, version)
    assert step(alarmed, "wait", version).alarm


def test_tamper_preserves_lockout_and_failure_count(version):
    alarmed = follow(["password_bad"] * 3 + ["tamper"], version)
    assert alarmed.alarm
    assert alarmed.failed_attempts == 3
    assert alarmed.phase == "locked_out"


def test_reset_without_admin_verification_is_rejected(version):
    # authenticated của người dùng thường không phải quyền quản trị.
    for state in (INITIAL_STATE, State(authenticated=True)):
        with pytest.raises(InvalidEvent):
            step(state, "admin_reset", version)
        with pytest.raises(InvalidEvent):
            step(state, "admin_reset", version, admin_authenticated=False)
        assert not state.admin_authorized


def test_admin_reset_recovers_from_lockout_and_alarm(version):
    locked_alarm = follow(["password_bad"] * 3 + ["tamper"], version)
    with pytest.raises(InvalidEvent):
        step(locked_alarm, "admin_reset", version, admin_authenticated=False)
    resetting = step(locked_alarm, "admin_reset", version, admin_authenticated=True)
    assert resetting.phase == "resetting" and resetting.admin_authorized
    assert resetting.failed_attempts == 3 and resetting.alarm
    assert not resetting.door_open and not resetting.authenticated
    assert step(resetting, "reset_complete", version) == INITIAL_STATE


def test_admin_reset_closes_door_and_revokes_user_session(version):
    opened = follow(["password_ok", "open_door"], version)
    resetting = step(opened, "admin_reset", version, admin_authenticated=True)
    assert resetting.admin_authorized
    assert not resetting.authenticated and not resetting.door_open


def test_admin_flag_only_affects_the_reset_request(version):
    state = step(INITIAL_STATE, "password_ok", version, admin_authenticated=True)
    assert state.authenticated
    assert not state.admin_authorized


def test_v1_resetting_only_accepts_completion():
    resetting = step(INITIAL_STATE, "admin_reset", admin_authenticated=True)
    assert list(successors(resetting, "v1")) == [("reset_complete", INITIAL_STATE)]
    for event in EVENTS:
        if event != "reset_complete":
            with pytest.raises(InvalidEvent):
                step(resetting, event, "v1", admin_authenticated=True)


def test_v0_reset_retry_preserves_reset_state_but_completion_still_exists():
    resetting = step(INITIAL_STATE, "admin_reset", "v0", admin_authenticated=True)
    assert step(resetting, "reset_retry", "v0") == resetting  # BUG-02.
    assert set(successors(resetting, "v0")) == {
        ("reset_complete", INITIAL_STATE), ("reset_retry", resetting),
    }


@pytest.mark.parametrize("admin_value", [0, 1, None, "yes"])
def test_admin_verification_result_must_be_an_explicit_boolean(admin_value):
    with pytest.raises(ValueError, match="admin_authenticated"):
        step(INITIAL_STATE, "admin_reset", admin_authenticated=admin_value)


def test_unknown_event_is_rejected(version):
    with pytest.raises(InvalidEvent):
        step(INITIAL_STATE, "unknown", version)


def test_invalid_version_is_not_silently_treated_as_v1():
    with pytest.raises(ValueError, match="Phiên bản"):
        step(INITIAL_STATE, "password_ok", "v2")
    with pytest.raises(ValueError, match="Phiên bản"):
        list(successors(INITIAL_STATE, "v2"))
