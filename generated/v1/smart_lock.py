# Generated from G2 model.json. Do not edit; regenerate with run.py --artifacts.
import argparse
import json

VERSION = 'v1'
SOURCE_MODEL_SHA256 = 'd0d83b24961a5de7803f8c9023ebd9df6770528d2b2d7c0c6843bfd16cdde085'
STATE_FIELDS = ('authenticated', 'failed_attempts', 'door_open', 'alarm', 'phase', 'admin_authorized')
EVENTS = ('password_ok', 'password_bad', 'open_door', 'close_door', 'tamper', 'admin_reset', 'reset_complete', 'reset_retry', 'wait')
INITIAL_STATE = 's0'
EVENT_INPUTS = {'admin_reset': {'admin_authenticated': True}}

STATES = {
    's0': (False, 0, False, False, 'normal', False),
    's1': (True, 0, False, False, 'normal', False),
    's2': (False, 1, False, False, 'normal', False),
    's3': (False, 0, False, True, 'normal', False),
    's4': (False, 0, False, False, 'resetting', True),
    's5': (True, 0, True, False, 'normal', False),
    's6': (False, 2, False, False, 'normal', False),
    's7': (False, 1, False, True, 'normal', False),
    's8': (False, 1, False, False, 'resetting', True),
    's9': (False, 0, False, True, 'resetting', True),
    's10': (False, 3, False, False, 'locked_out', False),
    's11': (False, 2, False, True, 'normal', False),
    's12': (False, 2, False, False, 'resetting', True),
    's13': (False, 1, False, True, 'resetting', True),
    's14': (False, 3, False, True, 'locked_out', False),
    's15': (False, 3, False, False, 'resetting', True),
    's16': (False, 2, False, True, 'resetting', True),
    's17': (False, 3, False, True, 'resetting', True),
}

LABELS = {
    's0': ('idle',),
    's1': ('authenticated',),
    's2': (),
    's3': ('alarm',),
    's4': ('admin_authorized', 'resetting'),
    's5': ('authenticated', 'door_open'),
    's6': (),
    's7': ('alarm',),
    's8': ('admin_authorized', 'resetting'),
    's9': ('admin_authorized', 'alarm', 'resetting'),
    's10': ('attempts_eq_3', 'locked_out'),
    's11': ('alarm',),
    's12': ('admin_authorized', 'resetting'),
    's13': ('admin_authorized', 'alarm', 'resetting'),
    's14': ('alarm', 'attempts_eq_3', 'locked_out'),
    's15': ('admin_authorized', 'attempts_eq_3', 'resetting'),
    's16': ('admin_authorized', 'alarm', 'resetting'),
    's17': ('admin_authorized', 'alarm', 'attempts_eq_3', 'resetting'),
}

TRANSITIONS = {
    ('s0', 'password_ok'): 's1',
    ('s0', 'password_bad'): 's2',
    ('s0', 'tamper'): 's3',
    ('s0', 'admin_reset'): 's4',
    ('s0', 'wait'): 's0',
    ('s1', 'open_door'): 's5',
    ('s1', 'tamper'): 's3',
    ('s1', 'admin_reset'): 's4',
    ('s1', 'wait'): 's1',
    ('s2', 'password_ok'): 's1',
    ('s2', 'password_bad'): 's6',
    ('s2', 'tamper'): 's7',
    ('s2', 'admin_reset'): 's8',
    ('s2', 'wait'): 's2',
    ('s3', 'tamper'): 's3',
    ('s3', 'admin_reset'): 's9',
    ('s3', 'wait'): 's3',
    ('s4', 'reset_complete'): 's0',
    ('s5', 'close_door'): 's0',
    ('s5', 'tamper'): 's3',
    ('s5', 'admin_reset'): 's4',
    ('s5', 'wait'): 's5',
    ('s6', 'password_ok'): 's1',
    ('s6', 'password_bad'): 's10',
    ('s6', 'tamper'): 's11',
    ('s6', 'admin_reset'): 's12',
    ('s6', 'wait'): 's6',
    ('s7', 'tamper'): 's7',
    ('s7', 'admin_reset'): 's13',
    ('s7', 'wait'): 's7',
    ('s8', 'reset_complete'): 's0',
    ('s9', 'reset_complete'): 's0',
    ('s10', 'tamper'): 's14',
    ('s10', 'admin_reset'): 's15',
    ('s10', 'wait'): 's10',
    ('s11', 'tamper'): 's11',
    ('s11', 'admin_reset'): 's16',
    ('s11', 'wait'): 's11',
    ('s12', 'reset_complete'): 's0',
    ('s13', 'reset_complete'): 's0',
    ('s14', 'tamper'): 's14',
    ('s14', 'admin_reset'): 's17',
    ('s14', 'wait'): 's14',
    ('s15', 'reset_complete'): 's0',
    ('s16', 'reset_complete'): 's0',
    ('s17', 'reset_complete'): 's0',
}



class InvalidEvent(ValueError):
    """Event bị từ chối; state của bên gọi không bị thay đổi."""


class InvalidState(ValueError):
    """State ID không thuộc mô hình reachable được nhúng."""


def state_values(state):
    if type(state) is not str or state not in STATES:
        raise InvalidState(f"Unknown state: {state!r}")
    return dict(zip(STATE_FIELDS, STATES[state]))


def step(state, event, *, admin_authenticated=False):
    if type(admin_authenticated) is not bool:
        raise ValueError("admin_authenticated must be bool")
    state_values(state)
    if type(event) is not str:
        raise InvalidEvent(f"Unknown event: {event!r}")
    required = EVENT_INPUTS.get(event, {})
    if required.get("admin_authenticated", False) and not admin_authenticated:
        raise InvalidEvent("Admin verification is required")
    try:
        return TRANSITIONS[(state, event)]
    except KeyError:
        raise InvalidEvent(f"Event {event!r} is not enabled at {state}") from None


def main(argv=None):
    parser = argparse.ArgumentParser(description="Generated Smart Lock " + VERSION)
    parser.add_argument("--events", nargs="*", default=[])
    parser.add_argument("--admin-authenticated", action="store_true")
    args = parser.parse_args(argv)
    current = INITIAL_STATE
    print(f"step 0 {current}: " + json.dumps(state_values(current)))
    for index, event in enumerate(args.events, 1):
        try:
            current = step(current, event, admin_authenticated=args.admin_authenticated)
        except InvalidEvent as error:
            print(f"step {index}: REJECTED {error}")
            return 1
        print(f"step {index} --{event}--> {current}: " + json.dumps(state_values(current)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
