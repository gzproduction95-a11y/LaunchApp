import unittest
import importlib.util
from pathlib import Path

from RemoteScripts.Launch.protocol import (
    APP_PREFIX,
    decode_frame,
    encode_frame,
)
from PythonApps.Launch.protocol import encode as device_encode, decode as device_decode
from PythonApps.Launch.protocol import VERSION as DEVICE_VERSION
from RemoteScripts.Launch.protocol import PROTOCOL_VERSION as LIVE_VERSION

_diagnostic_spec = importlib.util.spec_from_file_location(
    "launch_handshake_protocol",
    Path(__file__).resolve().parents[2] / "RemoteScripts" / "LaunchHandshake" / "protocol.py",
)
_diagnostic_protocol = importlib.util.module_from_spec(_diagnostic_spec)
_diagnostic_spec.loader.exec_module(_diagnostic_protocol)
DIAGNOSTIC_VERSION = _diagnostic_protocol.PROTOCOL_VERSION


class ProtocolFrameTests(unittest.TestCase):
    def test_round_trip_frame_and_full_sysex_envelope(self):
        frame = encode_frame(3, 17, (0, 63, 127))
        self.assertEqual(decode_frame(frame), (3, 17, (0, 63, 127)))
        wrapped = (0xF0, 0x00, 0x02, 0x03, 0x4D, 0x58) + frame + (0xF7,)
        self.assertEqual(decode_frame(wrapped), (3, 17, (0, 63, 127)))

    def test_invalid_checksum_is_rejected(self):
        frame = list(encode_frame(3, 4, (8, 9)))
        frame[-1] = (frame[-1] + 1) & 0x7F
        self.assertIsNone(decode_frame(frame))

    def test_unknown_version_is_rejected(self):
        frame = list(encode_frame(3, 4, (8, 9)))
        frame[len(APP_PREFIX)] = 1
        frame[-1] = sum(frame[2:-1]) & 0x7F
        self.assertIsNone(decode_frame(frame))

    def test_non_seven_bit_payload_is_rejected(self):
        self.assertIsNone(decode_frame((0x4C, 0x41, 1, 3, 4, 0x80, 0)))

    def test_truncated_and_wrong_prefix_frames_are_rejected(self):
        frame = encode_frame(3, 4, (8, 9))
        self.assertIsNone(decode_frame(frame[:-1]))
        self.assertIsNone(decode_frame((0x4C, 0x42) + frame[2:]))

    def test_message_fields_must_be_seven_bit_values(self):
        with self.assertRaises(ValueError):
            encode_frame(128, 0, ())
        with self.assertRaises(ValueError):
            encode_frame(0, 0, (128,))

    def test_device_and_remote_script_frames_are_byte_compatible(self):
        payload = (2, 64, 127)
        remote = encode_frame(19, 31, payload)
        device = device_encode(19, 31, payload)
        self.assertEqual(device, remote)
        self.assertEqual(device_decode(remote), (19, 31, payload))

    def test_protocol_v7_is_used_by_app_live_script_and_diagnostic_script(self):
        self.assertEqual((DEVICE_VERSION, LIVE_VERSION, DIAGNOSTIC_VERSION), (7, 7, 7))

    def test_protocol_v4_frames_are_rejected_by_v5(self):
        old = [0x4C, 0x41, 4, 3, 4, 8, 9, 0]
        old[-1] = sum(old[2:-1]) & 0x7F
        self.assertIsNone(decode_frame(old))

    def test_sync_ack_is_shared_by_all_protocol_implementations(self):
        from RemoteScripts.Launch.protocol import SYNC_ACK as LIVE_ACK
        from PythonApps.Launch.protocol import SYNC_ACK as DEVICE_ACK
        self.assertEqual(LIVE_ACK, DEVICE_ACK)


if __name__ == "__main__":
    unittest.main()
