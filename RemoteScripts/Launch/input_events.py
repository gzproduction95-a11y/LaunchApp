"""Decode raw MatrixOS key events while preserving device gesture timing."""

FLAG_PRESSED = 1
FLAG_RELEASED = 2
FLAG_HELD = 4
from .protocol_v2 import join_u14, join_u28


def decode_input_event(payload):
    payload = tuple(payload)
    if len(payload) != 14:
        return None
    try:
        session_id = join_u28(payload[:4])
        event_id = join_u14(payload[4], payload[5])
        device_ms = join_u28(payload[6:10])
    except ValueError:
        return None
    is_function, flags, x, y = payload[10:]
    if is_function not in (0, 1) or flags & ~7:
        return None
    if is_function:
        if (x, y) != (0x7F, 0x7F):
            return None
        x = y = None
    elif not (x < 8 and y < 8):
        return None
    return {
        "session_id": session_id,
        "event_id": event_id,
        "device_ms": device_ms,
        "is_function": bool(is_function),
        "pressed": bool(flags & FLAG_PRESSED),
        "released": bool(flags & FLAG_RELEASED),
        "held": bool(flags & FLAG_HELD),
        "x": x,
        "y": y,
    }


def extend_device_millis(current, previous_raw, previous_absolute):
    """Unwrap a 28-bit device clock; reject packets older than half its range."""
    current = int(current)
    if not 0 <= current <= 0x0FFFFFFF:
        return None
    if previous_raw is None or previous_absolute is None:
        return current, current
    delta = (current - int(previous_raw)) & 0x0FFFFFFF
    if delta >= 0x08000000:
        return None
    return current, int(previous_absolute) + delta
