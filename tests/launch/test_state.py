import unittest
import inspect

from PythonApps.Launch.state import SessionState, EMPTY, PLAYING


class SessionStateTests(unittest.TestCase):
    def test_incremental_live_updates_change_committed_state_without_full_sync(self):
        state = SessionState()
        state.sync_id = 17

        self.assertTrue(state.apply_incremental(19, (0, 17, 2, 10, 20, 30)))
        self.assertTrue(state.apply_incremental(20, (0, 17, 2, 0b11011)))
        self.assertTrue(state.apply_incremental(21, (0, 17, 17, PLAYING)))

        self.assertEqual(state.tracks[2]["color"], (10, 20, 30))
        self.assertTrue(state.tracks[2]["arm"])
        self.assertTrue(state.tracks[2]["mute"])
        self.assertTrue(state.tracks[2]["active"])
        self.assertEqual(state.slots[17]["status"], PLAYING)

    def test_rejects_malformed_incremental_live_updates(self):
        state = SessionState()
        state.sync_id = 17

        self.assertFalse(state.apply_incremental(19, (0, 17, 9, 10, 20, 30)))
        self.assertFalse(state.apply_incremental(20, (0, 17, 2, 32)))
        self.assertFalse(state.apply_incremental(21, (0, 17, 64, PLAYING)))
        self.assertFalse(state.apply_incremental(99, ()))

    def test_incremental_scene_state_updates_presence_activity_and_queue(self):
        state = SessionState()
        state.sync_id = 17
        self.assertTrue(state.apply_incremental(25, (0, 17, 3, 7)))
        self.assertEqual(state.scenes[3], {
            "valid": True, "active": True, "stop_queued": True,
        })
        self.assertFalse(state.apply_incremental(25, (0, 17, 8, 1)))
        self.assertFalse(state.apply_incremental(25, (0, 17, 1, 8)))

    def test_applies_track_color_and_flags(self):
        state = SessionState()
        self.assertTrue(state.update_track_color(2, (10, 20, 30)))
        self.assertTrue(state.update_track_flags(2, 0b11011))
        track = state.tracks[2]
        self.assertEqual(track["color"], (10, 20, 30))
        self.assertTrue(track["valid"])
        self.assertTrue(track["arm"])
        self.assertTrue(track["mute"])
        self.assertFalse(track["solo"])
        self.assertTrue(track["active"])

    def test_rejects_out_of_range_track_and_slot_ids(self):
        state = SessionState()
        self.assertFalse(state.update_track_flags(8, 0))
        self.assertFalse(state.update_slot(64, PLAYING))
        self.assertFalse(state.update_slot(0, 99))

    def test_track_presence_is_explicit_and_launch_queue_is_a_valid_slot_state(self):
        state = SessionState()
        self.assertTrue(state.update_track_color(3, (1, 2, 3)))
        self.assertFalse(state.tracks[3]["valid"])
        self.assertTrue(state.update_track_flags(3, 16))
        self.assertTrue(state.tracks[3]["valid"])
        self.assertTrue(state.update_track_flags(3, 0))
        self.assertFalse(state.tracks[3]["valid"])
        self.assertTrue(state.update_slot(3, 6))
        self.assertEqual(state.slots[3]["status"], 6)
        self.assertFalse(state.update_track_flags(4, 32))

    def test_full_sync_commits_atomically_only_after_complete(self):
        state = SessionState()
        state.update_slot(0, PLAYING)
        self.assertTrue(state.begin_sync(7, 4))
        state.stage_track_color(0, (1, 2, 3))
        state.stage_track_flags(0, 17)
        self.assertFalse(state.end_sync(7))
        self.assertEqual(state.slots[0]["status"], PLAYING)
        self.assertIsNone(state._sync)
        self.assertTrue(state.begin_sync(8, 4))
        state.stage_slot(0, EMPTY)
        state.stage_scene(0, 1)
        state.stage_track_color(0, (1, 2, 3))
        state.stage_track_flags(0, 17)
        self.assertTrue(state.end_sync(8))
        self.assertEqual(state.slots[0]["status"], EMPTY)
        self.assertEqual(state.tracks[0]["color"], (1, 2, 3))
        self.assertTrue(state.scenes[0]["valid"])

    def test_sync_with_wrong_id_is_discarded(self):
        state = SessionState()
        state.begin_sync(3, 1)
        state.stage_slot(0, PLAYING)
        self.assertFalse(state.end_sync(4))
        self.assertEqual(state.slots[0]["status"], EMPTY)

    def test_full_sync_commits_viewport_and_record_length_metadata_atomically(self):
        state = SessionState()
        parameters = inspect.signature(state.begin_sync).parameters
        for name in ("track_offset", "scene_offset", "track_count",
                     "scene_count", "rec_length_code"):
            self.assertIn(name, parameters)
        self.assertTrue(state.begin_sync(11, 1, track_offset=128, scene_offset=3,
                                         track_count=136, scene_count=11,
                                         rec_length_code=4))
        state.stage_slot(0, PLAYING)
        self.assertEqual((state.track_offset, state.scene_offset,
                          state.track_count, state.scene_count,
                          state.rec_length_code), (0, 0, 0, 0, 0))
        self.assertTrue(state.end_sync(11))
        self.assertEqual((state.track_offset, state.scene_offset,
                          state.track_count, state.scene_count,
                          state.rec_length_code), (128, 3, 136, 11, 4))

    def test_sync_id_is_committed_as_the_action_generation(self):
        state = SessionState()
        self.assertTrue(state.begin_sync(129, 1))
        state.stage_slot(0, EMPTY)
        self.assertTrue(state.end_sync(129))
        self.assertEqual(state.sync_id, 129)
        self.assertFalse(state.begin_sync(16384, 1))

    def test_old_sync_end_does_not_discard_newer_staged_sync(self):
        state = SessionState()
        state.begin_sync(130, 1)
        state.stage_slot(0, PLAYING)
        self.assertFalse(state.end_sync(129))
        self.assertEqual(state._sync["id"], 130)

    def test_full_sync_rejects_invalid_view_metadata(self):
        state = SessionState()
        self.assertIn("track_offset", inspect.signature(state.begin_sync).parameters)
        self.assertFalse(state.begin_sync(1, 1, track_offset=16384))
        self.assertFalse(state.begin_sync(1, 1, scene_count=-1))
        self.assertFalse(state.begin_sync(1, 1, rec_length_code=8))
        self.assertFalse(state.begin_sync(1, 1, track_offset=5, track_count=10))
        self.assertFalse(state.begin_sync(1, 1, scene_offset=5, scene_count=10))

    def test_incrementals_are_ignored_until_viewport_sync_commits(self):
        state = SessionState()
        self.assertTrue(state.begin_sync(2, 1, track_count=8, scene_count=8))
        self.assertFalse(state.apply_incremental(21, (0, PLAYING)))
        self.assertEqual(state.slots[0]["status"], EMPTY)

    def test_window_metadata_updates_counts_without_invalidating_existing_mirror(self):
        state = SessionState()
        self.assertTrue(state.begin_sync(9, 1, 0, 0, 8, 8, 0))
        self.assertTrue(state.stage_track_flags(0, 16))
        self.assertTrue(state.end_sync(9))
        self.assertTrue(state.update_window_meta(9, 0, 0, 12, 8))
        self.assertEqual(state.track_count, 12)
        self.assertTrue(state.synced)
        self.assertFalse(state.update_window_meta(8, 0, 0, 13, 8))


if __name__ == "__main__":
    unittest.main()
