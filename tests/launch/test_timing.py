import unittest

import RemoteScripts.Launch.timing as timing
current_bar_end_boundary = timing.current_bar_end_boundary


class TimingTests(unittest.TestCase):
    def test_current_bar_end_is_after_press_and_exact_boundary_means_next_bar(self):
        self.assertEqual(current_bar_end_boundary(0.0, 4, 4), 4.0)
        self.assertEqual(current_bar_end_boundary(2.25, 4, 4), 4.0)
        self.assertEqual(current_bar_end_boundary(4.0, 4, 4), 8.0)

    def test_current_bar_end_uses_non_four_four_signatures(self):
        self.assertEqual(current_bar_end_boundary(7.2, 3, 4), 9.0)
        self.assertEqual(current_bar_end_boundary(3.5, 7, 8), 7.0)
        self.assertEqual(current_bar_end_boundary(4.0, 7, 8), 7.0)

    def test_rejects_invalid_time_or_signature(self):
        for values in ((0, 0, 4), (0, 4, 0), (-1, 4, 4)):
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    current_bar_end_boundary(*values)

    def test_fixed_recording_length_converts_bars_to_live_beats(self):
        self.assertTrue(hasattr(timing, "record_length_beats"))
        self.assertEqual(timing.record_length_beats(2, 4, 4), 8.0)
        self.assertEqual(timing.record_length_beats(4, 3, 4), 12.0)
        self.assertEqual(timing.record_length_beats(8, 7, 8), 28.0)

    def test_fixed_recording_length_rejects_unsupported_values(self):
        self.assertTrue(hasattr(timing, "record_length_beats"))
        for values in ((3, 4, 4), (2, 0, 4), (2, 4, 0)):
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    timing.record_length_beats(*values)


if __name__ == "__main__":
    unittest.main()
