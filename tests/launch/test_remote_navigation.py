import importlib
import types
import unittest
from unittest.mock import patch


class FakeSurface:
    def __init__(self, live):
        self._c_instance = live
        self.components = []

    @property
    def song(self):
        return self._c_instance.song

    def component_guard(self):
        from contextlib import nullcontext
        return nullcontext()

    def _register_component(self, component):
        self.components.append(component)

    def _send_midi(self, message):
        self._c_instance.midi_out.append(tuple(message))
        return True

    def schedule_message(self, *_args):
        pass


class FakeRing:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.offsets = None

    def set_offsets(self, track, scene):
        self.offsets = (track, scene)


class FakeLive:
    def __init__(self, tracks=12, scenes=11):
        self.logs = []
        self.midi_out = []
        self.highlights = []
        self.song = types.SimpleNamespace(
            tracks=[make_track() for _ in range(tracks)],
            scenes=[make_scene() for _ in range(scenes)],
            is_playing=False, current_song_time=0.0,
            signature_numerator=4, signature_denominator=4, tempo=120.0,
        )

    def log_message(self, message):
        self.logs.append(message)

    def set_session_highlight(self, *args):
        self.highlights.append(args)


def make_scene():
    scene = types.SimpleNamespace(is_triggered=False, fired=0)
    scene.fire = lambda scene=scene: setattr(scene, "fired", scene.fired + 1)
    return scene


def make_track():
    slots = []
    for _ in range(12):
        slot = types.SimpleNamespace(has_clip=False, is_group_slot=False, calls=[])
        slot.fire = lambda slot=slot, **kwargs: slot.calls.append(kwargs)
        slots.append(slot)
    track = types.SimpleNamespace(
        color=0x336699, arm=False, mute=False, solo=False,
        can_be_armed=True, playing_slot_index=-1, fired_slot_index=-1,
        clip_slots=slots,
    )
    track.stop_all_clips = lambda: None
    return track


class RemoteNavigationTests(unittest.TestCase):
    def setUp(self):
        self.module = importlib.import_module("RemoteScripts.Launch")
        self.old_bases = self.module.Launch.__bases__
        self.old_ring = self.module.SessionRingComponent
        self.module.Launch.__bases__ = (FakeSurface,)
        self.module.SessionRingComponent = FakeRing
        self.clock = [10.0]
        self.clock_patch = patch.object(self.module, "_clock", lambda: self.clock[0])
        self.clock_patch.start()

    def tearDown(self):
        self.clock_patch.stop()
        self.module.Launch.__bases__ = self.old_bases
        self.module.SessionRingComponent = self.old_ring

    def create_script(self, tracks=12, scenes=11):
        live = FakeLive(tracks, scenes)
        return live, self.module.create_instance(live)

    def complete_sync(self, live, script):
        script._link_active = True
        script._send_full_sync()
        for _ in range(100):
            self.clock[0] += 0.1
            script._service_full_sync(self.clock[0])
            task = script._sync_in_flight
            if task is None or not task["awaiting_ack"]:
                if script._active_sync_id is not None:
                    break
                continue
            sync_id = task["id"]
            if task["awaiting_final_ack"]:
                payload = self.module.split_u14(sync_id) + (1,)
            else:
                payload = (self.module.split_u14(sync_id)
                           + (2, task["expected_sequence"]))
            script.receive_midi(self.module.encode_frame(
                self.module.SYNC_ACK, 77, payload))
        self.assertIsNotNone(script._active_sync_id)
        sync_id = script._active_sync_id
        self.assertEqual(script._active_sync_id, sync_id)
        return sync_id

    def test_navigation_drives_registered_ring_clamps_page_jump_and_home(self):
        live, script = self.create_script()
        self.complete_sync(live, script)
        self.assertEqual(script._session_ring.offsets, (0, 0))
        self.assertTrue(script._navigate(2, 8))
        self.assertEqual(script._session_ring.offsets, (4, 0))
        self.assertEqual((script._track_offset, script._scene_offset), (4, 0))
        self.assertTrue(script._navigate(4, 8))
        self.assertEqual(script._session_ring.offsets, (4, 3))
        self.assertFalse(script._navigate(4, 1))
        self.assertTrue(script._navigate(5, 0))
        self.assertEqual(script._session_ring.offsets, (0, 0))

    def test_rec_length_toggles_off_and_survives_device_sync_but_not_script_reload(self):
        live, script = self.create_script()
        self.complete_sync(live, script)
        live.midi_out.clear()
        self.assertTrue(script._set_record_length(4, 0))
        self.assertEqual(script._record_length_code, 4)
        self.assertFalse(script._sync_pending)
        response = self.module.decode_frame(live.midi_out[-1])
        self.assertEqual(response[0], self.module.REC_LENGTH_STATE)
        self.assertEqual(response[2][-1], 4)
        self.assertTrue(script._set_record_length(4, 4))
        self.assertEqual(script._record_length_code, 0)
        _, reloaded = self.create_script()
        self.assertEqual(reloaded._record_length_code, 0)

    def test_fixed_record_length_is_passed_to_live_in_beats_for_new_empty_slot(self):
        live, script = self.create_script(tracks=8, scenes=8)
        self.complete_sync(live, script)
        live.song.tracks[0].arm = True
        live.song.signature_numerator = 3
        live.song.signature_denominator = 4
        script._record_length_code = 4  # Six Bars
        script._grid_press(0)
        self.assertEqual(live.song.tracks[0].clip_slots[0].calls,
                         [{"record_length": 18.0}], live.logs)

    def test_local_clip_and_track_actions_use_current_ring_track_offset(self):
        live, script = self.create_script(tracks=12, scenes=10)
        self.complete_sync(live, script)
        self.assertTrue(script._navigate(2, 8))
        self.clock[0] += 0.8
        self.complete_sync(live, script)
        live.song.tracks[11].arm = True
        script._grid_press(7)
        self.assertEqual(live.song.tracks[11].clip_slots[0].calls, [{}], live.logs)
        script._link_active = True
        live.song.tracks[7].arm = False
        frame = self.module.encode_frame(self.module.TRACK_ACTION, 3,
                                         (3, 1, 0, 4, 0, 0)
                                         + self.module.split_u14(script._active_sync_id))
        script.receive_midi(frame)
        self.assertTrue(live.song.tracks[7].arm)

    def test_protocol_actions_reject_old_window_and_scene_action_uses_offset(self):
        live, script = self.create_script(tracks=12, scenes=11)
        sync_id = self.complete_sync(live, script)
        script._link_active = True
        nav = self.module.encode_frame(self.module.NAVIGATION, 2,
                                       (4, 8, 0, 0, 0, 0)
                                       + self.module.split_u14(sync_id))
        script.receive_midi(nav)
        self.assertEqual((script._track_offset, script._scene_offset), (0, 3))
        stale = self.module.encode_frame(self.module.SCENE_ACTION, 3,
                                         (0, 1, 0, 0, 0, 0)
                                         + self.module.split_u14(sync_id))
        script.receive_midi(stale)
        self.assertEqual(live.song.scenes[3].fired, 0)
        self.clock[0] += 0.8
        self.complete_sync(live, script)
        action = self.module.encode_frame(self.module.SCENE_ACTION, 4,
                                          (5, 1, 0, 0, 0, 3)
                                          + self.module.split_u14(script._active_sync_id))
        script.receive_midi(action)
        self.assertEqual(live.song.scenes[8].fired, 1)

    def test_rapid_track_additions_update_window_metadata_without_full_snapshot(self):
        live, script = self.create_script(tracks=4)
        self.complete_sync(live, script)
        live.midi_out.clear()
        for _ in range(8):
            live.song.tracks.append(make_track())
            self.clock[0] += 0.25
            script._update_session_shape(live.song)
        self.clock[0] += 0.59
        script._service_full_sync(self.clock[0])
        messages = [self.module.decode_frame(item) for item in live.midi_out]
        self.assertEqual(sum(item[0] == self.module.SYNC_BEGIN for item in messages), 0)
        self.assertGreaterEqual(sum(item[0] == self.module.WINDOW_META for item in messages), 1)
        latest_meta = [item for item in messages if item[0] == self.module.WINDOW_META][-1]
        self.assertEqual(self.module.join_u14(*latest_meta[2][6:8]), 12)
        self.assertTrue(all(len(item[2]) <= 102 for item in messages
                            if item[0] == self.module.SYNC_DATA))

    def test_sync_frames_are_spaced_even_when_poll_callback_runs_immediately(self):
        live, script = self.create_script(tracks=8, scenes=8)
        script._link_active = True
        script._send_full_sync()
        self.clock[0] += 0.8
        script._service_full_sync(self.clock[0])
        self.assertEqual(len(live.midi_out), 1)
        script._service_full_sync(self.clock[0] + 1.0)
        self.assertEqual(len(live.midi_out), 1,
                         "Live must wait for the device to finish parsing this SysEx frame")
        first = self.module.decode_frame(live.midi_out[0])
        script.receive_midi(self.module.encode_frame(
            self.module.SYNC_ACK, 79,
            self.module.split_u14(script._sync_in_flight["id"])
            + (2, first[1])))
        script._service_full_sync(self.clock[0])
        self.assertEqual(len(live.midi_out), 1)
        self.clock[0] += self.module.SYNC_FRAME_INTERVAL_SECONDS - 0.001
        script._service_full_sync(self.clock[0])
        self.assertEqual(len(live.midi_out), 1)
        self.clock[0] += 0.002
        script._service_full_sync(self.clock[0])
        self.assertEqual(len(live.midi_out), 2)

    def test_sync_ack_for_old_shape_does_not_reactivate_controls(self):
        live, script = self.create_script(tracks=8, scenes=8)
        self.complete_sync(live, script)
        stale_id = script._active_sync_id
        live.song.tracks.insert(0, make_track())
        script._update_session_shape(live.song)
        self.clock[0] += 0.2
        for _ in range(100):
            self.clock[0] += 0.1
            script._service_full_sync(self.clock[0])
            task = script._sync_in_flight
            if task is None or not task["awaiting_ack"]:
                continue
            if task["awaiting_final_ack"]:
                break
            script.receive_midi(self.module.encode_frame(
                self.module.SYNC_ACK, 80,
                self.module.split_u14(task["id"])
                + (2, task["expected_sequence"])))
        self.assertIsNotNone(script._sync_in_flight)
        script.receive_midi(self.module.encode_frame(
            self.module.SYNC_ACK, 78, self.module.split_u14(stale_id) + (1,)))
        self.assertIsNone(script._active_sync_id)
        self.assertIsNotNone(script._sync_in_flight)
        self.assertFalse(script._sync_pending)

    def test_old_generation_action_is_rejected_after_track_insert_reorders_window(self):
        live, script = self.create_script(tracks=8)
        old_id = self.complete_sync(live, script)
        new_track = make_track()
        live.song.tracks.insert(0, new_track)
        script._update_session_shape(live.song)
        old_action = self.module.encode_frame(
            self.module.TRACK_ACTION, 90,
            (0, 1, 0, 0, 0, 0) + self.module.split_u14(old_id))
        script.receive_midi(old_action)
        self.assertFalse(new_track.arm)


if __name__ == "__main__":
    unittest.main()
