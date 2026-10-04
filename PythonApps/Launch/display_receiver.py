"""Receive protocol-v11 host-rendered color tables."""

try:
    from .protocol_v2 import (FRAME_ACK, FRAME_TABLE_BEGIN,
                              FRAME_TABLE_COLOR_CHUNK, FRAME_TABLE_MAP_CHUNK,
                              FRAME_TABLE_COMMIT, FRAME_SLOT_DELTA,
                              join_u14, join_u28, unpack_rgb)
except ImportError:  # MatrixOS stages these files as top-level siblings.
    from protocol_v2 import (FRAME_ACK, FRAME_TABLE_BEGIN,
                             FRAME_TABLE_COLOR_CHUNK, FRAME_TABLE_MAP_CHUNK,
                             FRAME_TABLE_COMMIT, FRAME_SLOT_DELTA,
                             join_u14, join_u28, unpack_rgb)

CELL_COUNT = 64


class FrameReceiver:
    def __init__(self, session_id=None):
        self.session_id = session_id
        self.colors = (0,) * CELL_COUNT
        self.last_frame_id = None
        self._slot_colors = None
        self._cell_slots = None
        self._last_slot_signature = None
        self._table_pending = None

    def set_session(self, session_id):
        self.session_id = int(session_id)
        self.colors = (0,) * CELL_COUNT
        self.last_frame_id = None
        self._slot_colors = None
        self._cell_slots = None
        self._last_slot_signature = None
        self._table_pending = None

    @staticmethod
    def _newer(candidate, previous):
        if previous is None:
            return True
        distance = (candidate - previous) & 0x3FFF
        return 0 < distance < 0x2000

    def receive(self, decoded):
        if decoded is None:
            return None
        message, _sequence, payload = decoded
        if message == FRAME_TABLE_BEGIN:
            return self._table_begin(payload)
        if message == FRAME_TABLE_COLOR_CHUNK:
            return self._table_color_chunk(payload)
        if message == FRAME_TABLE_MAP_CHUNK:
            return self._table_map_chunk(payload)
        if message == FRAME_TABLE_COMMIT:
            return self._table_commit(payload)
        if message == FRAME_SLOT_DELTA:
            return self._slot_delta(payload)
        return None

    def _table_begin(self, payload):
        if len(payload) != 12:
            return None
        session = join_u28(payload[:4])
        frame = join_u14(payload[4], payload[5])
        base = join_u14(payload[6], payload[7])
        full, slot_count, color_chunks, map_chunks = payload[8:12]
        if (session != self.session_id or full not in (0, 1)
                or not 1 <= slot_count <= 64
                or not 0 <= color_chunks <= 5 or not 0 <= map_chunks <= 2
                or (full and (color_chunks == 0 or map_chunks == 0))
                or (not full and color_chunks == 0 and map_chunks == 0)
                or not self._newer(frame, self.last_frame_id)):
            return FRAME_ACK, frame, 0
        if (self._table_pending is not None
                and frame != self._table_pending["id"]
                and not self._newer(frame, self._table_pending["id"])):
            return FRAME_ACK, frame, 0
        if self._table_pending is not None and frame == self._table_pending["id"]:
            return None
        if full:
            palette = [None] * slot_count
            mapping = [None] * CELL_COUNT
        else:
            if (self.last_frame_id is None or base != self.last_frame_id
                    or self._slot_colors is None or self._cell_slots is None
                    or slot_count != len(self._slot_colors)):
                return FRAME_ACK, frame, 0
            palette = list(self._slot_colors)
            mapping = list(self._cell_slots)
        self._table_pending = {
            "id": frame, "full": bool(full), "base": base,
            "slot_count": slot_count, "expected_color_chunks": color_chunks,
            "expected_map_chunks": map_chunks, "colors": palette,
            "mapping": mapping, "color_chunks": {}, "map_chunks": {},
            "seen_slots": set(), "seen_cells": set(),
        }
        return None

    def _table_color_chunk(self, payload):
        pending = self._table_pending
        if pending is None or len(payload) < 10:
            return None
        frame = join_u14(payload[4], payload[5])
        if join_u28(payload[:4]) != self.session_id or frame != pending["id"]:
            return FRAME_ACK, frame, 0
        index, total, count = payload[6:9]
        signature = tuple(payload)
        if (total != pending["expected_color_chunks"] or index >= total
                or not 1 <= count <= 15 or len(payload) != 9 + count * 5):
            self._table_pending = None
            return FRAME_ACK, frame, 0
        previous = pending["color_chunks"].get(index)
        if previous is not None:
            if previous[0] == signature:
                return None
            self._table_pending = None
            return FRAME_ACK, frame, 0
        entries = []
        offset = 9
        for _ in range(count):
            slot = payload[offset]
            if slot >= pending["slot_count"] or slot in pending["seen_slots"]:
                self._table_pending = None
                return FRAME_ACK, frame, 0
            try:
                color = unpack_rgb(payload[offset + 1:offset + 5])
            except ValueError:
                self._table_pending = None
                return FRAME_ACK, frame, 0
            pending["seen_slots"].add(slot)
            pending["colors"][slot] = color
            entries.append(slot)
            offset += 5
        pending["color_chunks"][index] = (signature, tuple(entries))
        return None

    def _table_map_chunk(self, payload):
        pending = self._table_pending
        if pending is None or len(payload) < 11:
            return None
        frame = join_u14(payload[4], payload[5])
        if join_u28(payload[:4]) != self.session_id or frame != pending["id"]:
            return FRAME_ACK, frame, 0
        index, total, count = payload[6:9]
        signature = tuple(payload)
        if (total != pending["expected_map_chunks"] or index >= total
                or not 1 <= count <= 32 or len(payload) != 9 + count * 2):
            self._table_pending = None
            return FRAME_ACK, frame, 0
        previous = pending["map_chunks"].get(index)
        if previous is not None:
            if previous[0] == signature:
                return None
            self._table_pending = None
            return FRAME_ACK, frame, 0
        entries = []
        offset = 9
        for _ in range(count):
            cell, slot = payload[offset], payload[offset + 1]
            if (cell >= CELL_COUNT or cell in pending["seen_cells"]
                    or slot >= pending["slot_count"]):
                self._table_pending = None
                return FRAME_ACK, frame, 0
            pending["seen_cells"].add(cell)
            pending["mapping"][cell] = slot
            entries.append(cell)
            offset += 2
        pending["map_chunks"][index] = (signature, tuple(entries))
        return None

    def _table_commit(self, payload):
        pending = self._table_pending
        if (pending is None or len(payload) != 6
                or join_u28(payload[:4]) != self.session_id
                or join_u14(payload[4], payload[5]) != pending["id"]):
            return None
        self._table_pending = None
        complete = (len(pending["color_chunks"]) == pending["expected_color_chunks"]
                    and len(pending["map_chunks"]) == pending["expected_map_chunks"])
        if pending["full"]:
            complete = (complete
                        and pending["seen_slots"] == set(range(pending["slot_count"]))
                        and pending["seen_cells"] == set(range(CELL_COUNT)))
        if (not complete or any(color is None for color in pending["colors"])
                or any(slot is None for slot in pending["mapping"])):
            return FRAME_ACK, pending["id"], 0
        self._slot_colors = tuple(pending["colors"])
        self._cell_slots = tuple(pending["mapping"])
        self.colors = tuple(self._slot_colors[slot] for slot in self._cell_slots)
        self.last_frame_id = pending["id"]
        self._last_slot_signature = None
        return FRAME_ACK, self.last_frame_id, 1

    def _slot_delta(self, payload):
        if len(payload) < 14:
            return None
        session = join_u28(payload[:4])
        frame = join_u14(payload[4], payload[5])
        base = join_u14(payload[6], payload[7])
        count = payload[8]
        if (session != self.session_id or not 1 <= count <= 16
                or len(payload) != 9 + count * 5):
            return FRAME_ACK, frame, 0
        signature = tuple(payload)
        if frame == self.last_frame_id and signature == self._last_slot_signature:
            return FRAME_ACK, frame, 1
        if (self._table_pending is not None or self.last_frame_id is None
                or base != self.last_frame_id or not self._newer(frame, self.last_frame_id)
                or self._slot_colors is None or self._cell_slots is None):
            return FRAME_ACK, frame, 0
        palette = list(self._slot_colors)
        seen = set()
        offset = 9
        for _ in range(count):
            slot = payload[offset]
            if slot >= len(palette) or slot in seen:
                return FRAME_ACK, frame, 0
            try:
                palette[slot] = unpack_rgb(payload[offset + 1:offset + 5])
            except ValueError:
                return FRAME_ACK, frame, 0
            seen.add(slot)
            offset += 5
        self._slot_colors = tuple(palette)
        self.colors = tuple(self._slot_colors[slot] for slot in self._cell_slots)
        self.last_frame_id = frame
        self._last_slot_signature = signature
        return FRAME_ACK, frame, 1
