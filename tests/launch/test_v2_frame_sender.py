import unittest

from RemoteScripts.Launch.frame_sender import FrameSender
from RemoteScripts.Launch.protocol_v2 import FRAME_BEGIN, FRAME_COMMIT, FRAME_DELTA, FRAME_PALETTE_DELTA, decode_frame


class V2FrameSenderTests(unittest.TestCase):
    def messages(self, sent):
        return [decode_frame(frame) for frame in sent]

    def test_full_frame_is_spaced_and_timeout_starts_after_commit(self):
        sender = FrameSender(timeout_seconds=0.1)
        sender.reset(17)
        sent = []
        send = lambda frame: sent.append(frame) or True
        sender.offer((0x123456,) * 64, send, 0.0, force=True)
        self.assertEqual([item[0] for item in self.messages(sent)], [FRAME_BEGIN],
                         "initial frame must not burst into the device MIDI queue")
        sender.service(send, 0.02)
        self.assertEqual(len(sent), 1)
        for tick in (0.04, 0.08, 0.12, 0.16, 0.20):
            before = len(sent)
            sender.service(send, tick)
            self.assertEqual(len(sent), before + 1)
            self.assertEqual(sender.timeout_count, 0,
                             "partial transmission is not an ACK timeout")
        self.assertEqual(self.messages(sent)[-1][0], FRAME_COMMIT)
        sender.service(send, 0.29)
        self.assertEqual(sender.timeout_count, 0)
        sender.service(send, 0.31)
        self.assertEqual(sender.timeout_count, 1)

    def test_coalesces_while_one_frame_is_in_flight_then_sends_latest_delta(self):
        sender = FrameSender()
        sender.reset(123)
        sent = []
        first = (1,) * 64
        middle = first
        latest = list(middle)
        latest[7] = 2
        sender.offer(first, lambda frame: sent.append(frame) or True, 0.0, force=True)
        first_frame_id = sender.in_flight["id"]
        self.assertEqual(self.messages(sent)[0][0], FRAME_BEGIN)
        sent.clear()
        sender.offer(middle, lambda frame: sent.append(frame) or True, 0.01)
        sender.offer(tuple(latest), lambda frame: sent.append(frame) or True, 0.02)
        self.assertEqual(sent, [])
        for tick in (0.04, 0.08, 0.12, 0.16, 0.20):
            sender.service(lambda frame: sent.append(frame) or True, tick)
        sent.clear()
        self.assertTrue(sender.acknowledge(123, first_frame_id, 1, 0.23))
        self.assertEqual(sender.ack_count, 1)
        self.assertAlmostEqual(sender.last_ack_latency, 0.03)
        sender.offer(tuple(latest), lambda frame: sent.append(frame) or True, 0.24)
        sender.service(lambda frame: sent.append(frame) or True, 0.28)
        self.assertIsNotNone(sender.in_flight)
        decoded = self.messages(sent)
        self.assertEqual([frame[0] for frame in decoded], [FRAME_DELTA],
                         "small changed images should use one atomic message")
        self.assertEqual(decoded[0][2][8], 1, "only the latest changed cell is sent")

    def test_timeout_discards_uncertain_base_and_resends_a_full_frame(self):
        sender = FrameSender(timeout_seconds=0.2)
        sender.reset(9)
        sent = []
        colors = (0x123456,) * 64
        sender.offer(colors, lambda frame: sent.append(frame) or True, 0.0)
        for tick in (0.04, 0.08, 0.12, 0.16, 0.20):
            sender.service(lambda frame: sent.append(frame) or True, tick)
        sent.clear()
        sender.service(lambda frame: sent.append(frame) or True, 0.41)
        self.assertIsNotNone(sender.in_flight)
        self.assertEqual(sender.timeout_count, 1)
        decoded = self.messages(sent)
        self.assertEqual(decoded[0][2][6], 1, "unknown device state requires a full frame")

    def test_ack_keeps_the_context_of_the_frame_that_was_sent(self):
        sender = FrameSender(packet_gap_seconds=0.01)
        sender.reset(71)
        sent = []
        context = {"page": "session", "offset": "0,0", "valid_columns": "0,1,2,3"}
        sender.offer((0x224466,) * 64, lambda frame: sent.append(frame) or True,
                     1.0, force=True, context=context)
        for tick in (1.01, 1.02, 1.03, 1.04, 1.05):
            sender.service(lambda frame: sent.append(frame) or True, tick)
        frame_id = sender.in_flight["id"]
        sender.offer((0x6688AA,) * 64, lambda frame: sent.append(frame) or True,
                     1.06, context={"page": "track", "offset": "1,0"})
        self.assertTrue(sender.acknowledge(71, frame_id, 1, 1.07))
        self.assertEqual(sender.last_acknowledged["context"], context)
        self.assertEqual(sender.last_acknowledged["colors"], (0x224466,) * 64)

    def test_stale_ack_does_not_change_the_committed_base(self):
        sender = FrameSender()
        sender.reset(2)
        sender.offer((1,) * 64, lambda _frame: True, 0.0)
        frame_id = sender.in_flight["id"]
        self.assertFalse(sender.acknowledge(3, frame_id, 1, 0.1))
        self.assertFalse(sender.acknowledge(2, (frame_id + 1) & 0x3FFF, 1, 0.1))
        self.assertIsNone(sender.acknowledged_colors)

    def test_large_change_keeps_atomic_multi_packet_transaction(self):
        sender = FrameSender(packet_gap_seconds=0.01)
        sender.reset(27)
        sent = []
        send = lambda packet: sent.append(packet) or True
        initial = tuple([0] * 64)
        sender.offer(initial, send, 0.0, force=True)
        for tick in (0.01, 0.02, 0.03, 0.04, 0.05):
            sender.service(send, tick)
        first_id = sender.in_flight["id"]
        self.assertTrue(sender.acknowledge(27, first_id, 1, 0.06))
        latest = list(initial)
        for index in range(40):
            latest[index] = index + 1
        sent.clear()
        sender.offer(tuple(latest), send, 0.07)
        self.assertEqual(self.messages(sent)[0][0], FRAME_BEGIN,
                         "large changes stay in the existing atomic transaction")


    def test_large_repeated_color_change_uses_one_palette_packet(self):
        sender = FrameSender()
        sender.reset(27)
        sent = []
        send = lambda packet: sent.append(packet) or True
        initial = (0,) * 64
        sender.offer(initial, send, 0.0, force=True)
        for tick in (0.04, 0.08, 0.12, 0.16, 0.20):
            sender.service(send, tick)
        first_id = sender.in_flight["id"]
        self.assertTrue(sender.acknowledge(27, first_id, 1, 0.21))
        latest = list(initial)
        for index in range(24):
            latest[index] = 0xFF0000 if index % 2 else 0x220000
        sent.clear()
        sender.offer(tuple(latest), send, 0.24)
        self.assertEqual(self.messages(sent)[0][0], FRAME_PALETTE_DELTA)

    def test_palette_nack_disables_palette_for_session_and_recovers_with_full_frame(self):
        sender = FrameSender(packet_gap_seconds=0.01)
        sender.reset(271)
        sent = []
        send = lambda packet: sent.append(packet) or True
        sender.offer((0,) * 64, send, 0.0, force=True)
        for tick in (0.01, 0.02, 0.03, 0.04, 0.05):
            sender.service(send, tick)
        initial_id = sender.in_flight["id"]
        self.assertTrue(sender.acknowledge(271, initial_id, 1, 0.06))
        colors = [0] * 64
        for index in range(24):
            colors[index] = 0x220000 if index % 2 else 0xFF0000
        sent.clear()
        sender.offer(tuple(colors), send, 0.07)
        palette_id = sender.in_flight["id"]
        self.assertEqual(self.messages(sent)[0][0], FRAME_PALETTE_DELTA)
        self.assertTrue(sender.acknowledge(271, palette_id, 0, 0.08))
        sent.clear()
        sender.service(send, 0.09)
        decoded = self.messages(sent)
        self.assertEqual(decoded[0][0], FRAME_BEGIN)
        self.assertEqual(decoded[0][2][6], 1)
        self.assertTrue(sender.palette_disabled)


if __name__ == "__main__":
    unittest.main()
