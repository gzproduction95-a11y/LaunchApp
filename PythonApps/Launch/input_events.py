"""Encode raw MatrixOS key events for transfer to the computer."""

try:
    from .protocol_v2 import split_u14, split_u28
except ImportError:  # MatrixOS stages app files as top-level siblings.
    from protocol_v2 import split_u14, split_u28


FLAG_PRESSED = 1
FLAG_RELEASED = 2
FLAG_HELD = 4


def encode_input_event(session_id, event_id, timestamp_ms, is_function,
                       pressed, released, held, x=None, y=None):
    if not isinstance(is_function, bool):
        raise ValueError("function-key flag must be boolean")
    if is_function:
        if x is not None or y is not None:
            raise ValueError("function-key events cannot contain pad coordinates")
        x = y = 0x7F
    elif (not isinstance(x, int) or not isinstance(y, int)
          or not 0 <= x < 8 or not 0 <= y < 8):
        raise ValueError("pad event coordinates must be within the 8x8 grid")
    flags = ((FLAG_PRESSED if pressed else 0)
             | (FLAG_RELEASED if released else 0)
             | (FLAG_HELD if held else 0))
    return (split_u28(session_id) + split_u14(event_id)
            + split_u28(timestamp_ms & 0x0FFFFFFF)
            + (1 if is_function else 0, flags, x, y))
