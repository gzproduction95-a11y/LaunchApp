import unittest

try:
    import PythonApps.Launch.rendering as _rendering
    color_for_cell = _rendering.color_for_cell
    control_color_for_cell = getattr(_rendering, "control_color_for_cell", None)
    has_animated_state = _rendering.has_animated_state
except ImportError:
    color_for_cell = control_color_for_cell = has_animated_state = None
from PythonApps.Launch.state import (
    EMPTY, PLAYING, RECORDING, RECORD_END_QUEUED, STOPPED, STOP_QUEUED,
)
try:
    from PythonApps.Launch.state import LAUNCH_QUEUED
except ImportError:
    LAUNCH_QUEUED = 6


class RenderingTests(unittest.TestCase):
    def test_renderer_functions_are_available(self):
        self.assertTrue(callable(color_for_cell))
        self.assertTrue(callable(has_animated_state))

    def setUp(self):
        self.track = {
            "valid": True, "color": (64, 32, 16), "arm": False,
            "mute": False, "solo": False, "active": False,
        }
        self.slot = {"valid": True, "status": EMPTY}

    def render(self, row, phase=0, tempo=120, track=None, slot=None, page="track",
               column=0, scene=None, flash=False):
        return color_for_cell(
            page, row, track if track is not None else self.track,
            slot if slot is not None else self.slot, phase, tempo,
            column=column, scene=scene, flash=flash,
        )

    def test_track_controls_use_requested_live_switch_polarity_and_colors(self):
        self.assertEqual(self.render(4), 0x080000)
        self.track["arm"] = True
        self.assertEqual(self.render(4), 0xFF0000)
        self.track["arm"] = False
        self.assertEqual(self.render(5), 0xFFFF00)
        self.track["mute"] = True
        self.assertEqual(self.render(5), 0x080800)
        self.assertEqual(self.render(6), 0x000008)
        self.track["solo"] = True
        self.assertEqual(self.render(6), 0x0000FF)
        self.assertEqual(self.render(7), 0)
        self.track["active"] = True
        self.assertEqual(self.render(7), 0xFF0060)

    def test_missing_track_is_off_on_both_pages(self):
        missing = dict(self.track, valid=False)
        self.assertEqual(self.render(4, track=missing), 0)
        self.assertEqual(self.render(0, track=missing, page="session"), 0)

    def test_empty_slot_is_dim_and_stopped_clip_is_full_track_color(self):
        self.assertEqual(self.render(0, page="session"), 0x0C0603)
        self.slot["status"] = STOPPED
        self.assertEqual(self.render(0, page="session"), 0x804020)

    def test_playing_and_queued_breathing_share_phase_at_one_and_two_cycles_per_beat(self):
        self.slot["status"] = PLAYING
        playing = [self.render(0, phase=t, page="session") for t in (0, .25, .5, .75, 1)]
        self.assertGreater(playing[1], playing[0])
        self.assertEqual(playing[0], playing[4])

        self.slot["status"] = LAUNCH_QUEUED
        queued = [self.render(0, phase=t, page="session") for t in (0, .125, .25, .375, .5)]
        self.assertGreater(queued[1], queued[0])
        self.assertEqual(queued[0], queued[4])

    def test_armed_track_breathes_only_on_empty_slots_between_off_and_dim(self):
        self.track["arm"] = True
        self.slot["status"] = EMPTY
        samples = [self.render(0, phase=t, page="session") for t in (0, .5, 1)]
        self.assertGreater(max(samples), min(samples))
        self.assertEqual(min(samples), 0)
        self.assertLessEqual(max(samples), 0x0C0603)
        self.slot["status"] = STOPPED
        self.assertEqual(self.render(0, phase=.5, page="session"), 0x804020)
        self.slot["status"] = PLAYING
        self.assertEqual(self.render(0, phase=.5, page="session"),
                         self.render(0, phase=.5, track=dict(self.track, arm=False),
                                     page="session"))

    def test_armed_empty_breath_is_half_bpm_rate(self):
        self.track["arm"] = True
        self.slot["status"] = EMPTY
        samples = [self.render(0, phase=t, page="session") for t in (0, 1, 2)]
        self.assertEqual(samples[0], samples[2])
        self.assertNotEqual(samples[0], samples[1])

    def test_recording_remains_red_and_queued_states_animate(self):
        self.slot["status"] = RECORDING
        self.assertEqual(self.render(0, phase=.2, tempo=120, page="session"), 0xFF0000)
        self.slot["status"] = RECORD_END_QUEUED
        self.assertNotEqual(self.render(0, phase=0, page="session"), self.render(0, phase=.25, page="session"))
        self.slot["status"] = STOP_QUEUED
        self.assertNotEqual(self.render(0, phase=0, page="session"), self.render(0, phase=.25, page="session"))

    def test_scene_page_has_vertical_green_launch_and_red_stop_feedback(self):
        scene = {"valid": True, "active": False, "launch_queued": False,
                 "stop_queued": False}
        self.assertEqual(self.render(2, page="scene", column=7, scene=scene), 0x001000)
        self.assertEqual(self.render(2, page="scene", column=6, scene=scene), 0x100000)
        self.assertEqual(self.render(2, page="scene", column=5, scene=scene), 0)

        scene["active"] = True
        launch = [self.render(2, phase=t, page="scene", column=7, scene=scene)
                  for t in (0, .5, 1)]
        self.assertGreater(launch[1], launch[0])
        self.assertEqual(launch[0], launch[2])

        scene["stop_queued"] = True
        stop = [self.render(2, phase=t, page="scene", column=6, scene=scene)
                for t in (0, .25, .5)]
        self.assertGreater(stop[1], stop[0])
        self.assertEqual(stop[0], stop[2])
        self.assertLessEqual(max(stop), 0xFF0000)

    def test_unarmed_empty_slot_press_feedback_is_a_single_white_flash(self):
        self.assertEqual(self.render(0, phase=0, page="session", flash=True), 0xFFFFFF)
        self.assertEqual(self.render(0, phase=0, page="session", flash=False), 0x0C0603)
        self.track["arm"] = True
        self.assertNotEqual(self.render(0, phase=0, page="session", flash=True), 0xFFFFFF)
        self.slot["status"] = PLAYING
        self.track["arm"] = False
        self.assertNotEqual(self.render(0, phase=0, page="session", flash=True), 0xFFFFFF)

    def test_missing_scene_row_is_off_and_not_considered_animated(self):
        scene = {"valid": False, "active": False, "stop_queued": False}
        self.slot["status"] = EMPTY
        self.track["arm"] = True
        self.assertEqual(self.render(0, page="session", scene=scene), 0)
        tracks = [dict(self.track, arm=False) for _ in range(8)]
        tracks[0]["arm"] = True
        slots = [{"valid": True, "status": EMPTY} for _ in range(64)]
        scenes = [scene] + [{"valid": False} for _ in range(7)]
        self.assertFalse(has_animated_state("session", tracks, slots, scenes))

    def test_animation_tick_only_runs_when_a_visible_animation_exists(self):
        tracks = [dict(self.track, valid=False) for _ in range(8)]
        slots = [{"valid": True, "status": EMPTY} for _ in range(64)]
        self.assertFalse(has_animated_state(False, tracks, slots))
        tracks[0]["valid"] = True
        tracks[0]["arm"] = True
        self.assertTrue(has_animated_state(False, tracks, slots))
        self.assertFalse(has_animated_state(True, tracks, slots))

    def test_rec_length_fill_and_endpoint_lighting(self):
        self.assertTrue(callable(control_color_for_cell))
        self.assertEqual(control_color_for_cell(0, 0, 3, 0, 0, 8, 8), 0x0080FF)
        self.assertEqual(control_color_for_cell(0, 3, 3, 0, 0, 8, 8), 0x40C0FF)
        self.assertEqual(control_color_for_cell(1, 0, 4, 0, 0, 8, 8), 0x0080FF)
        self.assertEqual(control_color_for_cell(1, 1, 4, 0, 0, 8, 8), 0x40C0FF)
        self.assertEqual(control_color_for_cell(1, 0, 0, 0, 0, 8, 8), 0)
        self.assertEqual(control_color_for_cell(1, 2, 3, 0, 0, 8, 8), 0)

    def test_navigation_lights_follow_offsets_and_home(self):
        self.assertTrue(callable(control_color_for_cell))
        origin = lambda x, y: control_color_for_cell(y, x, 0, 0, 0, 8, 8)
        self.assertEqual(origin(5, 1), 0x001010)  # left disabled
        self.assertEqual(origin(6, 0), 0x001010)  # up disabled at baseline
        self.assertEqual(origin(6, 1), 0xFFFFFF)  # Home
        moved = lambda x, y: control_color_for_cell(y, x, 0, 4, 3, 12, 11)
        self.assertEqual(moved(5, 1), 0x00A0A0)
        self.assertEqual(moved(6, 0), 0x00A0A0)
        self.assertEqual(moved(7, 1), 0x001010)  # right at maximum
        self.assertEqual(moved(6, 2), 0x001010)  # down at maximum
        self.assertEqual(moved(6, 1), 0x4040FF)

    def test_page_jump_feedback_only_brightens_direction_cell(self):
        self.assertTrue(callable(control_color_for_cell))
        self.assertEqual(control_color_for_cell(1, 5, 0, 0, 0, 12, 12,
                                                feedback="left"), 0xFFFFFF)


if __name__ == "__main__":
    unittest.main()
