import importlib.util
import unittest
from pathlib import Path

from PythonApps.Launch.protocol_v2 import (
    FRAME_BEGIN, FRAME_CHUNK, FRAME_COMMIT, INPUT_EVENT, LINK_HELLO,
    decode_frame, encode_frame, pack_rgb, unpack_rgb,
)
_diagnostic_spec = importlib.util.spec_from_file_location(
    "launch_v2_handshake_protocol",
    Path(__file__).resolve().parents[2] / "RemoteScripts" / "LaunchHandshakeV2" / "protocol.py",
)
_diagnostic_protocol = importlib.util.module_from_spec(_diagnostic_spec)
_diagnostic_spec.loader.exec_module(_diagnostic_protocol)
diagnostic_encode = _diagnostic_protocol.encode_frame
diagnostic_decode = _diagnostic_protocol.decode_frame
from RemoteScripts.Launch.protocol_v2 import (
    decode_frame as remote_decode,
    encode_frame as remote_encode,
    pack_rgb as remote_pack_rgb,
    unpack_rgb as remote_unpack_rgb,
)


class V2ProtocolTests(unittest.TestCase):
    def test_rgb888_round_trips_through_seven_bit_sysex_bytes(self):
        for color in (0x000000, 0xFFFFFF, 0x123456, 0xFF0081):
            with self.subTest(color=color):
                packed = pack_rgb(color)
                self.assertEqual(len(packed), 4)
                self.assertTrue(all(0 <= value <= 127 for value in packed))
                self.assertEqual(unpack_rgb(packed), color)
                self.assertEqual(remote_unpack_rgb(remote_pack_rgb(color)), color)

    def test_versioned_frame_round_trips_and_rejects_corruption(self):
        frame = encode_frame(LINK_HELLO, 7, (11, 22, 33))
        self.assertEqual(decode_frame(frame), (LINK_HELLO, 7, (11, 22, 33)))
        self.assertEqual(remote_encode(LINK_HELLO, 7, (11, 22, 33)), frame)
        self.assertEqual(remote_decode(frame), (LINK_HELLO, 7, (11, 22, 33)))
        corrupted = frame[:-1] + ((frame[-1] + 1) & 0x7F,)
        self.assertIsNone(decode_frame(corrupted))

    def test_protocol_has_distinct_input_and_atomic_frame_messages(self):
        self.assertEqual(len({LINK_HELLO, INPUT_EVENT, FRAME_BEGIN,
                              FRAME_CHUNK, FRAME_COMMIT}), 5)


if __name__ == "__main__":
    unittest.main()
