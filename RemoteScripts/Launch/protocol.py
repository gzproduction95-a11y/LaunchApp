"""Launch v7 SysEx protocol verified with Mystrix Pro and Live 12.4.6."""

APP_PREFIX = (0x4C, 0x41)
PROTOCOL_VERSION = 7
MATRIXOS_SYSEX_HEADER = (0xF0, 0x00, 0x02, 0x03, 0x4D, 0x58)
SYSEX_END = 0xF7

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


def _u7(value):
    value = int(value)
    if value < 0 or value > 0x7F:
        raise ValueError("protocol fields must be 7-bit values")
    return value


def split_u14(value):
    value = int(value)
    if value < 0 or value > 0x3FFF:
        raise ValueError("protocol field exceeds 14-bit range")
    return (value >> 7, value & 0x7F)


def join_u14(high, low):
    high = _u7(high)
    low = _u7(low)
    return high * 128 + low


def encode_frame(message_type, sequence, payload):
    message_type = _u7(message_type)
    sequence = _u7(sequence)
    body = tuple(_u7(value) for value in payload)
    frame = APP_PREFIX + (PROTOCOL_VERSION, message_type, sequence) + body
    checksum = sum(frame[len(APP_PREFIX):]) & 0x7F
    return frame + (checksum,)


def decode_frame(data):
    try:
        data = tuple(int(value) for value in data)
    except (TypeError, ValueError):
        return None

    if data and data[0] == 0xF0:
        if len(data) < len(MATRIXOS_SYSEX_HEADER) + 1:
            return None
        if data[:len(MATRIXOS_SYSEX_HEADER)] != MATRIXOS_SYSEX_HEADER or data[-1] != SYSEX_END:
            return None
        frame = data[len(MATRIXOS_SYSEX_HEADER):-1]
    else:
        frame = data[:-1] if data and data[-1] == SYSEX_END else data

    if len(frame) < len(APP_PREFIX) + 4:
        return None
    if any(value < 0 or value > 0x7F for value in frame):
        return None
    if frame[:len(APP_PREFIX)] != APP_PREFIX:
        return None
    if frame[len(APP_PREFIX)] != PROTOCOL_VERSION:
        return None

    checksum = frame[-1]
    expected = sum(frame[len(APP_PREFIX):-1]) & 0x7F
    if checksum != expected:
        return None

    message_type = frame[len(APP_PREFIX) + 1]
    sequence = frame[len(APP_PREFIX) + 2]
    payload = frame[len(APP_PREFIX) + 3:-1]
    return message_type, sequence, payload
