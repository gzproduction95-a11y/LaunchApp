import unittest

from PythonApps.Launch.controller import LaunchController


class LaunchControllerTests(unittest.TestCase):
    def setUp(self):
        self.controller = LaunchController((0, 99))

    @staticmethod
    def keypad_event(input_id, point, *, pressed=False, released=False):
        return {
            "id": input_id,
            "point": point,
            "keypad": {"pressed": pressed, "released": released},
        }

    def test_session_grid_press_maps_row_major_slot(self):
        actions = self.controller.handle_event(self.keypad_event((1, 4), (3, 6), pressed=True), 10)
        self.assertEqual(actions, [("grid", 51)])

    def test_grid_release_does_not_launch_again(self):
        actions = self.controller.handle_event(self.keypad_event((1, 4), (3, 6), released=True), 10)
        self.assertEqual(actions, [])

    def test_fn_single_enters_track_page_and_control_row_routes_track(self):
        fn = self.keypad_event((0, 99), None, pressed=True)
        self.assertEqual(self.controller.handle_event(fn, 10), [])
        fn_release = self.keypad_event((0, 99), None, released=True)
        self.assertEqual(self.controller.handle_event(fn_release, 40), [("page", "track")])
        actions = self.controller.handle_event(self.keypad_event((1, 4), (2, 4), pressed=True), 50)
        self.assertEqual(actions, [("track", 2, "arm")])

    def test_fn_double_from_any_page_enters_scene_page_and_routes_scene_columns(self):
        fn = self.keypad_event((0, 99), None, pressed=True)
        release = self.keypad_event((0, 99), None, released=True)
        self.controller.handle_event(fn, 10)
        self.assertEqual(self.controller.handle_event(release, 40), [("page", "track")])
        self.controller.handle_event(fn, 100)
        self.assertEqual(self.controller.handle_event(release, 130), [("page", "scene")])
        self.assertEqual(self.controller.handle_event(
            self.keypad_event((1, 4), (7, 5), pressed=True), 150), [("scene_launch", 5)])
        self.assertEqual(self.controller.handle_event(
            self.keypad_event((1, 4), (6, 5), pressed=True), 160), [("scene_stop", 5)])
        self.assertEqual(self.controller.handle_event(
            self.keypad_event((1, 4), (5, 5), pressed=True), 170), [])

    def test_fn_single_from_scene_returns_to_base_page(self):
        fn = self.keypad_event((0, 99), None, pressed=True)
        release = self.keypad_event((0, 99), None, released=True)
        self.controller.handle_event(fn, 10)
        self.controller.handle_event(release, 40)
        self.controller.handle_event(fn, 100)
        self.controller.handle_event(release, 130)
        self.assertEqual(self.controller.gesture.page, "scene")
        self.assertEqual(self.controller.handle_event(fn, 500), [])
        self.assertEqual(self.controller.handle_event(release, 540), [("page", "session")])

    def test_upper_track_page_pad_is_ignored_but_breaks_double_click(self):
        fn = self.keypad_event((0, 99), None, pressed=True)
        self.controller.handle_event(fn, 10)
        self.controller.handle_event(self.keypad_event((0, 99), None, released=True), 40)
        self.controller.handle_event(self.keypad_event((1, 4), (0, 0), pressed=True), 60)
        self.controller.handle_event(fn, 100)
        actions = self.controller.handle_event(self.keypad_event((0, 99), None, released=True), 120)
        self.assertEqual(actions, [("page", "session")])

    def test_quick_double_fn_enters_scene_page(self):
        fn = self.keypad_event((0, 99), None, pressed=True)
        release = self.keypad_event((0, 99), None, released=True)
        self.controller.handle_event(fn, 10)
        self.assertEqual(self.controller.handle_event(release, 40), [("page", "track")])
        self.controller.handle_event(fn, 100)
        self.assertEqual(self.controller.handle_event(release, 130), [("page", "scene")])
        self.assertEqual(self.controller.gesture.page, "scene")

    def test_track_page_rec_length_and_navigation_cells_route_separately(self):
        fn = self.keypad_event((0, 99), None, pressed=True)
        self.controller.handle_event(fn, 10)
        self.controller.handle_event(self.keypad_event((0, 99), None, released=True), 40)

        length = self.controller.handle_event(
            self.keypad_event((1, 4), (3, 1), pressed=True), 50)
        self.assertEqual(length, [("record_length", 8)])
        invalid = self.controller.handle_event(
            self.keypad_event((1, 4), (2, 1), pressed=True), 55)
        self.assertEqual(invalid, [])

        self.assertEqual(self.controller.handle_event(
            self.keypad_event((1, 4), (6, 0), pressed=True), 60),
            [("nav_preview", "up")])
        hold = self.keypad_event((1, 4), (6, 0))
        hold["keypad"]["hold"] = True
        self.assertEqual(self.controller.handle_event(hold, 470),
                         [("navigate", "up", 8)])
        release = self.keypad_event((1, 4), (6, 0), released=True)
        self.assertEqual(self.controller.handle_event(release, 480), [])

    def test_navigation_short_press_waits_for_release_and_home_is_one_action(self):
        fn = self.keypad_event((0, 99), None, pressed=True)
        self.controller.handle_event(fn, 10)
        self.controller.handle_event(self.keypad_event((0, 99), None, released=True), 40)

        left = self.keypad_event((1, 4), (5, 1), pressed=True)
        self.assertEqual(self.controller.handle_event(left, 100), [("nav_preview", "left")])
        self.assertEqual(self.controller.handle_event(
            self.keypad_event((1, 4), (5, 1), released=True), 150),
            [("navigate", "left", 1)])
        self.assertEqual(self.controller.handle_event(
            self.keypad_event((1, 4), (6, 1), pressed=True), 200),
            [("navigate", "home", 0)])


if __name__ == "__main__":
    unittest.main()
