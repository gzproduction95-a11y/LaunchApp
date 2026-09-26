"""Read-only Ableton Live handshake and MIDI round-trip smoke test.

This Control Surface deliberately ignores Launch grid and track commands.
It replies to the device handshake and sends one test-color snapshot only.
"""

import logging

from ableton.v2.control_surface import ControlSurface
from ableton.v2.control_surface.elements import SysexElement

from .protocol import (MATRIXOS_SYSEX_HEADER, HELLO, REQUEST_FULL_SYNC, GRID_PRESS, TRACK_ACTION,
                       HELLO_ACK, SYNC_BEGIN, SYNC_DATA, SYNC_END,
                       decode_frame, encode_frame)

_logger = logging.getLogger("LaunchHandshakeCheck")
SYSEX_IDENTIFIER = MATRIXOS_SYSEX_HEADER


class LaunchHandshakeCheck(ControlSurface):
    def __init__(self, c_instance):
        super(LaunchHandshakeCheck, self).__init__(c_instance)
        self._launch_host = c_instance
        self._sequence = 0
        self._sync_id = 0
        self._sysex_input = None
        with self.component_guard():
            self._sysex_input = SysexElement(sysex_identifier=SYSEX_IDENTIFIER)
            self._sysex_input.add_value_listener(self._on_sysex)
        self._log("Launch Handshake Check initialized")

    def _log(self, message):
        try:
            self._launch_host.log_message(message)
        except Exception:
            # Diagnostics must never prevent a Control Surface from loading.
            try:
                _logger.info(message)
            except Exception:
                pass

    def _send(self, message, payload=()):
        self._sequence = (self._sequence + 1) & 0x7F
        frame = encode_frame(message, self._sequence, payload)
        sent = self._send_midi((0xF0, 0x00, 0x02, 0x03, 0x4D, 0x58) + frame + (0xF7,))
        if sent is False:
            self._log("Launch Handshake Check MIDI send failed: type={}".format(message))
        return sent

    def receive_midi(self, midi_bytes):
        """Keep the parser callable in isolated tests; Live routes via element."""
        self._handle_protocol_message(midi_bytes)

    def _on_sysex(self, midi_bytes):
        self._handle_protocol_message(midi_bytes)

    def _handle_protocol_message(self, midi_bytes):
        decoded = decode_frame(midi_bytes)
        if decoded is None:
            return
        message, _sequence, _payload = decoded
        if message == HELLO:
            self._log("Launch Handshake Check received HELLO")
            self._send(HELLO_ACK)
        elif message == REQUEST_FULL_SYNC:
            self._send_test_snapshot()
        elif message in (GRID_PRESS, TRACK_ACTION):
            self._log("Launch Handshake Check ignored a control action")

    def _send_test_snapshot(self):
        self._sync_id = (self._sync_id + 1) & 0x3FFF
        sync_hi, sync_lo = self._sync_id >> 7, self._sync_id & 0x7F
        self._send(SYNC_BEGIN, (sync_hi, sync_lo, 2,
                                0, 0, 0, 0, 0, 8, 0, 8, 0))
        # A violet marker and explicit Track-present flag prove the return path
        # without reading or changing any Live Set state.
        self._send(SYNC_DATA, (sync_hi, sync_lo, 0, 0, 64, 0, 64, 1, 0, 16))
        self._send(SYNC_END, (sync_hi, sync_lo))
        self._log("Launch Handshake Check sent test snapshot")


def create_instance(c_instance):
    return LaunchHandshakeCheck(c_instance)
