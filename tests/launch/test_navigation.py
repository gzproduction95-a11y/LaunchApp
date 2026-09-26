import unittest
import importlib.util
from pathlib import Path

_navigation_path = Path(__file__).resolve().parents[2] / "PythonApps" / "Launch" / "navigation.py"
_navigation_spec = (importlib.util.spec_from_file_location("launch_navigation", _navigation_path)
                    if _navigation_path.exists() else None)
_navigation = None
if _navigation_spec is not None and _navigation_spec.loader is not None:
    _navigation = importlib.util.module_from_spec(_navigation_spec)
    _navigation_spec.loader.exec_module(_navigation)


class NavigationHelpersTests(unittest.TestCase):
    def test_navigation_helper_module_exists(self):
        self.assertIsNotNone(_navigation, "Launch navigation helpers are not implemented")

    @unittest.skipIf(_navigation is None, "navigation helper module not implemented yet")
    def test_record_length_codes_round_trip_all_supported_values(self):
        self.assertEqual(_navigation.record_length_code(0), 0)
        for code, bars in enumerate(_navigation.BAR_OPTIONS, 1):
            self.assertEqual(_navigation.record_length_code(bars), code)
            self.assertEqual(_navigation.bars_for_code(code), bars)
        self.assertEqual(_navigation.bars_for_code(0), 0)

    @unittest.skipIf(_navigation is None, "navigation helper module not implemented yet")
    def test_record_length_uses_bar_duration_in_beats_for_time_signature(self):
        self.assertEqual(_navigation.beats_for_bars(2, 4, 4), 8.0)
        self.assertEqual(_navigation.beats_for_bars(2, 3, 4), 6.0)
        self.assertEqual(_navigation.beats_for_bars(2, 7, 8), 7.0)

    @unittest.skipIf(_navigation is None, "navigation helper module not implemented yet")
    def test_invalid_record_length_or_signature_is_rejected(self):
        with self.assertRaises(ValueError):
            _navigation.record_length_code(3)
        with self.assertRaises(ValueError):
            _navigation.bars_for_code(8)
        with self.assertRaises(ValueError):
            _navigation.beats_for_bars(4, 0, 4)

    @unittest.skipIf(_navigation is None, "navigation helper module not implemented yet")
    def test_offsets_clamp_to_last_full_or_partial_available_window(self):
        self.assertEqual(_navigation.clamp_offsets(-1, -3, 8, 4), (0, 0))
        self.assertEqual(_navigation.clamp_offsets(99, 99, 12, 11), (4, 3))
        self.assertEqual(_navigation.clamp_offsets(13, 3, 17, 12), (9, 3))

    @unittest.skipIf(_navigation is None, "navigation helper module not implemented yet")
    def test_viewport_local_coordinates_translate_to_live_indices(self):
        self.assertEqual(_navigation.viewport_target(7, 7, 4, 3, 12, 11), (11, 10))
        self.assertIsNone(_navigation.viewport_target(7, 7, 4, 3, 11, 10))
        self.assertIsNone(_navigation.viewport_target(8, 0, 0, 0, 8, 8))

    @unittest.skipIf(_navigation is None, "navigation helper module not implemented yet")
    def test_fourteen_bit_offsets_round_trip_without_seven_bit_overflow(self):
        for value in (0, 127, 128, 255, 16383):
            self.assertEqual(_navigation.join_u14(*_navigation.split_u14(value)), value)
        with self.assertRaises(ValueError):
            _navigation.split_u14(16384)
        with self.assertRaises(ValueError):
            _navigation.join_u14(128, 0)


if __name__ == "__main__":
    unittest.main()
