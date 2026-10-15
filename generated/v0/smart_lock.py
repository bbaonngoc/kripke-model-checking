# Generated from G2 model.json. Do not edit; regenerate with run.py --artifacts.
import argparse
import json

VERSION = 'v0'
SOURCE_MODEL_SHA256 = '1c2480b813aeb640d4cdcedeffd98521444945e3941fb0b56f0c765d752f7e26'
STATE_FIELDS = ('authenticated', 'failed_attempts', 'door_open', 'alarm', 'phase', 'admin_authorized')
EVENTS = ('password_ok', 'password_bad', 'open_door', 'close_door', 'tamper', 'admin_reset', 'reset_complete', 'reset_retry', 'wait')
INITIAL_STATE = 's0'
EVENT_INPUTS = {'admin_reset': {'admin_authenticated': True}}

STATES = {
    's0': (False, 0, False, False, 'normal', False),
    's1': (True, 0, False, False, 'normal', False),
    's2': (False, 1, False, False, 'normal', False),
    's3': (False, 0, True, False, 'normal', False),
    's4': (False, 0, False, True, 'normal', False),
    's5': (False, 0, False, False, 'resetting', True),
    's6': (True, 0, True, False, 'normal', False),
    's7': (False, 2, False, False, 'normal', False),
    's8': (False, 1, True, False, 'normal', False),
    's9': (False, 1, False, True, 'normal', False),
    's10': (False, 1, False, False, 'resetting', True),
    's11': (False, 0, False, True, 'resetting', True),
    's12': (False, 3, False, False, 'locked_out', False),
    's13': (False, 2, True, False, 'normal', False),
    's14': (False, 2, False, True, 'normal', False),
    's15': (False, 2, False, False, 'resetting', True),
    's16': (False, 1, False, True, 'resetting', True),
    's17': (False, 3, False, True, 'locked_out', False),
    's18': (False, 3, False, False, 'resetting', True),
    's19': (False, 2, False, True, 'resetting', True),
    's20': (False, 3, False, True, 'resetting', True),
}

LABELS = {
    's0': ('idle',),
    's1': ('authenticated',),
    's2': (),
    's3': ('door_open',),
    's4': ('alarm',),
    's5': ('admin_authorized', 'resetting'),
    's6': ('authenticated', 'door_open'),
    's7': (),
    's8': ('door_open',),
    's9': ('alarm',),
    's10': ('admin_authorized', 'resetting'),
    's11': ('admin_authorized', 'alarm', 'resetting'),
    's12': ('attempts_eq_3', 'locked_out'),
    's13': ('door_open',),
    's14': ('alarm',),
    's15': ('admin_authorized', 'resetting'),
    's16': ('admin_authorized', 'alarm', 'resetting'),
    's17': ('alarm', 'attempts_eq_3', 'locked_out'),
    's18': ('admin_authorized', 'attempts_eq_3', 'resetting'),
    's19': ('admin_authorized', 'alarm', 'resetting'),
    's20': ('admin_authorized', 'alarm', 'attempts_eq_3', 'resetting'),
}

TRANSITIONS = {
    ('s0', 'password_ok'): 's1',
    ('s0', 'password_bad'): 's2',
    ('s0', 'open_door'): 's3',
    ('s0', 'tamper'): 's4',
    ('s0', 'admin_reset'): 's5',
    ('s0', 'wait'): 's0',
    ('s1', 'open_door'): 's6',
    ('s1', 'tamper'): 's4',
    ('s1', 'admin_reset'): 's5',
    ('s1', 'wait'): 's1',
    ('s2', 'password_ok'): 's1',
    ('s2', 'password_bad'): 's7',
    ('s2', 'open_door'): 's8',
    ('s2', 'tamper'): 's9',
    ('s2', 'admin_reset'): 's10',
    ('s2', 'wait'): 's2',
    ('s3', 'close_door'): 's0',
    ('s3', 'tamper'): 's4',
    ('s3', 'admin_reset'): 's5',
    ('s3', 'wait'): 's3',
    ('s4', 'tamper'): 's4',
    ('s4', 'admin_reset'): 's11',
    ('s4', 'wait'): 's4',
    ('s5', 'reset_complete'): 's0',
    ('s5', 'reset_retry'): 's5',
    ('s6', 'close_door'): 's0',
    ('s6', 'tamper'): 's4',
    ('s6', 'admin_reset'): 's5',
    ('s6', 'wait'): 's6',
    ('s7', 'password_ok'): 's1',
    ('s7', 'password_bad'): 's12',
    ('s7', 'open_door'): 's13',
    ('s7', 'tamper'): 's14',
    ('s7', 'admin_reset'): 's15',
    ('s7', 'wait'): 's7',
    ('s8', 'close_door'): 's2',
    ('s8', 'tamper'): 's9',
    ('s8', 'admin_reset'): 's10',
    ('s8', 'wait'): 's8',
    ('s9', 'tamper'): 's9',
    ('s9', 'admin_reset'): 's16',
    ('s9', 'wait'): 's9',
    ('s10', 'reset_complete'): 's0',
    ('s10', 'reset_retry'): 's10',
    ('s11', 'reset_complete'): 's0',
    ('s11', 'reset_retry'): 's11',
    ('s12', 'tamper'): 's17',
    ('s12', 'admin_reset'): 's18',
    ('s12', 'wait'): 's12',
    ('s13', 'close_door'): 's7',
    ('s13', 'tamper'): 's14',
    ('s13', 'admin_reset'): 's15',
    ('s13', 'wait'): 's13',
    ('s14', 'tamper'): 's14',
    ('s14', 'admin_reset'): 's19',
    ('s14', 'wait'): 's14',
    ('s15', 'reset_complete'): 's0',
    ('s15', 'reset_retry'): 's15',
    ('s16', 'reset_complete'): 's0',
    ('s16', 'reset_retry'): 's16',
    ('s17', 'tamper'): 's17',
    ('s17', 'admin_reset'): 's20',
    ('s17', 'wait'): 's17',
    ('s18', 'reset_complete'): 's0',
    ('s18', 'reset_retry'): 's18',
    ('s19', 'reset_complete'): 's0',
    ('s19', 'reset_retry'): 's19',
    ('s20', 'reset_complete'): 's0',
    ('s20', 'reset_retry'): 's20',
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
