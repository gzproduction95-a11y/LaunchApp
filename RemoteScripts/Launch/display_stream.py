"""Build bounded, atomic SysEx updates for the device's 8x8 LED surface."""

from .protocol_v2 import (FRAME_BEGIN, FRAME_CHUNK, FRAME_COMMIT, FRAME_DELTA, FRAME_PALETTE_DELTA,
                          encode_frame, pack_rgb, split_u14, split_u28)

CELL_COUNT = 64
MAX_ENTRIES_PER_CHUNK = 16
MAX_DELTA_ENTRIES = 16
MAX_PALETTE_COLORS = 32


def new_frame_id(previous):
    return 0 if previous is None else (int(previous) + 1) & 0x3FFF


def build_delta_message(session_id, frame_id, base_frame_id, entries,
                        sequence=0):
    """Encode one bounded atomic image delta for the last acknowledged base."""
    entries = tuple((int(index), int(color)) for index, color in entries)
    if not 1 <= len(entries) <= MAX_DELTA_ENTRIES:
        raise ValueError("single-message delta must contain 1..16 cells")
    indices = [index for index, _color in entries]
    if len(set(indices)) != len(indices) or any(not 0 <= index < CELL_COUNT for index in indices):
        raise ValueError("delta cell indices must be unique and within the LED grid")
    payload = split_u28(session_id) + split_u14(frame_id) + split_u14(base_frame_id) + (len(entries),)
    for index, color in entries:
        payload += (index,) + pack_rgb(color)
    return encode_frame(FRAME_DELTA, sequence, payload)


def _pack_7bit_values(values, width):
    accumulator = 0
    bit_count = 0
    packed = []
    for value in values:
        accumulator = (accumulator << width) | int(value)
        bit_count += width
        while bit_count >= 7:
            bit_count -= 7
            packed.append((accumulator >> bit_count) & 0x7F)
    if bit_count:
        packed.append((accumulator << (7 - bit_count)) & 0x7F)
    return tuple(packed)


def build_palette_delta_message(session_id, frame_id, base_frame_id,
                                colors, acknowledged_colors, sequence=0):
    """Encode changed cells as a bounded bitmap plus a compact color palette."""
    colors = tuple(int(color) for color in colors)
    acknowledged_colors = tuple(int(color) for color in acknowledged_colors)
    if len(colors) != CELL_COUNT or len(acknowledged_colors) != CELL_COUNT:
        raise ValueError("palette delta requires two 64-cell images")
    changed = [i for i in range(CELL_COUNT) if colors[i] != acknowledged_colors[i]]
    if not changed:
        raise ValueError("palette delta must change at least one cell")
    palette = []
    lookup = {}
    indexes = []
    for index in changed:
        color = colors[index]
        if color not in lookup:
            lookup[color] = len(palette)
            palette.append(color)
        indexes.append(lookup[color])
    if len(palette) > MAX_PALETTE_COLORS:
        raise ValueError("palette delta has too many colors")
    width = max(1, (len(palette) - 1).bit_length())
    mask = sum(1 << (63 - index) for index in changed)
    bitmap_value = mask << 6
    bitmap = tuple((bitmap_value >> (63 - 7 * group)) & 0x7F for group in range(10))
    payload = (split_u28(session_id) + split_u14(frame_id)
               + split_u14(base_frame_id) + (len(palette), len(changed))
               + bitmap)
    for color in palette:
        payload += pack_rgb(color)
    payload += _pack_7bit_values(indexes, width)
    message = encode_frame(FRAME_PALETTE_DELTA, sequence, payload)
    if len(message) + 7 > 102:
        raise ValueError("palette delta exceeds 102-byte wire limit")
    return message


def build_frame(session_id, frame_id, colors, acknowledged_colors,
                sequence_start=0, max_entries=MAX_ENTRIES_PER_CHUNK, base_frame_id=None):
    """Return encoded messages and canonical colors for one full or delta frame."""
    colors = tuple(int(color) for color in colors)
    if len(colors) != CELL_COUNT or any(color < 0 or color > 0xFFFFFF for color in colors):
        raise ValueError("a Launch frame must contain 64 RGB888 colors")
    if acknowledged_colors is not None and len(acknowledged_colors) != CELL_COUNT:
        raise ValueError("acknowledged frame must contain 64 colors")
    if not 1 <= int(max_entries) <= 20:
        raise ValueError("chunk capacity must be between 1 and 20 cells")

    full = acknowledged_colors is None
    entries = [(index, color) for index, color in enumerate(colors)
               if full or color != acknowledged_colors[index]]
    if not entries:
        return (), colors
    if (acknowledged_colors is not None and len(entries) > MAX_DELTA_ENTRIES
            and len(set(colors)) <= MAX_PALETTE_COLORS):
        try:
            palette_delta = build_palette_delta_message(
                session_id, frame_id, base_frame_id=(((int(frame_id) - 1) & 0x3FFF) if base_frame_id is None else base_frame_id), colors=colors,
                acknowledged_colors=acknowledged_colors, sequence=sequence_start)
        except ValueError:
            palette_delta = None
        if palette_delta is not None:
            return (palette_delta,), colors
    chunks = [entries[index:index + max_entries]
              for index in range(0, len(entries), max_entries)]
    session = split_u28(session_id)
    frame = split_u14(frame_id)
    messages = []
    seq = int(sequence_start) & 0x7F

    def encode(message_type, payload):
        nonlocal seq
        message = encode_frame(message_type, seq, payload)
        seq = (seq + 1) & 0x7F
        return message

    messages.append(encode(FRAME_BEGIN, session + frame + (1 if full else 0, len(chunks))))
    for chunk_index, chunk in enumerate(chunks):
        payload = session + frame + (chunk_index, len(chunk))
        for cell_index, color in chunk:
            payload += (cell_index,) + pack_rgb(color)
        messages.append(encode(FRAME_CHUNK, payload))
    messages.append(encode(FRAME_COMMIT, session + frame))
    return tuple(messages), colors
