"""Bounded protocol-v11 color-slot table and delta encoders."""
from .protocol_v2 import (FRAME_SLOT_DELTA, FRAME_TABLE_BEGIN,
                          FRAME_TABLE_COLOR_CHUNK, FRAME_TABLE_COMMIT,
                          FRAME_TABLE_MAP_CHUNK, encode_frame, pack_rgb,
                          split_u14, split_u28)

CELL_COUNT = 64
MAX_SLOTS = 64
MAX_COLOR_CHUNK = 15
MAX_MAP_CHUNK = 32


def build_slot_delta(session_id, frame_id, base_frame_id, entries, sequence=0):
    entries = tuple((int(slot), int(color)) for slot, color in entries)
    if not 1 <= len(entries) <= 16:
        raise ValueError("slot delta must update 1..16 colors")
    slots = [slot for slot, _color in entries]
    if len(set(slots)) != len(slots) or any(not 0 <= slot < MAX_SLOTS for slot in slots):
        raise ValueError("slot ids must be unique and within 0..63")
    payload = (split_u28(session_id) + split_u14(frame_id)
               + split_u14(base_frame_id) + (len(entries),))
    for slot, color in entries:
        payload += (slot,) + pack_rgb(color)
    message = encode_frame(FRAME_SLOT_DELTA, sequence, payload)
    if len(message) + 7 > 102:
        raise ValueError("slot delta exceeds the 102-byte wire limit")
    return message


def build_color_table(session_id, frame_id, base_frame_id,
                      slot_colors, cell_slots, sequence=0):
    slot_colors = tuple(int(color) for color in slot_colors)
    cell_slots = tuple(int(slot) for slot in cell_slots)
    if not 1 <= len(slot_colors) <= MAX_SLOTS or len(cell_slots) != CELL_COUNT:
        raise ValueError("color table requires 1..64 slots and 64 cell references")
    if any(not 0 <= color <= 0xFFFFFF for color in slot_colors):
        raise ValueError("slot color must be RGB888")
    if any(not 0 <= slot < len(slot_colors) for slot in cell_slots):
        raise ValueError("cell references an undefined color slot")
    full = base_frame_id is None
    base = 0 if full else int(base_frame_id)
    color_parts = [slot_colors[i:i + MAX_COLOR_CHUNK]
                   for i in range(0, len(slot_colors), MAX_COLOR_CHUNK)]
    map_parts = [cell_slots[i:i + MAX_MAP_CHUNK]
                 for i in range(0, CELL_COUNT, MAX_MAP_CHUNK)]
    sid = split_u28(session_id)
    fid = split_u14(frame_id)
    base_id = split_u14(base)
    messages = []
    def add(kind, payload):
        nonlocal sequence
        messages.append(encode_frame(kind, sequence & 0x7F, payload))
        sequence += 1
    add(FRAME_TABLE_BEGIN, sid + fid + base_id
        + (1 if full else 0, len(slot_colors), len(color_parts), len(map_parts)))
    for index, part in enumerate(color_parts):
        payload = sid + fid + (index, len(color_parts), len(part))
        for slot, color in enumerate(part, index * MAX_COLOR_CHUNK):
            payload += (slot,) + pack_rgb(color)
        add(FRAME_TABLE_COLOR_CHUNK, payload)
    for index, part in enumerate(map_parts):
        start = index * MAX_MAP_CHUNK
        payload = sid + fid + (index, len(map_parts), len(part))
        for cell, slot in enumerate(part, start):
            payload += (cell, slot)
        add(FRAME_TABLE_MAP_CHUNK, payload)
    add(FRAME_TABLE_COMMIT, sid + fid)
    if any(len(message) + 7 > 102 for message in messages):
        raise ValueError("color table transaction contains an oversized packet")
    return tuple(messages)


def build_table_patch(session_id, frame_id, base_frame_id, slot_count,
                      color_entries, cell_entries, sequence=0):
    color_entries = tuple((int(slot), int(color)) for slot, color in color_entries)
    cell_entries = tuple((int(cell), int(slot)) for cell, slot in cell_entries)
    if not 1 <= int(slot_count) <= MAX_SLOTS:
        raise ValueError("invalid color slot count")
    if len({slot for slot, _ in color_entries}) != len(color_entries):
        raise ValueError("duplicate color slot update")
    if len({cell for cell, _ in cell_entries}) != len(cell_entries):
        raise ValueError("duplicate cell mapping update")
    if any(not 0 <= slot < slot_count or not 0 <= color <= 0xFFFFFF
           for slot, color in color_entries):
        raise ValueError("invalid color slot update")
    if any(not 0 <= cell < CELL_COUNT or not 0 <= slot < slot_count
           for cell, slot in cell_entries):
        raise ValueError("invalid cell mapping update")
    color_parts = [color_entries[i:i + MAX_COLOR_CHUNK]
                   for i in range(0, len(color_entries), MAX_COLOR_CHUNK)]
    map_parts = [cell_entries[i:i + MAX_MAP_CHUNK]
                 for i in range(0, len(cell_entries), MAX_MAP_CHUNK)]
    if not color_parts and not map_parts:
        raise ValueError("empty color table patch")
    sid = split_u28(session_id); fid = split_u14(frame_id)
    base = split_u14(base_frame_id); messages = []
    def add(kind, payload):
        nonlocal sequence
        messages.append(encode_frame(kind, sequence & 0x7F, payload)); sequence += 1
    add(FRAME_TABLE_BEGIN, sid + fid + base
        + (0, slot_count, len(color_parts), len(map_parts)))
    for index, part in enumerate(color_parts):
        payload = sid + fid + (index, len(color_parts), len(part))
        for slot, color in part:
            payload += (slot,) + pack_rgb(color)
        add(FRAME_TABLE_COLOR_CHUNK, payload)
    for index, part in enumerate(map_parts):
        payload = sid + fid + (index, len(map_parts), len(part))
        for cell, slot in part:
            payload += (cell, slot)
        add(FRAME_TABLE_MAP_CHUNK, payload)
    add(FRAME_TABLE_COMMIT, sid + fid)
    if any(len(message) + 7 > 102 for message in messages):
        raise ValueError("color table patch contains an oversized packet")
    return tuple(messages)


def assign_role_slots(roles, colors, previous_roles):
    """Retain ids for still-visible roles and safely reuse ids that left the frame."""
    roles = tuple(roles)
    colors = tuple(int(color) for color in colors)
    if len(roles) != CELL_COUNT or len(colors) != CELL_COUNT:
        raise ValueError("role assignment requires 64 cells")
    active = set(roles)
    role_to_slot = {}
    occupied = set()
    for role, slot in previous_roles.items():
        if role in active and isinstance(slot, int) and 0 <= slot < MAX_SLOTS and slot not in occupied:
            role_to_slot[role] = slot
            occupied.add(slot)
    free = [slot for slot in range(MAX_SLOTS) if slot not in occupied]
    for role in sorted(active - set(role_to_slot), key=repr):
        if not free:
            raise ValueError("visible frame needs more than 64 color roles")
        slot = free.pop(0)
        role_to_slot[role] = slot
        occupied.add(slot)
    slot_colors = [0] * MAX_SLOTS
    slot_seen = [False] * MAX_SLOTS
    mapping = []
    for role, color in zip(roles, colors):
        slot = role_to_slot[role]
        if slot_seen[slot] and slot_colors[slot] != color:
            raise ValueError("one stable color role produced conflicting RGB values")
        slot_colors[slot] = color
        slot_seen[slot] = True
        mapping.append(slot)
    return tuple(slot_colors), tuple(mapping), role_to_slot
