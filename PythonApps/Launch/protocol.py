"""Small 7-bit SysEx framing shared with the Live Remote Script."""

APP_PREFIX = (0x4C, 0x41)
VERSION = 7

HELLO = 1
REQUEST_FULL_SYNC = 2
GRID_PRESS = 3
TRACK_ACTION = 4
SCENE_ACTION = 5
NAVIGATION = 6
REC_LENGTH = 7
HELLO_ACK = 17
SYNC_BEGIN = 18
TRACK_COLOR = 19
TRACK_STATE = 20
SLOT_STATE = 21
SYNC_END = 22
SYNC_DATA = 23
HEARTBEAT = 24
SCENE_STATE = 25
SYNC_ACK = 26
WINDOW_META = 27
REC_LENGTH_STATE = 28

def encode(message_type, sequence, payload=()):
    body = APP_PREFIX + (VERSION, message_type, sequence) + tuple(payload)
    if any(not isinstance(value, int) or value < 0 or value > 127 for value in body):
        raise ValueError("Launch SysEx fields must be 7-bit integers")
    checksum = sum(body[2:]) & 0x7F
    return body + (checksum,)

def decode(data):
    try:
        values = tuple(int(value) for value in data)
    except (TypeError, ValueError):
        return None
    if values and values[0] == 0xF0:
        header = (0xF0, 0, 2, 3, 0x4D, 0x58)
        if len(values) < 7 or values[:6] != header or values[-1] != 0xF7:
            return None
        values = values[6:-1]
    elif values and values[-1] == 0xF7:
        values = values[:-1]
    if len(values) < 6 or any(value < 0 or value > 127 for value in values):
        return None
    if values[:3] != APP_PREFIX + (VERSION,) or sum(values[2:-1]) & 0x7F != values[-1]:
        return None
    return values[3], values[4], values[5:-1]
