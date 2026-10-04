"""Read-only Launch v9 handshake and LED-frame diagnostic."""

import logging
from time import monotonic

from ableton.v2.control_surface import ControlSurface
from ableton.v2.control_surface.elements import SysexElement

from .protocol import (MATRIXOS_SYSEX_HEADER, LINK_HELLO, LINK_ACK, INPUT_EVENT,
                       HEARTBEAT, FRAME_BEGIN, FRAME_CHUNK, FRAME_COMMIT,
                       FRAME_ACK, FRAME_REQUEST, decode_frame, encode_frame,
                       split_u14, split_u28, join_u14, join_u28, pack_rgb)

_logger = logging.getLogger("LaunchHandshakeCheck")
SYSEX_IDENTIFIER = MATRIXOS_SYSEX_HEADER


class LaunchHandshakeCheck(ControlSurface):
    def __init__(self, c_instance):
        super(LaunchHandshakeCheck, self).__init__(c_instance)
        self._launch_host = c_instance
        self._sequence = 0
        self._device_boot_id = None
        self._session_id = None
        self._sysex_input = None
        self._pending_frames = []
        self._frame_tick_pending = False
        with self.component_guard():
            self._sysex_input = SysexElement(sysex_identifier=SYSEX_IDENTIFIER)
            self._sysex_input.add_value_listener(self._on_sysex)
        self._log("Launch v9 Handshake Check initialized; no Live actions are enabled")

    def _log(self, message):
        try:
            self._launch_host.log_message(message)
        except Exception:
            try:
                _logger.info(message)
            except Exception:
                pass

    def _send(self, message, payload=()):
        self._sequence = (self._sequence + 1) & 0x7F
        frame = encode_frame(message, self._sequence, payload)
        sent = self._send_midi(MATRIXOS_SYSEX_HEADER + frame + (0xF7,))
        if sent is False:
            self._log("Launch v9 Handshake Check MIDI send failed: type={}".format(message))
        return sent

    def receive_midi(self, midi_bytes):
        self._handle_protocol_message(midi_bytes)

    def _on_sysex(self, midi_bytes):
        self._handle_protocol_message(midi_bytes)

    def _send_test_frame(self):
        session = split_u28(self._session_id)
        frame_id = split_u14(0)
        colors = (0xFF00FF,) + (0,) * 63
        chunks = [tuple(range(start, min(start + 16, 64)))
                  for start in range(0, 64, 16)]
        pending = [(FRAME_BEGIN, session + frame_id + (1, len(chunks)))]
        for chunk_index, cells in enumerate(chunks):
            payload = session + frame_id + (chunk_index, len(cells))
            for cell in cells:
                payload += (cell,) + pack_rgb(colors[cell])
            pending.append((FRAME_CHUNK, payload))
        pending.append((FRAME_COMMIT, session + frame_id))
        self._pending_frames = pending
        self._schedule_next_frame_packet()

    def _schedule_next_frame_packet(self):
        if self._pending_frames and not self._frame_tick_pending:
            self._frame_tick_pending = True
            self.schedule_message(1, self._send_next_frame_packet)

    def _send_next_frame_packet(self):
        self._frame_tick_pending = False
        if not self._pending_frames:
            return
        message, payload = self._pending_frames.pop(0)
        self._send(message, payload)
        if self._pending_frames:
            self._schedule_next_frame_packet()
        else:
            self._log("Launch v9 Handshake Check sent one violet marker frame")

    def _handle_protocol_message(self, midi_bytes):
        decoded = decode_frame(midi_bytes)
        if decoded is None:
            return
        message, _sequence, payload = decoded
        if message == LINK_HELLO and len(payload) == 4:
            boot_id = join_u28(payload)
            if self._device_boot_id != boot_id or self._session_id is None:
                self._device_boot_id = boot_id
                self._session_id = int(monotonic() * 1000.0) & 0x0FFFFFFF or 1
            self._send(LINK_ACK, split_u28(boot_id) + split_u28(self._session_id))
            self._send_test_frame()
            self._log("Launch v9 Handshake Check received LINK_HELLO")
        elif message == FRAME_ACK and len(payload) == 7:
            if (join_u28(payload[:4]) == self._session_id
                    and join_u14(payload[4], payload[5]) == 0):
                self._log("Launch v9 test frame acknowledged status={}".format(payload[6]))
        elif message == HEARTBEAT and len(payload) == 4:
            if join_u28(payload) == self._session_id:
                self._send(HEARTBEAT, split_u28(self._session_id))
                self._log("Launch v9 device heartbeat received")
        elif message == INPUT_EVENT:
            self._log("Launch v9 Handshake Check ignored a raw control event")
        elif message == FRAME_REQUEST and len(payload) == 4:
            if join_u28(payload) == self._session_id:
                self._send_test_frame()


def create_instance(c_instance):
    return LaunchHandshakeCheck(c_instance)
