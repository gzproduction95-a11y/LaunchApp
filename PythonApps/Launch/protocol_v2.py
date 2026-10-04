"""Launch v11 transport for raw controls and computer-rendered RGB frames."""

APP_PREFIX = (0x4C, 0x41)
PROTOCOL_VERSION = 11
MATRIXOS_SYSEX_HEADER = (0xF0, 0x00, 0x02, 0x03, 0x4D, 0x58)
SYSEX_END = 0xF7

LINK_HELLO = 1
LINK_ACK = 2
INPUT_EVENT = 3
HEARTBEAT = 4
INPUT_RESET = 5
FRAME_BEGIN = 32
FRAME_CHUNK = 33
FRAME_COMMIT = 34
FRAME_ACK = 35
FRAME_REQUEST = 36
FRAME_DELTA = 37
FRAME_PALETTE_DELTA = 39
FRAME_TABLE_BEGIN = 40
FRAME_TABLE_COLOR_CHUNK = 41
FRAME_TABLE_MAP_CHUNK = 42
FRAME_TABLE_COMMIT = 43
FRAME_SLOT_DELTA = 44


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
    return _u7(high) * 128 + _u7(low)


def split_u28(value):
    value = int(value)
    if value < 0 or value > 0x0FFFFFFF:
        raise ValueError("protocol field exceeds 28-bit range")
    return ((value >> 21) & 0x7F, (value >> 14) & 0x7F,
            (value >> 7) & 0x7F, value & 0x7F)


def join_u28(values):
    values = tuple(_u7(value) for value in values)
    if len(values) != 4:
        raise ValueError("28-bit value requires four 7-bit bytes")
    return values[0] * (1 << 21) + values[1] * (1 << 14) + values[2] * 128 + values[3]


def pack_rgb(color):
    """Pack RGB888 into four legal SysEx bytes without losing high bits."""
    color = int(color)
    if color < 0 or color > 0xFFFFFF:
        raise ValueError("RGB color must be a 24-bit integer")
    red, green, blue = (color >> 16) & 0xFF, (color >> 8) & 0xFF, color & 0xFF
    high_bits = ((red >> 7) << 2) | ((green >> 7) << 1) | (blue >> 7)
    return (red & 0x7F, green & 0x7F, blue & 0x7F, high_bits)


def unpack_rgb(values):
    values = tuple(_u7(value) for value in values)
    if len(values) != 4 or values[3] > 7:
        raise ValueError("invalid packed RGB888 color")
    red = values[0] | (((values[3] >> 2) & 1) << 7)
    green = values[1] | (((values[3] >> 1) & 1) << 7)
    blue = values[2] | ((values[3] & 1) << 7)
    return (red << 16) | (green << 8) | blue


def encode_frame(message_type, sequence, payload=()):
    body = tuple(_u7(value) for value in payload)
    frame = APP_PREFIX + (PROTOCOL_VERSION, _u7(message_type), _u7(sequence)) + body
    checksum = sum(frame[len(APP_PREFIX):]) & 0x7F
    return frame + (checksum,)


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
