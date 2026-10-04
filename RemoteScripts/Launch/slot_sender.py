"""Atomic sender for host-rendered color tables and bounded color updates."""
from .slot_stream import build_color_table, build_slot_delta, build_table_patch
from .display_stream import new_frame_id


class ColorTableSender:
    def __init__(self, timeout_seconds=0.25, packet_gap_seconds=0.04):
        self.timeout_seconds = float(timeout_seconds)
        self.packet_gap_seconds = float(packet_gap_seconds)
        self.reset(None)

    def reset(self, session_id):
        self.session_id = None if session_id is None else int(session_id)
        self.acknowledged_colors = None
        self.acknowledged_slots = None
        self.acknowledged_frame_id = None
        self.in_flight = None
        self._desired_colors = None
        self._desired_slots = None
        self._force_full = True
        self._pending_packets = ()
        self._last_packet_at = None
        self._next_id = 0
        self._sequence = 0
        self.sent_count = self.ack_count = self.nack_count = self.timeout_count = 0
        self.last_ack_latency = None
        self.max_ack_latency = 0.0
        self.last_ack_render_age = None
        self.max_ack_render_age = 0.0
        self.last_acknowledged = None

    def install_table(self, slot_colors, cell_slots, send_message, now):
        return self.offer(slot_colors, cell_slots, send_message, now, force=True)

    def offer(self, slot_colors, cell_slots, send_message, now,
              force=False, context=None):
        if self.session_id is None:
            return False
        colors = tuple(int(color) for color in slot_colors)
        slots = tuple(int(slot) for slot in cell_slots)
        if len(colors) < 1 or len(colors) > 64 or len(slots) != 64:
            raise ValueError("invalid color table dimensions")
        if any(not 0 <= slot < len(colors) for slot in slots):
            raise ValueError("cell references an undefined color slot")
        self._desired_colors = colors
        self._desired_slots = slots
        self._desired_context = dict(context) if context is not None else None
        self._force_full = self._force_full or bool(force)
        return self.service(send_message, now)

    def service(self, send_message, now):
        if self.session_id is None or self._desired_colors is None:
            return False
        now = float(now)
        if self.in_flight is not None:
            if self._pending_packets:
                return self._send_next_packet(send_message, now)
            if now - self.in_flight["sent_at"] <= self.timeout_seconds:
                return False
            self.in_flight = None
            self.acknowledged_colors = None
            self.acknowledged_slots = None
            self.acknowledged_frame_id = None
            self._force_full = True
            self.timeout_count += 1
        palette = self._desired_colors
        mapping = self._desired_slots
        full = (self._force_full or self.acknowledged_colors is None
                or len(palette) != len(self.acknowledged_colors))
        frame_id = self._next_id
        frame_colors = tuple(palette[slot] for slot in mapping)
        if full:
            kind = "table_full"
            messages = build_color_table(self.session_id, frame_id, None,
                                         palette, mapping, self._sequence)
        else:
            color_entries = tuple((slot, color) for slot, color in enumerate(palette)
                                  if color != self.acknowledged_colors[slot])
            map_entries = tuple((cell, slot) for cell, slot in enumerate(mapping)
                                if slot != self.acknowledged_slots[cell])
            if not color_entries and not map_entries:
                return False
            if not map_entries and len(color_entries) <= 16:
                kind = "slot_delta"
                messages = (build_slot_delta(self.session_id, frame_id,
                    self.acknowledged_frame_id, color_entries, self._sequence),)
            else:
                kind = "table_patch"
                messages = build_table_patch(self.session_id, frame_id,
                    self.acknowledged_frame_id, len(palette), color_entries,
                    map_entries, self._sequence)
        self.in_flight = {"id": frame_id, "colors": palette,
                          "frame_colors": frame_colors, "slots": mapping,
                          "full": full, "kind": kind, "sent_at": None,
                          "context": self._desired_context}
        self._pending_packets = messages
        self._next_id = new_frame_id(frame_id)
        self._sequence = (self._sequence + len(messages)) & 0x7F
        self._force_full = False
        return self._send_next_packet(send_message, now)

    def _send_next_packet(self, send_message, now):
        if (self._last_packet_at is not None
                and now - self._last_packet_at + 1e-9 < self.packet_gap_seconds):
            return False
        if send_message(self._pending_packets[0]) is False:
            self._pending_packets = ()
            self.in_flight = None
            self.acknowledged_colors = None
            self.acknowledged_slots = None
            self.acknowledged_frame_id = None
            self._force_full = True
            return False
        self._pending_packets = self._pending_packets[1:]
        self._last_packet_at = now
        if not self._pending_packets:
            self.in_flight["sent_at"] = now
            self.sent_count += 1
        return True

    def acknowledge(self, session_id, frame_id, status, now=None):
        task = self.in_flight
        if (task is None or task["sent_at"] is None
                or int(session_id) != self.session_id or int(frame_id) != task["id"]):
            return False
        self.last_acknowledged = dict(task)
        self.last_acknowledged["status"] = int(status)
        if int(status) == 1:
            self.acknowledged_colors = task["colors"]
            self.acknowledged_slots = task["slots"]
            self.acknowledged_frame_id = task["id"]
            self.ack_count += 1
            if now is not None:
                self.last_ack_latency = max(0.0, float(now) - task["sent_at"])
                self.max_ack_latency = max(self.max_ack_latency, self.last_ack_latency)
                rendered_at = (task["context"] or {}).get("render_at")
                if rendered_at is not None:
                    self.last_ack_render_age = max(0.0, float(now) - float(rendered_at))
                    self.max_ack_render_age = max(self.max_ack_render_age,
                                                  self.last_ack_render_age)
        else:
            self.acknowledged_colors = None
            self.acknowledged_slots = None
            self.acknowledged_frame_id = None
            self._force_full = True
            self.nack_count += 1
        self.in_flight = None
        return True
