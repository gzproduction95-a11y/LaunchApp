import unittest

from PythonApps.Launch.protocol_v2 import (FRAME_ACK, FRAME_TABLE_BEGIN,
    FRAME_TABLE_COLOR_CHUNK, FRAME_TABLE_MAP_CHUNK, FRAME_TABLE_COMMIT,
    FRAME_SLOT_DELTA)
from PythonApps.Launch.display_receiver import FrameReceiver
from RemoteScripts.Launch.protocol_v2 import decode_frame
from RemoteScripts.Launch.slot_stream import (assign_role_slots, build_color_table, build_slot_delta, build_table_patch)
from RemoteScripts.Launch.display_stream import build_frame
from RemoteScripts.Launch.rendering import color_for_cell, color_role_for_cell
from RemoteScripts.Launch.slot_sender import ColorTableSender


class V3ColorSlotTests(unittest.TestCase):
    def deliver(self, receiver, messages):
        result = None
        for message in messages:
            result = receiver.receive(decode_frame(message)) or result
        return result

    def test_render_roles_keep_dynamic_states_separate_from_current_rgb_values(self):
        track = {"valid": True, "color": (90, 40, 12), "arm": True}
        scene = {"valid": True}
        empty = {"valid": False, "status": 0}
        armed_role = color_role_for_cell("session", 1, 3, track, empty, scene)
        self.assertEqual(color_role_for_cell("session", 7, 3, track, empty, scene),
                         armed_role)
        recording = {"valid": True, "status": 3}
        recording_role = color_role_for_cell("session", 0, 3, track, recording, scene)
        self.assertNotEqual(recording_role, armed_role)
        prior = {}
        colors, mapping, allocated = assign_role_slots(
            (armed_role,) * 48 + (recording_role,) * 16,
            (0x101010,) * 48 + (0xFF0000,) * 16, prior)
        self.assertEqual(len(colors), 64)
        self.assertEqual(len(set(mapping)), 2)
        next_colors, next_mapping, next_allocated = assign_role_slots(
            (armed_role,) * 40 + (recording_role,) * 24,
            (0x202020,) * 40 + (0x0000FF,) * 24, allocated)
        self.assertEqual(next_mapping[:40], mapping[:40])
        self.assertEqual(next_mapping[40], mapping[48])
        self.assertEqual(next_colors[mapping[0]], 0x202020)
        self.assertEqual(next_colors[mapping[48]], 0x0000FF)

    def test_real_session_renderer_uses_at_most_sixteen_slots_for_eight_recording_tracks(self):
        track_colors = ((127, 23, 11), (9, 127, 31), (21, 41, 127),
                        (127, 103, 5), (91, 15, 107), (7, 99, 113),
                        (127, 55, 93), (61, 117, 13))
        roles_by_phase = []
        tables_by_phase = []
        mappings_by_phase = []
        previous = {}
        for phase in (0.0, 0.25, 0.5, 0.75):
            colors = []
            roles = []
            for row in range(8):
                for column in range(8):
                    track = {"valid": True, "arm": True,
                             "color": track_colors[column]}
                    is_recording = row == 0
                    slot = {"valid": is_recording,
                            "status": 3 if is_recording else 0}
                    scene = {"valid": True}
                    colors.append(color_for_cell(
                        "session", row, track, slot, phase, column=column,
                        scene=scene, arm_phase_beats=phase))
                    roles.append(color_role_for_cell(
                        "session", row, column, track, slot, scene))
            table, mapping, previous = assign_role_slots(roles, colors, previous)
            roles_by_phase.append(len(set(roles)))
            tables_by_phase.append(table)
            mappings_by_phase.append(mapping)
        self.assertEqual(roles_by_phase, [16] * 4)
        self.assertTrue(all(mapping == mappings_by_phase[0]
                            for mapping in mappings_by_phase))
        for before, after in zip(tables_by_phase, tables_by_phase[1:]):
            entries = tuple((slot, color) for slot, color in enumerate(after)
                            if color != before[slot])
            self.assertLessEqual(len(entries), 16)
            self.assertLessEqual(len(build_slot_delta(23, 2, 1, entries)) + 7, 102)

    def test_real_eight_track_recording_cycle_survives_sender_and_device_roundtrip(self):
        track_colors = ((127, 23, 11), (9, 127, 31), (21, 41, 127),
                        (127, 103, 5), (91, 15, 107), (7, 99, 113),
                        (127, 55, 93), (61, 117, 13))
        sender = ColorTableSender()
        sender.reset(23)
        receiver = FrameReceiver(23)
        sent = []
        due_acks = []
        now = 0.0

        def send(message):
            sent.append(message)
            ack = receiver.receive(decode_frame(message))
            if ack is not None:
                due_acks.append((now + 0.03, ack))
            return True

        def render(phase):
            colors = []
            roles = []
            for row in range(8):
                for column in range(8):
                    track = {"valid": True, "arm": True,
                             "color": track_colors[column]}
                    slot = {"valid": row == 0, "status": 3 if row == 0 else 0}
                    scene = {"valid": True}
                    colors.append(color_for_cell(
                        "session", row, track, slot, phase, column=column,
                        scene=scene, arm_phase_beats=phase))
                    roles.append(color_role_for_cell(
                        "session", row, column, track, slot, scene))
            table, mapping, render_roles = assign_role_slots(roles, colors, role_slots)
            role_slots.clear()
            role_slots.update(render_roles)
            return table, mapping, tuple(colors)

        role_slots = {}
        initial_table, initial_mapping, initial_colors = render(0.0)
        sender.install_table(initial_table, initial_mapping, send, now)
        for _ in range(20):
            now += 0.04
            sender.service(send, now)
            if due_acks and due_acks[0][0] <= now:
                _when, ack = due_acks.pop(0)
                sender.acknowledge(23, ack[1], ack[2], now)
                break
        self.assertIsNotNone(sender.acknowledged_slots)
        self.assertEqual(receiver.colors, initial_colors)
        sent.clear()

        for step in range(1, 51):
            now += 0.04
            while due_acks and due_acks[0][0] <= now:
                _when, ack = due_acks.pop(0)
                sender.acknowledge(23, ack[1], ack[2], now)
            table, mapping, frame = render(now * 2.0)
            sender.offer(table, mapping, send, now,
                         context={"render_at": now})
            self.assertEqual(receiver.colors, frame)
        self.assertGreaterEqual(sender.ack_count, 45)
        self.assertTrue(sent)
        self.assertTrue(all(decode_frame(message)[0] == FRAME_SLOT_DELTA
                            for message in sent))
        self.assertTrue(all(len(message) + 7 <= 102 for message in sent))
        self.assertEqual(sender.nack_count, 0)
        self.assertEqual(sender.timeout_count, 0)

    def test_full_color_table_is_bounded_and_commits_atomically(self):
        table = tuple(0x10203 * (slot + 1) & 0xFFFFFF for slot in range(16))
        mapping = tuple(cell % len(table) for cell in range(64))
        messages = build_color_table(23, 1, None, table, mapping)
        receiver = FrameReceiver(23)
        decoded = [decode_frame(message) for message in messages]
        self.assertEqual(decoded[0][0], FRAME_TABLE_BEGIN)
        self.assertEqual(decoded[-1][0], FRAME_TABLE_COMMIT)
        self.assertTrue(all(len(message) + 7 <= 102 for message in messages))
        self.assertEqual(receiver.colors, (0,) * 64)
        self.assertEqual(self.deliver(receiver, messages), (FRAME_ACK, 1, 1))
        self.assertEqual(receiver.colors,
                         tuple(table[slot] for slot in mapping))

    def test_identical_table_chunk_retransmission_is_ignored_and_can_commit(self):
        table = tuple(0x10101 * (slot + 1) for slot in range(16))
        mapping = tuple(cell % 16 for cell in range(64))
        messages = build_color_table(23, 1, None, table, mapping)
        receiver = FrameReceiver(23)
        for message in messages[:-1]:
            decoded = decode_frame(message)
            receiver.receive(decoded)
            if decoded[0] in (FRAME_TABLE_COLOR_CHUNK, FRAME_TABLE_MAP_CHUNK):
                self.assertIsNone(receiver.receive(decoded))
        self.assertEqual(receiver.receive(decode_frame(messages[-1])),
                         (FRAME_ACK, 1, 1))
        self.assertEqual(receiver.colors,
                         tuple(table[slot] for slot in mapping))

    def test_v11_device_receiver_source_fits_previously_working_file_budget(self):
        source = (__import__("pathlib").Path(__file__).resolve().parents[2]
                  / "PythonApps" / "Launch" / "display_receiver.py")
        self.assertLessEqual(source.stat().st_size, 9839,
                             "V2.1.1's 9839-byte receiver loaded on this device")

    def test_v11_device_receiver_ignores_obsolete_full_rgb_frame_messages(self):
        colors = tuple((cell * 0x030507) & 0xFFFFFF for cell in range(64))
        legacy_messages, _ = build_frame(23, 1, colors, None)
        receiver = FrameReceiver(23)
        self.assertIsNone(self.deliver(receiver, legacy_messages))
        self.assertEqual(receiver.colors, (0,) * 64)

    def test_incomplete_or_invalid_color_table_never_changes_display(self):
        old_table = (0x111111, 0x222222)
        old_mapping = tuple(cell % 2 for cell in range(64))
        receiver = FrameReceiver(23)
        first = build_color_table(23, 1, None, old_table, old_mapping)
        self.deliver(receiver, first)
        before = receiver.colors
        second = build_color_table(23, 2, 1, (0x333333, 0x444444),
                                   tuple((cell + 1) % 2 for cell in range(64)))
        self.assertIsNone(self.deliver(receiver, second[:-1]))
        self.assertEqual(receiver.colors, before)
        bad_map = list(second)
        message, seq, payload = decode_frame(bad_map[-2])
        bad_payload = list(payload)
        bad_payload[9] = 0
        from RemoteScripts.Launch.protocol_v2 import encode_frame
        bad_map[-2] = encode_frame(message, seq, bad_payload)
        self.assertEqual(self.deliver(receiver, bad_map), (FRAME_ACK, 2, 0))
        self.assertEqual(receiver.colors, before)

    def test_palette_and_mapping_patch_commits_as_one_visible_frame(self):
        colors = tuple(0x100000 + slot * 0x010203 for slot in range(16))
        mapping = tuple(cell % 8 for cell in range(64))
        receiver = FrameReceiver(23)
        self.deliver(receiver, build_color_table(23, 1, None, colors, mapping))
        changed_colors = tuple((slot, 0xFF0000 + slot) for slot in range(8, 14))
        changed_cells = tuple((track, 8 + track) for track in range(6))
        messages = build_table_patch(23, 2, 1, 16,
                                     changed_colors, changed_cells)
        self.assertEqual(len(messages), 4)
        self.assertTrue(all(len(message) + 7 <= 102 for message in messages))
        for message in messages[:-1]:
            self.assertIsNone(receiver.receive(decode_frame(message)))
        self.assertEqual(receiver.colors,
                         tuple(colors[mapping[cell]] for cell in range(64)))
        self.assertEqual(receiver.receive(decode_frame(messages[-1])),
                         (FRAME_ACK, 2, 1))
        expected_colors = list(colors)
        for slot, color in changed_colors:
            expected_colors[slot] = color
        expected_mapping = list(mapping)
        for cell, slot in changed_cells:
            expected_mapping[cell] = slot
        self.assertEqual(receiver.colors,
                         tuple(expected_colors[slot] for slot in expected_mapping))

    def test_mapping_only_patch_is_valid_and_atomic(self):
        colors = (0x020304, 0xA0B0C0)
        before = tuple(cell % 2 for cell in range(64))
        receiver = FrameReceiver(23)
        self.deliver(receiver, build_color_table(23, 1, None, colors, before))
        updated = tuple((cell, 1 - before[cell]) for cell in range(6))
        messages = build_table_patch(23, 2, 1, 2, (), updated)
        self.assertEqual(len(messages), 3)
        for message in messages[:-1]:
            self.assertIsNone(receiver.receive(decode_frame(message)))
        self.assertEqual(receiver.receive(decode_frame(messages[-1])),
                         (FRAME_ACK, 2, 1))
        after = list(before)
        for cell, slot in updated:
            after[cell] = slot
        self.assertEqual(receiver.colors, tuple(colors[slot] for slot in after))

    def test_rejected_slot_delta_resynchronizes_with_a_fresh_full_table(self):
        sender = ColorTableSender()
        sender.reset(23)
        receiver = FrameReceiver(23)
        sent = []
        pending = []
        now = 0.0
        table = tuple(0x120000 + slot for slot in range(16))
        mapping = tuple(cell % 16 for cell in range(64))
        def send(message):
            sent.append(message)
            ack = receiver.receive(decode_frame(message))
            if ack is not None:
                pending.append(ack)
            return True
        sender.install_table(table, mapping, send, now)
        for _ in range(20):
            now += 0.05
            sender.service(send, now)
            if pending:
                ack = pending.pop(0)
                sender.acknowledge(23, ack[1], ack[2], now)
                break
        self.assertIsNotNone(sender.acknowledged_colors)
        sent.clear()
        updated = list(table)
        updated[3] = 0xFEDCBA
        sender.offer(tuple(updated), mapping, send, now + 0.05)
        self.assertEqual(decode_frame(sent[-1])[0], FRAME_SLOT_DELTA)
        frame_id = sender.in_flight["id"]
        self.assertTrue(sender.acknowledge(23, frame_id, 0, now + 0.06))
        sent.clear()
        sender.service(send, now + 0.10)
        self.assertEqual(decode_frame(sent[0])[0], FRAME_TABLE_BEGIN)
        self.assertEqual(sender.in_flight["kind"], "table_full")

    def test_sixteen_color_slots_fit_one_rgb_delta(self):
        entries = tuple((slot, 0xABCDEF ^ slot) for slot in range(16))
        message = build_slot_delta(23, 2, 1, entries)
        self.assertEqual(decode_frame(message)[0], FRAME_SLOT_DELTA)
        self.assertEqual(len(message) + 7, 102)
        with self.assertRaises(ValueError):
            build_slot_delta(23, 2, 1, entries + ((16, 0),))

    def test_eight_armed_six_to_eight_recording_tracks_stream_one_packet_per_blink(self):
        for recording_count in (6, 7, 8):
            with self.subTest(recording_count=recording_count):
                sender = ColorTableSender()
                sender.reset(23)
                table = tuple(0x100000 + x * 0x010203 for x in range(16))
                mapping = []
                for row in range(8):
                    for track in range(8):
                        mapping.append(8 + track if row == 0 and track < recording_count
                                       else track)
                messages = []
                receiver = FrameReceiver(23)
                pending_acks = []
                def send(message):
                    messages.append(message)
                    ack = receiver.receive(decode_frame(message))
                    if ack is not None:
                        pending_acks.append(ack)
                    return True
                now = 0.0
                sender.install_table(table, tuple(mapping), send, now)
                for _ in range(16):
                    now += 0.04
                    sender.service(send, now)
                    if pending_acks:
                        ack = pending_acks.pop(0)
                        sender.acknowledge(23, ack[1], ack[2], now)
                        break
                self.assertIsNotNone(sender.acknowledged_slots)
                messages.clear()
                for phase in (0, 0.5, 1.0, 1.5):
                    with self.subTest(phase=phase):
                        colors = list(table)
                        for track in range(recording_count):
                            colors[8 + track] = (0xFF0000 if phase % 1.0 < 0.5
                                                 else table[track])
                        sender.offer(tuple(colors), tuple(mapping), send, now + 0.04)
                        self.assertEqual(len(messages), 1)
                        self.assertEqual(decode_frame(messages[-1])[0], FRAME_SLOT_DELTA)
                        ack = pending_acks.pop(0)
                        sender.acknowledge(23, ack[1], ack[2], now + 0.05)
                        self.assertEqual(receiver.colors,
                                         tuple(colors[slot] for slot in mapping))
                        now += 0.05
                        messages.clear()


if __name__ == '__main__':
    unittest.main()
