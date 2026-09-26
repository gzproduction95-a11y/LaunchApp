import unittest

from PythonApps.Launch.gestures import FnPageGesture


class FnPageGestureTests(unittest.TestCase):
    def setUp(self):
        self.gesture = FnPageGesture()

    def tap(self, start_ms, duration_ms=40):
        self.gesture.fn_press(start_ms)
        return self.gesture.fn_release(start_ms + duration_ms)

    def test_single_tap_enters_track_page_immediately(self):
        self.assertTrue(self.tap(100))
        self.assertEqual(self.gesture.page, "track")

    def test_quick_second_tap_enters_scene_page_without_second_single_action(self):
        self.tap(100)
        self.assertTrue(self.tap(200))
        self.assertEqual(self.gesture.page, "scene")

    def test_second_press_at_450ms_is_a_new_single_tap(self):
        self.tap(100)
        self.assertTrue(self.tap(590))  # 450 ms from first release at 140.
        self.assertEqual(self.gesture.page, "session")

    def test_second_press_at_449ms_is_double_but_at_451ms_is_single(self):
        self.tap(100)
        self.gesture.fn_press(589)  # 449 ms after release at 140.
        self.assertTrue(self.gesture.fn_release(620))
        self.assertEqual(self.gesture.page, "scene")

        self.gesture.fn_press(700)
        self.assertTrue(self.gesture.fn_release(740))  # new single from Scene
        self.assertEqual(self.gesture.page, "session")
        self.gesture.fn_press(1191)  # 451 ms after release at 740.
        self.assertTrue(self.gesture.fn_release(1230))
        self.assertEqual(self.gesture.page, "track")

    def test_pad_press_breaks_double_tap_pair(self):
        self.tap(100)
        self.gesture.pad_press()
        self.assertTrue(self.tap(200))
        self.assertEqual(self.gesture.page, "session")

    def test_pad_press_during_second_tap_makes_it_a_single_tap(self):
        self.tap(100)
        self.gesture.fn_press(200)
        self.gesture.pad_press()
        self.assertTrue(self.gesture.fn_release(240))
        self.assertEqual(self.gesture.page, "session")

    def test_third_tap_after_double_pair_starts_a_new_single(self):
        self.tap(100)
        self.tap(200)
        self.assertTrue(self.tap(300))
        self.assertEqual(self.gesture.page, "session")

    def test_fn_hold_over_three_seconds_does_not_toggle_on_release(self):
        self.gesture.fn_press(100)
        self.assertFalse(self.gesture.fn_release(3101))
        self.assertEqual(self.gesture.page, "session")

    def test_release_without_press_is_ignored(self):
        self.assertFalse(self.gesture.fn_release(100))
        self.assertEqual(self.gesture.page, "session")

    def test_duplicate_press_is_ignored(self):
        self.gesture.fn_press(100)
        self.gesture.fn_press(200)
        self.assertTrue(self.gesture.fn_release(240))
        self.assertEqual(self.gesture.page, "track")


if __name__ == "__main__":
    unittest.main()
