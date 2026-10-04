import importlib.util
import sys
import types
import unittest
from pathlib import Path

from PythonApps.Launch.protocol_v2 import (
    FRAME_ACK, FRAME_TABLE_BEGIN,
    FRAME_TABLE_COLOR_CHUNK, FRAME_TABLE_MAP_CHUNK, FRAME_TABLE_COMMIT,
    FRAME_SLOT_DELTA, LINK_ACK, LINK_HELLO, decode_frame,
    encode_frame, split_u14, split_u28,
)
from RemoteScripts.Launch.slot_stream import build_color_table, build_slot_delta

APP_DIR = Path(__file__).resolve().parents[2] / "PythonApps" / "Launch"


class Packet:
    def __init__(self, data):
        self._data = tuple(data)

    def is_sysex(self):
        return True

    def is_sysex_start(self):
        return False

    def data(self):
        return self._data


class V2DeviceRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.clock = [1000]
        self.sent = []
        self.led_updates = []
        self.logs = []
        self.input_events = []
        midi = types.SimpleNamespace(
            PORT_USB=1,
            send_sysex=lambda _port, data, _meta: self.sent.append(tuple(data)) or True,
            get=lambda _timeout: None,
        )
        matrixos = types.SimpleNamespace(
            Input=types.SimpleNamespace(
                function_key=lambda: (0, 99),
                clear=lambda: None,
                get_event=lambda _timeout: self.input_events.pop(0)
                if self.input_events else None,
            ),
            LED=types.SimpleNamespace(
                set_xy=lambda x, y, color: self.led_updates.append((x, y, color)),
                update=lambda: self.led_updates.append("commit"),
            ),
            MIDI=midi,
            SYS=types.SimpleNamespace(millis=lambda: self.clock[0]),
            Logging=types.SimpleNamespace(info=lambda *args: self.logs.append(args)),
        )
        self.saved = {name: sys.modules.get(name) for name in
                      ("MatrixOS", "protocol_v2", "display_receiver", "input_events")}
        sys.modules["MatrixOS"] = matrixos
        sys.path.insert(0, str(APP_DIR))
        spec = importlib.util.spec_from_file_location(
            "launch_device_v2_test_main", APP_DIR / "main_v2.py")
        self.app = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.app)
        self.app.startup()
        self.led_updates.clear()

    def tearDown(self):
        sys.path.remove(str(APP_DIR))
        for name, previous in self.saved.items():
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous

    def test_starts_new_protocol_and_forwards_raw_input_with_timestamp(self):
        hello = decode_frame(self.sent[-1])
        self.assertEqual(hello[0], LINK_HELLO)
        boot_id = hello[2]
        session = 0x12345
        self.app.handle_midi(Packet(encode_frame(
            LINK_ACK, 1, tuple(boot_id) + split_u28(session)) + (0xF7,)))
        self.assertTrue(self.app.connected)
        self.input_events.append({"id": (1, 4), "point": (5, 1),
                                  "keypad": {"pressed": True}})
        self.clock[0] = 1007
        self.app.loop()
        event = next(decode_frame(data) for data in reversed(self.sent)
                     if decode_frame(data) and decode_frame(data)[0] == self.app.INPUT_EVENT)
        self.assertEqual(event[2][0:4], split_u28(session))
        self.assertEqual(event[2][6:10], split_u28(1007))
        self.assertEqual(event[2][-2:], (5, 1))

    def test_only_applies_a_led_frame_after_atomic_commit(self):
        session = 22
        self.app.handle_midi(Packet(encode_frame(
            LINK_ACK, 2, split_u28(self.app.boot_id) + split_u28(session)) + (0xF7,)))
        slot_colors = tuple((index * 0x020406) & 0xFFFFFF for index in range(16))
        mapping = tuple(cell % 16 for cell in range(64))
        messages = build_color_table(session, 1, None, slot_colors, mapping)
        for message in messages[:-1]:
            self.app.handle_midi(Packet(message + (0xF7,)))
        self.assertEqual(self.led_updates, [])
        self.app.handle_midi(Packet(messages[-1] + (0xF7,)))
        expected = tuple(slot_colors[slot] for slot in mapping)
        self.assertEqual(self.app.frame_receiver.colors, expected)
        self.assertEqual(self.led_updates.count("commit"), 1)
        self.assertEqual(len([item for item in self.led_updates if item != "commit"]),
                         sum(color != 0 for color in expected))
        ack = decode_frame(self.sent[-1])
        self.assertEqual(ack[0], FRAME_ACK)
        self.assertEqual(ack[2], split_u28(session) + (0, 1, 1))

    def test_color_table_and_rgb_deltas_apply_atomically_on_device(self):
        session = 22
        self.app.handle_midi(Packet(encode_frame(
            LINK_ACK, 2, split_u28(self.app.boot_id) + split_u28(session)) + (0xF7,)))
        slot_colors = tuple(0x102030 + slot * 0x010101 for slot in range(16))
        mapping = tuple(cell % 16 for cell in range(64))
        messages = build_color_table(session, 1, None, slot_colors, mapping)
        self.assertEqual(decode_frame(messages[0])[0], FRAME_TABLE_BEGIN)
        self.assertEqual(decode_frame(messages[-1])[0], FRAME_TABLE_COMMIT)
        for message in messages[:-1]:
            self.app.handle_midi(Packet(message + (0xF7,)))
        self.assertEqual(self.led_updates, [])
        self.app.handle_midi(Packet(messages[-1] + (0xF7,)))
        expected = tuple(slot_colors[slot] for slot in mapping)
        self.assertEqual(self.app.frame_receiver.colors, expected)
        self.assertEqual(self.led_updates.count("commit"), 1)
        self.assertEqual([item[2] for item in self.led_updates if item != "commit"],
                         list(expected))
        self.led_updates.clear()
        updated = tuple((slot, 0xFF0000 + slot) for slot in range(6))
        delta = build_slot_delta(session, 2, 1, updated)
        self.assertEqual(decode_frame(delta)[0], FRAME_SLOT_DELTA)
        self.app.handle_midi(Packet(delta + (0xF7,)))
        for slot, color in updated:
            slot_colors = slot_colors[:slot] + (color,) + slot_colors[slot + 1:]
        expected = tuple(slot_colors[slot] for slot in mapping)
        self.assertEqual(self.app.frame_receiver.colors, expected)
        self.assertEqual(self.led_updates.count("commit"), 1)
        ack = decode_frame(self.sent[-1])
        self.assertEqual(ack[2], split_u28(session) + (0, 2, 1))

    def test_table_decoder_exception_is_nacked_and_device_loop_remains_connected(self):
        self.app.connected = True
        self.app.session_id = 0x12345
        self.app.frame_receiver.set_session(self.app.session_id)

        def fail_decode(_payload):
            raise OverflowError("simulated constrained-integer failure")
        self.app.frame_receiver._table_begin = fail_decode

        payload = (split_u28(self.app.session_id) + split_u14(19)
                   + split_u14(18) + (1, 2, 1, 2))
        packet = Packet(encode_frame(FRAME_TABLE_BEGIN, 4, payload) + (0xF7,))
        self.app.handle_midi(packet)

        response = decode_frame(self.sent[-1])
        self.assertEqual(response[0], FRAME_ACK)
        self.assertEqual(response[2], split_u28(self.app.session_id) + split_u14(19) + (0,))
        self.assertTrue(self.app.connected)
        self.assertEqual(self.app.session_id, 0x12345)
        self.assertTrue(any("display decode error" in item[-1] for item in self.logs))


if __name__ == "__main__":
    unittest.main()
