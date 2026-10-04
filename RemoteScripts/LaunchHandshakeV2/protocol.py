"""Small Launch v9 codec for the standalone read-only smoke script."""

APP_PREFIX = (0x4C, 0x41)
PROTOCOL_VERSION = 9
MATRIXOS_SYSEX_HEADER = (0xF0, 0x00, 0x02, 0x03, 0x4D, 0x58)
SYSEX_END = 0xF7
LINK_HELLO, LINK_ACK, INPUT_EVENT, HEARTBEAT = 1, 2, 3, 4
FRAME_BEGIN, FRAME_CHUNK, FRAME_COMMIT, FRAME_ACK, FRAME_REQUEST, FRAME_DELTA = 32, 33, 34, 35, 36, 37


def _u7(value):
    value = int(value)
    if value < 0 or value > 0x7F:
        raise ValueError("protocol fields must be 7-bit integers")
    return value


def split_u14(value):
    value = int(value)
    if not 0 <= value <= 0x3FFF:
        raise ValueError("field exceeds 14-bit range")
    return value >> 7, value & 0x7F


def join_u14(high, low):
    return _u7(high) * 128 + _u7(low)


def split_u28(value):
    value = int(value)
    if not 0 <= value <= 0x0FFFFFFF:
        raise ValueError("field exceeds 28-bit range")
    return ((value >> 21) & 0x7F, (value >> 14) & 0x7F,
            (value >> 7) & 0x7F, value & 0x7F)


def join_u28(values):
    values = tuple(_u7(value) for value in values)
    if len(values) != 4:
        raise ValueError("28-bit field requires four bytes")
    return values[0] * (1 << 21) + values[1] * (1 << 14) + values[2] * 128 + values[3]


def pack_rgb(color):
    color = int(color)
    if color < 0 or color > 0xFFFFFF:
        raise ValueError("RGB color must be 24-bit")
    red, green, blue = color >> 16 & 0xFF, color >> 8 & 0xFF, color & 0xFF
    return (red & 0x7F, green & 0x7F, blue & 0x7F,
            ((red >> 7) << 2) | ((green >> 7) << 1) | (blue >> 7))


def encode_frame(message_type, sequence, payload=()):
    body = tuple(_u7(value) for value in payload)
    frame = APP_PREFIX + (PROTOCOL_VERSION, _u7(message_type), _u7(sequence)) + body
    return frame + (sum(frame[len(APP_PREFIX):]) & 0x7F,)


def decode_frame(data):
    try:
        values = tuple(int(value) for value in data)
    except (TypeError, ValueError):
        return None
    if values and values[0] == 0xF0:
        header = MATRIXOS_SYSEX_HEADER
        if len(values) < len(header) + 1 or values[:len(header)] != header or values[-1] != SYSEX_END:
            return None
        values = values[len(header):-1]
    elif values and values[-1] == SYSEX_END:
        values = values[:-1]
    if len(values) < 6 or any(value < 0 or value > 0x7F for value in values):
        return None
    if values[:3] != APP_PREFIX + (PROTOCOL_VERSION,):
        return None
    if sum(values[len(APP_PREFIX):-1]) & 0x7F != values[-1]:
        return None
    return values[3], values[4], values[5:-1]
