"""Small copy of the Launch SysEx frame codec for the standalone smoke script."""

APP_PREFIX = (0x4C, 0x41)
PROTOCOL_VERSION = 7
MATRIXOS_SYSEX_HEADER = (0xF0, 0x00, 0x02, 0x03, 0x4D, 0x58)
SYSEX_END = 0xF7

HELLO = 1
REQUEST_FULL_SYNC = 2
GRID_PRESS = 3
TRACK_ACTION = 4
SCENE_ACTION = 5
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


def _u7(value):
    value = int(value)
    if value < 0 or value > 0x7F:
        raise ValueError("protocol fields must be 7-bit values")
    return value


def encode_frame(message_type, sequence, payload=()):
    body = tuple(_u7(value) for value in payload)
    frame = APP_PREFIX + (PROTOCOL_VERSION, _u7(message_type), _u7(sequence)) + body
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
        data = data[len(MATRIXOS_SYSEX_HEADER):-1]
    elif data and data[-1] == SYSEX_END:
        data = data[:-1]
    if len(data) < len(APP_PREFIX) + 4 or any(value < 0 or value > 0x7F for value in data):
        return None
    if data[:len(APP_PREFIX)] != APP_PREFIX or data[len(APP_PREFIX)] != PROTOCOL_VERSION:
        return None
    if sum(data[len(APP_PREFIX):-1]) & 0x7F != data[-1]:
        return None
    return data[len(APP_PREFIX) + 1], data[len(APP_PREFIX) + 2], data[len(APP_PREFIX) + 3:-1]
