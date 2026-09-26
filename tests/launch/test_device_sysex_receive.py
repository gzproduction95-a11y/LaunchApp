"""Exercise the device receiver with MatrixOS 4.0's actual SysEx packet API."""

import importlib.util
import sys
import types
import unittest
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[2] / "PythonApps" / "Launch"


class FirmwarePacket:
    def __init__(self, data):
        self._data = tuple(data)

    def is_sysex(self):
        return True

    def is_sysex_start(self):
        return False  # MatrixOS consumes the six-byte manufacturer header.

    def data(self):
        return self._data

    def status(self):
        # Firmware exposes data[0] as status, including for SysEx fragments.
        return self._data[0]

    def length(self):
        # Firmware's Python PacketLength returns 0 for data fragments.
        return 1 if self._data[0] == 0xF7 else 0


class DeviceSysExReceiveTests(unittest.TestCase):
    def test_ack_split_into_firmware_packets_requests_full_sync(self):
        from PythonApps.Launch.protocol import HELLO_ACK, HEARTBEAT, REQUEST_FULL_SYNC, encode, decode

        sent = []
        clock = [1000]
        input_events = []
        midi = types.SimpleNamespace(
            PORT_USB=1,
            STATUS_SYSEX_END=0xF7,
            send_sysex=lambda _port, data, _meta: sent.append(bytes(data)) or True,
            get=lambda _timeout: None,
        )
        matrixos = types.SimpleNamespace(
            Input=types.SimpleNamespace(function_key=lambda: (0, 99),
                                        get_event=lambda _timeout: input_events.pop(0)
                                        if input_events else None),
            LED=types.SimpleNamespace(set_xy=lambda *_args: None, update=lambda: None), MIDI=midi,
            SYS=types.SimpleNamespace(millis=lambda: clock[0]),
            Logging=types.SimpleNamespace(info=lambda *_args: None),
        )
        saved = {name: sys.modules.get(name) for name in
                 ("MatrixOS", "controller", "protocol", "state")}
        sys.modules["MatrixOS"] = matrixos
        sys.path.insert(0, str(APP_DIR))
        try:
            spec = importlib.util.spec_from_file_location("launch_device_test_main", APP_DIR / "main.py")
            app = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(app)
            frame = encode(HELLO_ACK, 1) + (0xF7,)
            for index in range(0, len(frame), 3):
                fragment = frame[index:index + 3]
                app.handle_midi(FirmwarePacket(fragment + (0,) * (3 - len(fragment))))
            self.assertTrue(app.connected)
            self.assertEqual(sent, [bytes(encode(REQUEST_FULL_SYNC, 1))])
            for index in range(0, len(frame), 3):
                fragment = frame[index:index + 3]
                app.handle_midi(FirmwarePacket(fragment + (0,) * (3 - len(fragment))))
            self.assertEqual(sent, [bytes(encode(REQUEST_FULL_SYNC, 1))],
                             "duplicate acknowledgement must not start another full sync")
            clock[0] = 2000
            app.loop()
            self.assertEqual(sent[-1], bytes(encode(HEARTBEAT, 2)),
                             "connected App must keep Live informed that it is still open")
            tempo_tenths = 1234
            phase_u14 = 6144
            frame = encode(HEARTBEAT, 3, (tempo_tenths >> 7, tempo_tenths & 0x7F,
                                          phase_u14 >> 7, phase_u14 & 0x7F, 1)) + (0xF7,)
            app.handle_midi(FirmwarePacket(frame))
            self.assertEqual(app.state.tempo, 123.4)
            self.assertAlmostEqual(app.state.phase_clock.phase_at(clock[0]), 1.5)
            # A USB SysEx end packet may contain one, two or three real bytes.
            for payload in ((), (7,), (7, 8)):
                app.connected = False
                frame = encode(HEARTBEAT, 2, payload) + (0xF7,)
                for index in range(0, len(frame), 3):
                    fragment = frame[index:index + 3]
                    app.handle_midi(FirmwarePacket(fragment + (0,) * (3 - len(fragment))))
                self.assertTrue(app.connected, "end packet alignment {}".format(len(payload)))

            from RemoteScripts.Launch.model import snapshot_payloads, pack_sync_records
            from PythonApps.Launch.protocol import (SYNC_BEGIN, SYNC_DATA, SYNC_END,
                                                    SYNC_ACK, WINDOW_META,
                                                    REC_LENGTH_STATE)

            records = snapshot_payloads(types.SimpleNamespace(tracks=[]))
            sync_id = 257
            hi, lo = divmod(sync_id, 128)
            frames = [encode(SYNC_BEGIN, 3, (hi, lo, len(records),
                                             0, 0, 0, 0, 0, 0, 0, 0, 0))]
            frames.extend(encode(SYNC_DATA, 4 + index, (hi, lo) + payload)
                          for index, payload in enumerate(pack_sync_records(records, 100)))
            frames.append(encode(SYNC_END, 7, (hi, lo)))
            for frame in frames:
                message = frame + (0xF7,)
                for index in range(0, len(message), 3):
                    fragment = message[index:index + 3]
                    app.handle_midi(FirmwarePacket(fragment + (0,) * (3 - len(fragment))))
            self.assertEqual(len(app.state._sync or {}), 0)
            self.assertTrue(all(slot["valid"] for slot in app.state.slots))
            self.assertEqual(app.state.sync_id, sync_id)
            self.assertEqual(decode(sent[-1])[0], SYNC_ACK)
            self.assertEqual(decode(sent[-1])[2], (hi, lo, 1))
            sync_acks = [decode(packet)[2] for packet in sent
                         if decode(packet) is not None and decode(packet)[0] == SYNC_ACK]
            self.assertEqual(len(sync_acks), len(frames))
            self.assertTrue(all(ack[2] == 2 for ack in sync_acks[:-1]))
            self.assertEqual(sync_acks[-1][2], 1)

            self.assertTrue(app.state.synced)
            window_meta = encode(WINDOW_META, 8, (hi, lo, 0, 0, 0, 0, 0, 12, 0, 8))
            app.handle_midi(FirmwarePacket(window_meta + (0xF7,)))
            self.assertEqual(app.state.track_count, 12)
            rec_length = encode(REC_LENGTH_STATE, 9, (hi, lo, 3))
            app.handle_midi(FirmwarePacket(rec_length + (0xF7,)))
            self.assertEqual(app.state.rec_length_code, 3)

            app.controller.gesture.page = "track"
            app.state.rec_length_code = 0
            input_events.append({"id": (1, 4), "point": (0, 0),
                                 "keypad": {"pressed": True}})
            app.loop()
            self.assertEqual(app.state.rec_length_code, 1,
                             "Rec Length preview must render locally on key press")
            self.assertEqual(decode(sent[-1])[0], 7)

            input_events.append({"id": (1, 4), "point": (5, 1),
                                 "keypad": {"pressed": True}})
            app.loop()
            self.assertEqual(app.nav_feedback, "left",
                             "Navigation key gets local press feedback before Live responds")
            bad_id = 258
            bad_hi, bad_lo = divmod(bad_id, 128)
            bad_frames = [encode(SYNC_BEGIN, 8, (bad_hi, bad_lo, len(records),
                                                0, 0, 0, 0, 0, 0, 0, 0, 0)),
                          encode(SYNC_END, 9, (bad_hi, bad_lo))]
            for frame in bad_frames:
                app.handle_midi(FirmwarePacket(frame + (0xF7,)))
            self.assertFalse(app.state.synced)
            self.assertEqual(decode(sent[-1])[2], (bad_hi, bad_lo, 0))

            for _ in range(100):
                app.handle_midi(FirmwarePacket((1, 2, 3)))
            self.assertLessEqual(len(app.sysex_buffer), 256,
                                 "missing F7 must not grow the MicroPython buffer forever")

            class OtherMidiPacket:
                def is_sysex(self):
                    return False

            pending = [OtherMidiPacket() for _ in range(12)]
            midi.get = lambda _timeout: pending.pop(0) if pending else None
            app.loop()
            self.assertEqual(len(pending), 4,
                             "each App loop should drain a bounded batch from the MIDI queue")
        finally:
            sys.path.remove(str(APP_DIR))
            for name, original in saved.items():
                if original is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = original


if __name__ == "__main__":
    unittest.main()
