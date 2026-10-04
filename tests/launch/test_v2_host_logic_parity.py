import importlib
import sys
import types
import unittest
from pathlib import Path

from PythonApps.Launch.controller import LaunchController as DeviceController
from PythonApps.Launch.phase import MusicalPhaseClock as DevicePhaseClock
from PythonApps.Launch.rendering import color_for_cell as device_color_for_cell
from RemoteScripts.Launch.controller import LaunchController as HostController
from RemoteScripts.Launch.phase import MusicalPhaseClock as HostPhaseClock
from RemoteScripts.Launch.rendering import color_for_cell as host_color_for_cell


class V2HostLogicParityTests(unittest.TestCase):
    def test_legacy_live_stop_quantization_uses_live_song_q_bar(self):
        live_api = types.ModuleType("Live")
        live_api.Song = types.SimpleNamespace(
            Quantization=types.SimpleNamespace(q_bar=4, q_half=5))
        previous_live = sys.modules.get("Live")
        previous_legacy = sys.modules.pop("RemoteScripts.Launch.legacy", None)
        sys.modules["Live"] = live_api
        try:
            legacy = importlib.import_module("RemoteScripts.Launch.legacy")
            self.assertEqual(legacy.BAR_LAUNCH_QUANTIZATION,
                             live_api.Song.Quantization.q_bar)
        finally:
            sys.modules.pop("RemoteScripts.Launch.legacy", None)
            if previous_legacy is not None:
                sys.modules["RemoteScripts.Launch.legacy"] = previous_legacy
            if previous_live is None:
                sys.modules.pop("Live", None)
            else:
                sys.modules["Live"] = previous_live

    def test_host_pure_logic_is_copied_exactly_from_v1_device_logic(self):
        root = Path(__file__).resolve().parents[2]
        names = ("controller.py", "gestures.py", "navigation.py", "phase.py",
                 "state.py")
        for name in names:
            with self.subTest(module=name):
                self.assertEqual((root / "PythonApps/Launch" / name).read_bytes(),
                                 (root / "RemoteScripts/Launch" / name).read_bytes())

    def test_fn_and_navigation_event_trace_matches_device_controller(self):
        device = DeviceController((0, 99))
        host = HostController((0, 99))
        events = [
            ({"id": (0, 99), "keypad": {"pressed": True}}, 10),
            ({"id": (0, 99), "keypad": {"released": True}}, 20),
            ({"id": (1, 4), "point": (7, 1), "keypad": {"pressed": True}}, 25),
            ({"id": (1, 4), "point": (7, 1), "keypad": {"hold": True}}, 900),
            ({"id": (1, 4), "point": (7, 1), "keypad": {"released": True}}, 910),
        ]
        for event, at_ms in events:
            self.assertEqual(device.handle_event(event, at_ms),
                             host.handle_event(event, at_ms))
        self.assertEqual(device.gesture.page, host.gesture.page)

    def test_host_renderer_matches_v1_for_static_track_controls(self):
        track = {"valid": True, "color": (127, 65, 3), "arm": True,
                 "mute": False, "solo": False, "active": True}
        slot = {"valid": True, "status": 1}
        for row in range(4, 8):
            args = ("track", row, track, slot, 0.0, 120.0)
            self.assertEqual(device_color_for_cell(*args), host_color_for_cell(*args))

    def test_phase_clock_matches_v1_extrapolation(self):
        device, host = DevicePhaseClock(), HostPhaseClock()
        for clock in (device, host):
            self.assertTrue(clock.update(8192, 123.4, True, 1000))
        for now in (1000, 1010, 1040, 2000, 0xFFFFFFFF):
            self.assertEqual(device.phase_at(now), host.phase_at(now))


if __name__ == "__main__":
    unittest.main()
