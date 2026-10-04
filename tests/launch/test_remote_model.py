import unittest
import inspect
from types import SimpleNamespace

from RemoteScripts.Launch.model import (
    snapshot_payloads, apply_track_action, pack_sync_records,
    collect_scene_targets, active_clip_in_track,
    EMPTY, STOPPED, PLAYING, RECORDING, STOP_QUEUED, RECORD_END_QUEUED,
    SCENE_PRESENT, SCENE_ACTIVE, SCENE_STOP_QUEUED,
    _slot_state,
)

LAUNCH_QUEUED = 6


class RemoteModelTests(unittest.TestCase):
    def setUp(self):
        self.clip = SimpleNamespace(is_playing=False, is_recording=False)
        self.slot = SimpleNamespace(has_clip=True, clip=self.clip, is_triggered=False)
        self.track = SimpleNamespace(color=0x336699, arm=False, mute=False, solo=False,
                                     playing_slot_index=-1, clip_slots=[self.slot],
                                     can_be_armed=True, stop_all_clips=lambda: setattr(self, "stopped", True))
        self.song = SimpleNamespace(tracks=[self.track], scenes=[object()])

    def test_snapshot_is_fixed_8_tracks_and_64_slots(self):
        messages = snapshot_payloads(self.song)
        self.assertEqual(len(messages), 88)
        self.assertEqual(messages[0], ("color", 0, (25, 51, 76)))
        self.assertEqual(next(record for record in messages
                              if record[:2] == ("slot", 63)), ("slot", 63, 0))

    def test_sync_chunks_fit_v5_data_frame_budget(self):
        chunks = pack_sync_records(snapshot_payloads(self.song))
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk) <= 46 for chunk in chunks))
        self.assertEqual(sum(len(chunk) for chunk in chunks), 280)

    def test_snapshot_maps_current_ring_window_to_local_ids(self):
        tracks = []
        scenes = []
        for track_index in range(12):
            slot = SimpleNamespace(has_clip=True, clip=SimpleNamespace(
                is_playing=False, is_recording=False), is_triggered=False)
            channel = track_index + 1
            color = (channel << 17) | (channel << 9) | (channel << 1)
            tracks.append(SimpleNamespace(color=color,
                                          arm=False, mute=False, solo=False,
                                          playing_slot_index=-1,
                                          clip_slots=[slot] * 12))
        for scene_index in range(12):
            scenes.append(object())
        song = SimpleNamespace(tracks=tracks, scenes=scenes, is_playing=True)

        parameters = inspect.signature(snapshot_payloads).parameters
        self.assertIn("track_offset", parameters)
        self.assertIn("scene_offset", parameters)
        messages = snapshot_payloads(song, track_offset=4, scene_offset=3)

        self.assertEqual(next(value for kind, index, value in messages
                              if kind == "color" and index == 0),
                         (5, 5, 5))
        self.assertEqual(next(value for kind, index, value in messages
                              if kind == "color" and index == 7),
                         (12, 12, 12))
        self.assertEqual(next(value for kind, index, value in messages
                              if kind == "slot" and index == 0), STOPPED)
        self.assertEqual(next(value for kind, index, value in messages
                              if kind == "scene" and index == 0), SCENE_PRESENT)

    def test_scene_snapshot_scans_all_tracks_and_marks_pending_stop(self):
        tracks = []
        for _ in range(9):
            clip = SimpleNamespace(is_playing=False, is_recording=False)
            slot = SimpleNamespace(has_clip=True, clip=clip)
            tracks.append(SimpleNamespace(clip_slots=[slot]))
        tracks[8].clip_slots[0].clip.is_playing = True
        song = SimpleNamespace(tracks=tracks, scenes=[object(), object()], is_playing=True)

        records = snapshot_payloads(song, scene_stop_queued=(0,))

        self.assertEqual(next(value for kind, index, value in records
                              if kind == "scene" and index == 0),
                         SCENE_PRESENT | SCENE_ACTIVE | SCENE_STOP_QUEUED)
        self.assertEqual(next(value for kind, index, value in records
                              if kind == "scene" and index == 1), SCENE_PRESENT)
        self.assertEqual(next(value for kind, index, value in records
                              if kind == "scene" and index == 2), 0)

    def test_scene_stop_targets_active_clips_across_all_tracks_only_in_requested_row(self):
        clips = []
        tracks = []
        for _ in range(9):
            row0 = SimpleNamespace(is_playing=False, is_recording=False)
            row1 = SimpleNamespace(is_playing=False, is_recording=False)
            slots = [SimpleNamespace(has_clip=True, clip=row0, is_group_slot=False),
                     SimpleNamespace(has_clip=True, clip=row1, is_group_slot=False)]
            tracks.append(SimpleNamespace(clip_slots=slots, playing_slot_index=-1))
            clips.extend((row0, row1))
        clips[0].is_playing = True
        clips[17].is_recording = True
        song = SimpleNamespace(tracks=tracks, scenes=[object(), object()], is_playing=True)

        targets = collect_scene_targets(song, 0)

        self.assertEqual([(target[0], target[1]) for target in targets], [(0, 0)])
        self.assertEqual(collect_scene_targets(song, 1)[0][:2], (8, 1))

    def test_active_clip_lookup_returns_currently_playing_clip_slot(self):
        active = SimpleNamespace(is_playing=True, is_recording=False)
        stopped = SimpleNamespace(is_playing=False, is_recording=False)
        track = SimpleNamespace(clip_slots=[
            SimpleNamespace(has_clip=True, clip=stopped),
            SimpleNamespace(has_clip=True, clip=active),
        ])
        target = active_clip_in_track(track)
        self.assertEqual(target[:2], (1, active))

    def test_track_actions_toggle_flags_and_stop_current_track(self):
        apply_track_action(self.song, 0, 1)
        self.assertTrue(self.track.arm)
        apply_track_action(self.song, 0, 2)
        self.assertTrue(self.track.mute)
        apply_track_action(self.song, 0, 3)
        self.assertTrue(self.track.solo)
        apply_track_action(self.song, 0, 4)
        self.assertTrue(self.stopped)

    def test_snapshot_marks_track_presence_and_uses_live_playing_slot_for_stop_row(self):
        self.track.playing_slot_index = 0
        flags = next(value for kind, index, value in snapshot_payloads(self.song)
                     if kind == "flags" and index == 0)
        self.assertTrue(flags & 16)
        self.assertTrue(flags & 8)
        absent = next(value for kind, index, value in snapshot_payloads(self.song)
                      if kind == "flags" and index == 1)
        self.assertEqual(absent, 0)

    def test_stopped_transport_displays_active_clip_as_stopped_and_clears_track_active(self):
        self.song.is_playing = False
        self.clip.is_playing = True
        self.track.playing_slot_index = 0

        messages = snapshot_payloads(self.song)

        self.assertEqual(next(value for kind, index, value in messages
                              if kind == "slot" and index == 0), STOPPED)
        flags = next(value for kind, index, value in messages
                     if kind == "flags" and index == 0)
        self.assertFalse(flags & 8)

        self.song.is_playing = True
        messages = snapshot_payloads(self.song)
        self.assertEqual(next(value for kind, index, value in messages
                              if kind == "slot" and index == 0), PLAYING)
        flags = next(value for kind, index, value in messages
                     if kind == "flags" and index == 0)
        self.assertTrue(flags & 8)

    def test_triggered_slots_distinguish_launch_stop_and_record_end_queue(self):
        self.slot.is_triggered = True
        self.assertEqual(_slot_state(self.track, 0, self.slot), LAUNCH_QUEUED)
        self.clip.is_playing = True
        self.assertEqual(_slot_state(self.track, 0, self.slot), STOP_QUEUED)
        self.track.fired_slot_index = 0
        self.assertEqual(_slot_state(self.track, 0, self.slot), LAUNCH_QUEUED)
        self.track.fired_slot_index = -2
        self.assertEqual(_slot_state(self.track, 0, self.slot), STOP_QUEUED)
        self.clip.is_playing = False
        self.clip.is_recording = True
        self.assertEqual(_slot_state(self.track, 0, self.slot), RECORD_END_QUEUED)

    def test_empty_triggered_slot_is_launch_queued_and_untriggered_empty_is_empty(self):
        self.slot.has_clip = False
        self.slot.clip = None
        self.slot.is_triggered = False
        self.assertEqual(_slot_state(self.track, 0, self.slot), EMPTY)
        self.slot.is_triggered = True
        self.assertEqual(_slot_state(self.track, 0, self.slot), LAUNCH_QUEUED)

    def test_empty_slot_triggered_during_count_in_is_queued_while_transport_stopped(self):
        self.song.is_playing = False
        self.slot.has_clip = False
        self.slot.clip = None
        self.slot.is_triggered = True

        self.assertEqual(_slot_state(self.track, 0, self.slot, transport_running=False),
                         LAUNCH_QUEUED)

    def test_invalid_track_action_is_ignored(self):
        apply_track_action(self.song, 0, 99)
        self.assertFalse(self.track.arm)

    def test_sync_chunks_are_bounded_and_do_not_split_records(self):
        records = snapshot_payloads(self.song)
        chunks = pack_sync_records(records, max_payload=15)
        self.assertTrue(all(len(chunk) <= 15 for chunk in chunks))
        rebuilt = []
        for chunk in chunks:
            index = 0
            while index < len(chunk):
                tag, record_id = chunk[index:index + 2]
                index += 2
                size = 3 if tag == 0 else 1
                rebuilt.append((tag, record_id, tuple(chunk[index:index + size])))
                index += size
            self.assertEqual(index, len(chunk))
        self.assertEqual(len(rebuilt), 88)


if __name__ == "__main__":
    unittest.main()
