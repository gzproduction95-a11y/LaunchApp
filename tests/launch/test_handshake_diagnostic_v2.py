import importlib
import sys
import types
import unittest
from contextlib import contextmanager


class FakeControlSurface:
    _active_guard = None

    def __init__(self, c_instance):
        self._c_instance = c_instance
        self.controls = []
        self.scheduled = []

    def _send_midi(self, message):
        return self._c_instance.send_midi(message)

    @contextmanager
    def component_guard(self):
        previous = FakeControlSurface._active_guard
        FakeControlSurface._active_guard = self
        try:
            yield
        finally:
            FakeControlSurface._active_guard = previous

    def _register_control(self, control):
        self.controls.append(control)

    def schedule_message(self, delay, callback, *args):
        self.scheduled.append((delay, callback, args))

    def deliver_sysex(self, message):
        for control in self.controls:
            header = control.kwargs["sysex_identifier"]
            if tuple(message[:len(header)]) == header:
                control.emit(tuple(message[len(header):-1]))
                return True
        return False


class FakeLive:
    def __init__(self):
        self.logs = []
        self.midi_out = []

    def log_message(self, message):
        self.logs.append(message)

    def send_midi(self, message):
        self.midi_out.append(tuple(message))
        return True


class FakeSysexElement:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.listeners = []
        FakeControlSurface._active_guard._register_control(self)

    def add_value_listener(self, callback):
        self.listeners.append(callback)

    def emit(self, value):
        for callback in self.listeners:
            callback(value)


class HandshakeDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.saved = {name: sys.modules.get(name) for name in (
            "ableton", "ableton.v2", "ableton.v2.control_surface",
            "ableton.v2.control_surface.elements", "RemoteScripts.LaunchHandshakeV2")}
        ableton = types.ModuleType("ableton")
        ableton.__path__ = []
        v2 = types.ModuleType("ableton.v2")
        v2.__path__ = []
        control = types.ModuleType("ableton.v2.control_surface")
        control.ControlSurface = FakeControlSurface
        elements = types.ModuleType("ableton.v2.control_surface.elements")
        elements.SysexElement = FakeSysexElement
        sys.modules.update({"ableton": ableton, "ableton.v2": v2,
                            "ableton.v2.control_surface": control,
                            "ableton.v2.control_surface.elements": elements})
        sys.modules.pop("RemoteScripts.LaunchHandshakeV2", None)
        self.module = importlib.import_module("RemoteScripts.LaunchHandshakeV2")

    def tearDown(self):
        sys.modules.pop("RemoteScripts.LaunchHandshakeV2", None)
        for name, value in self.saved.items():
            if value is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value

    def test_v8_diagnostic_acknowledges_and_displays_test_frame_only(self):
        live = FakeLive()
        script = self.module.create_instance(live)
        boot = 0x1234567
        hello = (self.module.MATRIXOS_SYSEX_HEADER
                 + self.module.encode_frame(self.module.LINK_HELLO, 1,
                                            self.module.split_u28(boot)) + (0xF7,))
        self.assertTrue(script.deliver_sysex(hello))
        decoded = [self.module.decode_frame(frame) for frame in live.midi_out]
        self.assertEqual([item[0] for item in decoded], [self.module.LINK_ACK],
                         "the handshake must not burst-send LED packets")
        self.assertEqual(decoded[0][2][:4], self.module.split_u28(boot))
        for _ in range(6):
            self.assertEqual(len(script.scheduled), 1)
            delay, callback, args = script.scheduled.pop(0)
            self.assertGreaterEqual(delay, 1)
            before = len(live.midi_out)
            callback(*args)
            self.assertEqual(len(live.midi_out), before + 1,
                             "each Live scheduler tick sends one LED packet")
        decoded = [self.module.decode_frame(frame) for frame in live.midi_out]
        self.assertEqual(decoded[1][0], self.module.FRAME_BEGIN)
        self.assertEqual(decoded[-1][0], self.module.FRAME_COMMIT)
        session = script._session_id
        ack = self.module.encode_frame(
            self.module.FRAME_ACK, 2,
            self.module.split_u28(session) + self.module.split_u14(0) + (1,))
        script.receive_midi(ack)
        self.assertTrue(any("acknowledged status=1" in line for line in live.logs))
        script.receive_midi(self.module.encode_frame(
            self.module.INPUT_EVENT, 3, (0,) * 14))
        self.assertTrue(any("ignored a raw control event" in line for line in live.logs))
        heartbeat = self.module.encode_frame(
            self.module.HEARTBEAT, 4, self.module.split_u28(session))
        script.receive_midi(heartbeat)
        self.assertEqual(self.module.decode_frame(live.midi_out[-1])[0],
                         self.module.HEARTBEAT)
        self.assertTrue(any("no Live actions" in line for line in live.logs))

    def test_link_only_diagnostic_sends_no_led_frame_or_live_action(self):
        try:
            link_module = importlib.import_module("RemoteScripts.LaunchLinkOnly")
        except ModuleNotFoundError:
            self.fail("the link-only diagnostic is missing")
        live = FakeLive()
        script = link_module.create_instance(live)
        boot = 0x1234567
        script.receive_midi(link_module.encode_frame(
            link_module.LINK_HELLO, 1, link_module.split_u28(boot)))
        decoded = [link_module.decode_frame(frame) for frame in live.midi_out]
        self.assertEqual([item[0] for item in decoded], [link_module.LINK_ACK])
        self.assertEqual(decoded[0][2][:4], link_module.split_u28(boot))
        self.assertTrue(any("no LED frames" in line for line in live.logs))

    def test_v7_frames_are_rejected_by_v8_diagnostic(self):
        live = FakeLive()
        script = self.module.create_instance(live)
        old = (0x4C, 0x41, 7, self.module.LINK_HELLO, 1, 0, 0)
        old += (sum(old[2:]) & 0x7F,)
        script.receive_midi(old)
        self.assertEqual(live.midi_out, [])


if __name__ == "__main__":
    unittest.main()
