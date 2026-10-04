"""V8 link-only Live diagnostic; sends no display frames or Live actions."""

from time import monotonic

from ableton.v2.control_surface import ControlSurface
from ableton.v2.control_surface.elements import SysexElement

from .protocol import (HEARTBEAT, LINK_ACK, LINK_HELLO,
                       MATRIXOS_SYSEX_HEADER, decode_frame, encode_frame,
                       join_u28, split_u28)


class LaunchLinkOnly(ControlSurface):
    def __init__(self, c_instance):
        super(LaunchLinkOnly, self).__init__(c_instance)
        self._host = c_instance
        self._sequence = 0
        self._boot_id = None
        self._session_id = None
        with self.component_guard():
            self._sysex_input = SysexElement(
                sysex_identifier=MATRIXOS_SYSEX_HEADER)
            self._sysex_input.add_value_listener(self._on_sysex)
        self._log("Launch link-only diagnostic ready; no LED frames or Live actions")

    def _log(self, message):
        try:
            self._host.log_message(message)
        except Exception:
            pass

    def _send(self, message_type, payload):
        self._sequence = (self._sequence + 1) & 0x7F
        frame = encode_frame(message_type, self._sequence, payload)
        return self._send_midi(MATRIXOS_SYSEX_HEADER + frame + (0xF7,))

    def receive_midi(self, midi_bytes):
        self._on_sysex(midi_bytes)

    def _on_sysex(self, midi_bytes):
        decoded = decode_frame(midi_bytes)
        if decoded is None:
            return
        message, _sequence, payload = decoded
        if message == LINK_HELLO and len(payload) == 4:
            boot_id = join_u28(payload)
            if self._boot_id != boot_id or self._session_id is None:
                self._boot_id = boot_id
                self._session_id = int(monotonic() * 1000.0) & 0x0FFFFFFF or 1
            self._send(LINK_ACK, split_u28(boot_id) + split_u28(self._session_id))
            self._log("Launch link-only acknowledged boot={}; no LED frames sent".format(boot_id))
        elif message == HEARTBEAT and len(payload) == 4:
            if join_u28(payload) == self._session_id:
                self._send(HEARTBEAT, split_u28(self._session_id))


def create_instance(c_instance):
    return LaunchLinkOnly(c_instance)
