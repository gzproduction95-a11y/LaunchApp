"""Bounded latest-frame sender with atomic acknowledgements and resync."""

from .display_stream import build_frame, new_frame_id
from .display_stream import build_delta_message, build_palette_delta_message


class FrameSender:
    def __init__(self, timeout_seconds=0.25, packet_gap_seconds=0.04):
        self.timeout_seconds = float(timeout_seconds)
        self.packet_gap_seconds = float(packet_gap_seconds)
        self.session_id = None
        self.acknowledged_colors = None
        self.acknowledged_frame_id = None
        self.in_flight = None
        self._desired_colors = None
        self._desired_context = None
        self._force_full = True
        self.palette_disabled = False
        self._next_id = 0
        self._sequence = 0
        self._pending_packets = ()
        self._last_packet_at = None
        self.sent_count = 0
        self.ack_count = 0
        self.nack_count = 0
        self.timeout_count = 0
        self.last_ack_latency = None
        self.max_ack_latency = 0.0
        self.last_acknowledged = None

    def reset(self, session_id):
        self.session_id = int(session_id)
        self.acknowledged_colors = None
        self.acknowledged_frame_id = None
        self.in_flight = None
        self._desired_colors = None
        self._desired_context = None
        self._force_full = True
        self.palette_disabled = False
        self._next_id = 0
        self._sequence = 0
        self._pending_packets = ()
        self._last_packet_at = None
        self.sent_count = 0
        self.ack_count = 0
        self.nack_count = 0
        self.timeout_count = 0
        self.last_ack_latency = None
        self.max_ack_latency = 0.0
        self.last_acknowledged = None

    def offer(self, colors, send_message, now, force=False, context=None):
        self._desired_colors = tuple(colors)
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
            self.acknowledged_frame_id = None
            self._force_full = True
            self.timeout_count += 1
        frame_id = self._next_id
        colors = tuple(self._desired_colors)
        full = self._force_full or self.acknowledged_colors is None
        if full:
            kind = "full"
            messages, colors = build_frame(
                self.session_id, frame_id, colors, None,
                sequence_start=self._sequence)
        else:
            changed = [(index, color) for index, color in enumerate(colors)
                       if color != self.acknowledged_colors[index]]
            if not changed:
                messages = ()
            elif len(changed) <= 16:
                kind = "delta"
                messages = (build_delta_message(
                    self.session_id, frame_id, self.acknowledged_frame_id,
                    changed, sequence=self._sequence),)
            else:
                kind = "chunked"
                try:
                    palette = (None if self.palette_disabled else build_palette_delta_message(
                        self.session_id, frame_id, self.acknowledged_frame_id,
                        colors, self.acknowledged_colors, sequence=self._sequence))
                except ValueError:
                    palette = None
                if palette is not None:
                    kind = "palette"
                    messages = (palette,)
                else:
                    messages, colors = build_frame(
                        self.session_id, frame_id, colors, self.acknowledged_colors,
                        sequence_start=self._sequence, base_frame_id=self.acknowledged_frame_id)
        if not messages:
            self._force_full = False
            return False
        self.in_flight = {"id": frame_id, "colors": colors,
                          "full": full, "kind": kind, "sent_at": None,
                          "context": (dict(self._desired_context)
                                      if self._desired_context is not None else None)}
        self._pending_packets = messages
        self._next_id = new_frame_id(frame_id)
        self._sequence = (self._sequence + len(messages)) & 0x7F
        self._force_full = False
        return self._send_next_packet(send_message, now)

    def _send_next_packet(self, send_message, now):
        if (self._last_packet_at is not None
                and now - self._last_packet_at + 1e-9 < self.packet_gap_seconds):
            return False
        packet = self._pending_packets[0]
        if send_message(packet) is False:
            self._pending_packets = ()
            self.in_flight = None
            self.acknowledged_colors = None
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
                or int(session_id) != self.session_id
                or int(frame_id) != task["id"]):
            return False
        self.last_acknowledged = {
            "id": task["id"], "status": int(status), "full": task["full"],
            "kind": task["kind"], "colors": task["colors"],
            "context": task["context"],
        }
        if int(status) == 1:
            self.acknowledged_colors = task["colors"]
            self.acknowledged_frame_id = task["id"]
            self.ack_count += 1
            if now is not None:
                self.last_ack_latency = max(0.0, float(now) - task["sent_at"])
                self.max_ack_latency = max(self.max_ack_latency, self.last_ack_latency)
        else:
            self.acknowledged_colors = None
            self.acknowledged_frame_id = None
            self._force_full = True
            if task["kind"] == "palette":
                self.palette_disabled = True
            self.nack_count += 1
        self.in_flight = None
        return True
