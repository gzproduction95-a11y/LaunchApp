import unittest

from PythonApps.Launch.display_receiver import FrameReceiver
from PythonApps.Launch.protocol_v2 import FRAME_ACK, encode_frame
from RemoteScripts.Launch.display_stream import build_frame
from RemoteScripts.Launch.protocol_v2 import decode_frame
from RemoteScripts.Launch.slot_stream import build_color_table, build_slot_delta


class V2DisplayFrameTests(unittest.TestCase):
    def deliver(self, receiver, messages):
        result = None
        for message in messages:
            result = receiver.receive(decode_frame(message)) or result
        return result

    def test_v11_full_table_commits_only_when_all_chunks_arrive(self):
        colors = tuple((slot * 0x030507) & 0xFFFFFF for slot in range(16))
        mapping = tuple(cell % len(colors) for cell in range(64))
        messages = build_color_table(23, 1, None, colors, mapping)
        receiver = FrameReceiver(23)
        self.assertIsNone(self.deliver(receiver, messages[:-1]))
        self.assertEqual(receiver.colors, (0,) * 64)
        self.assertEqual(self.deliver(receiver, messages[-1:]), (FRAME_ACK, 1, 1))
        self.assertEqual(receiver.colors, tuple(colors[slot] for slot in mapping))

    def test_v11_receiver_ignores_obsolete_full_rgb_frame_messages(self):
        colors = tuple((cell * 0x030507) & 0xFFFFFF for cell in range(64))
        old_messages, _ = build_frame(23, 1, colors, None)
        receiver = FrameReceiver(23)
        self.assertIsNone(self.deliver(receiver, old_messages))
        self.assertEqual(receiver.colors, (0,) * 64)

    def test_v11_slot_delta_updates_known_table_and_reacks_exact_retry(self):
        colors = tuple(0x100000 + slot for slot in range(8))
        mapping = tuple(cell % 8 for cell in range(64))
        receiver = FrameReceiver(23)
        self.deliver(receiver, build_color_table(23, 1, None, colors, mapping))
        message = build_slot_delta(23, 2, 1, ((3, 0xABCDEF),))
        decoded = decode_frame(message)
        self.assertEqual(receiver.receive(decoded), (FRAME_ACK, 2, 1))
        self.assertEqual(receiver.receive(decoded), (FRAME_ACK, 2, 1))
        self.assertEqual(receiver.colors,
                         tuple(0xABCDEF if slot == 3 else colors[slot]
                               for slot in mapping))

    def test_v11_receiver_rejects_wrong_session_without_changing_display(self):
        colors = (0x123456, 0xFEDCBA)
        mapping = tuple(cell % 2 for cell in range(64))
        receiver = FrameReceiver(23)
        messages = build_color_table(24, 1, None, colors, mapping)
        self.assertEqual(self.deliver(receiver, messages), (FRAME_ACK, 1, 0))
        self.assertEqual(receiver.colors, (0,) * 64)

    def test_receiver_source_stays_within_confirmed_v21_load_size(self):
        from pathlib import Path
        source = Path(__file__).resolve().parents[2] / "PythonApps" / "Launch" / "display_receiver.py"
        self.assertLessEqual(source.stat().st_size, 9839)


if __name__ == "__main__":
    unittest.main()
