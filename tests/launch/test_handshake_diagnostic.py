import importlib
import sys
import types
import unittest
from contextlib import contextmanager
from unittest.mock import patch


class FakeControlSurface:
    _active_guard = None

    def __init__(self, c_instance):
        self._c_instance = c_instance
        self.controls = []

    @property
    def song(self):
        return self._c_instance.song

    def _send_midi(self, message):
        return self._c_instance.send_midi(message)

    def schedule_message(self, *_args):
        pass

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

    def disconnect(self):
        for control in self.controls:
            control.reset()

    def deliver_sysex(self, message):
        for control in self.controls:
            identifier = control.kwargs["sysex_identifier"]
            if tuple(message[:len(identifier)]) == identifier:
                # Live's registered SysEx control receives the bytes between
                # its identifier and the final F7.
                control.emit(tuple(message[len(identifier):-1]))
                return True
        return False


class FakeLiveInstance:
    def __init__(self):
        self.logs = []
        self.midi_out = []
        self.song = types.SimpleNamespace(
            tracks=[], scenes=[types.SimpleNamespace() for _ in range(8)],
            is_playing=False, current_song_time=0.0,
            signature_numerator=4, signature_denominator=4, tempo=120.0)

    def log_message(self, message):
        self.logs.append(message)

    def send_midi(self, message):
        self.midi_out.append(tuple(message))
        return True


class RewrappingLiveObject:
    """A Live-like proxy whose wrapper changes while its underlying object does not."""
    def __init__(self, value, identity):
        self._value = value
        self._identity = identity

    def __getattr__(self, name):
        value = getattr(self._value, name)
        if name in ("tracks", "scenes", "clip_slots"):
            return [RewrappingLiveObject(item, (name, index, id(item)))
                    for index, item in enumerate(value)]
        if name == "clip" and value is not None:
            return RewrappingLiveObject(value, ("clip", id(value)))
        return value

    def __eq__(self, other):
        return (isinstance(other, RewrappingLiveObject)
                and self._identity == other._identity)


class FakeInputControlElement:
    def __init__(self, message_type, **kwargs):
        owner = FakeControlSurface._active_guard
        if owner is None:
            raise RuntimeError("Required dependency send_midi not provided")
        self.message_type = message_type
        self.kwargs = kwargs
        self.listeners = []
        owner._register_control(self)

    def add_value_listener(self, callback):
        self.listeners.append(callback)

    def emit(self, value):
        for callback in self.listeners:
            callback(value)

    def reset(self):
        raise NotImplementedError("generic SysEx input cannot send a reset value")


class FakeSysexElement(FakeInputControlElement):
    def __init__(self, **kwargs):
        super().__init__("sysex", **kwargs)

    def reset(self):
        pass


class HandshakeDiagnosticTests(unittest.TestCase):
    def _complete_production_sync(self, production, script, live, clock):
        script.receive_midi(production.encode_frame(production.REQUEST_FULL_SYNC, 1, ()))
        for _ in range(100):
            clock[0] += 0.1
            script._service_full_sync(clock[0])
            task = script._sync_in_flight
            if task is None or not task["awaiting_ack"]:
                if script._active_sync_id is not None:
                    return script._active_sync_id
                continue
            if task["awaiting_final_ack"]:
                payload = production.split_u14(task["id"]) + (1,)
            else:
                payload = (production.split_u14(task["id"])
                           + (2, task["expected_sequence"]))
            script.receive_midi(production.encode_frame(
                production.SYNC_ACK, 2, payload))
        self.fail("production sync did not reach its device-ack phase")

    def setUp(self):
        self.original = {name: sys.modules.get(name) for name in (
            "ableton", "ableton.v2", "ableton.v2.control_surface",
            "ableton.v2.control_surface.elements",
            "RemoteScripts.LaunchHandshake",
        )}
        ableton = types.ModuleType("ableton")
        ableton.__path__ = []
        v2 = types.ModuleType("ableton.v2")
        v2.__path__ = []
        control_surface = types.ModuleType("ableton.v2.control_surface")
        control_surface.ControlSurface = FakeControlSurface
        control_surface.InputControlElement = FakeInputControlElement
        control_surface.MIDI_SYSEX_TYPE = "sysex"
        elements = types.ModuleType("ableton.v2.control_surface.elements")
        elements.SysexElement = FakeSysexElement
        sys.modules.update({
            "ableton": ableton,
            "ableton.v2": v2,
            "ableton.v2.control_surface": control_surface,
            "ableton.v2.control_surface.elements": elements,
        })
        sys.modules.pop("RemoteScripts.LaunchHandshake", None)
        self.module = importlib.import_module("RemoteScripts.LaunchHandshake")

    def tearDown(self):
        sys.modules.pop("RemoteScripts.LaunchHandshake", None)
        for name, original in self.original.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original

    def test_responds_to_handshake_and_full_sync_without_live_actions(self):
        live = FakeLiveInstance()
        script = self.module.create_instance(live)
        hello = self.module.MATRIXOS_SYSEX_HEADER + self.module.encode_frame(self.module.HELLO, 1) + (0xF7,)
        request = self.module.MATRIXOS_SYSEX_HEADER + self.module.encode_frame(self.module.REQUEST_FULL_SYNC, 2) + (0xF7,)
        self.assertTrue(script.deliver_sysex(hello))
        self.assertTrue(script.deliver_sysex(request))
        script.receive_midi(self.module.encode_frame(self.module.GRID_PRESS, 3, (0,)))
        script.receive_midi(self.module.encode_frame(self.module.TRACK_ACTION, 4, (0, 4)))

        decoded = [self.module.decode_frame(message) for message in live.midi_out]
        self.assertEqual([item[0] for item in decoded], [self.module.HELLO_ACK,
                         self.module.SYNC_BEGIN, self.module.SYNC_DATA,
                         self.module.SYNC_END])
        self.assertEqual(decoded[1][2], (0, 1, 2, 0, 0, 0, 0, 0, 8, 0, 8, 0))
        self.assertEqual(decoded[2][2], (0, 1, 0, 0, 64, 0, 64, 1, 0, 16))
        self.assertEqual(decoded[3][2], (0, 1))
        self.assertTrue(any("initialized" in line for line in live.logs))
        self.assertTrue(any("ignored" in line for line in live.logs))

    def test_registers_live_sysex_receiver_for_matrixos_launch_frames(self):
        live = FakeLiveInstance()
        script = self.module.create_instance(live)
        self.assertEqual(script._sysex_input.message_type, "sysex")
        self.assertEqual(script._sysex_input.kwargs["sysex_identifier"],
                         self.module.SYSEX_IDENTIFIER)
        self.assertEqual(self.module.SYSEX_IDENTIFIER,
                         self.module.MATRIXOS_SYSEX_HEADER)
        self.assertEqual(len(script._sysex_input.listeners), 1)
        self.assertIn(script._sysex_input, script.controls)

    def test_production_launch_registers_same_live_sysex_receiver(self):
        previous = sys.modules.pop("RemoteScripts.Launch", None)
        try:
            production = importlib.import_module("RemoteScripts.Launch")
            live = FakeLiveInstance()
            script = production.create_instance(live)
            self.assertIsNotNone(script._sysex_input)
            self.assertEqual(script._sysex_input.kwargs["sysex_identifier"],
                             production.SYSEX_IDENTIFIER)
            self.assertIn(script._sysex_input, script.controls)
            codec = importlib.import_module("RemoteScripts.Launch.protocol")
            hello = codec.MATRIXOS_SYSEX_HEADER + production.encode_frame(
                production.HELLO, 1, ()) + (0xF7,)
            self.assertTrue(script.deliver_sysex(hello))
            self.assertEqual(codec.decode_frame(live.midi_out[0])[0],
                             production.HELLO_ACK)
            script.disconnect()
        finally:
            sys.modules.pop("RemoteScripts.Launch", None)
            if previous is not None:
                sys.modules["RemoteScripts.Launch"] = previous

    def test_production_launch_uses_live_song_property_for_sync_and_poll(self):
        previous = sys.modules.pop("RemoteScripts.Launch", None)
        try:
            production = importlib.import_module("RemoteScripts.Launch")
            live = FakeLiveInstance()
            live.song.tempo = 123.4
            live.song.tracks = [types.SimpleNamespace(
                color=0x404040, arm=False, mute=False, solo=False, clip_slots=[])]
            script = production.create_instance(live)
            codec = importlib.import_module("RemoteScripts.Launch.protocol")
            clock = [1.0]
            with patch.object(production, "_clock", lambda: clock[0], create=True):
                self._complete_production_sync(production, script, live, clock)
                generation = production.split_u14(script._active_sync_id)
                self.assertTrue(script.deliver_sysex(
                    codec.MATRIXOS_SYSEX_HEADER + codec.encode_frame(
                        production.GRID_PRESS, 2, (0, 0, 0, 0, 0) + generation) + (0xF7,)))
                script.receive_midi(codec.encode_frame(
                    production.TRACK_ACTION, 3, (0, 4, 0, 0, 0, 0) + generation))
                script.receive_midi(codec.encode_frame(
                    production.HEARTBEAT, 4, ()))
                for _ in range(4):
                    clock[0] += 0.1
                    script._poll()
            messages = [codec.decode_frame(value)[0] for value in live.midi_out]
            self.assertIn(production.SYNC_END, messages)
            self.assertIn(production.HEARTBEAT, messages)
            heartbeat = next(codec.decode_frame(value) for value in live.midi_out
                             if codec.decode_frame(value)[0] == production.HEARTBEAT)
            tempo_tenths = 1234
            self.assertEqual(heartbeat[2][:2], (tempo_tenths >> 7, tempo_tenths & 0x7F))
            self.assertEqual(len(heartbeat[2]), 5)
            self.assertFalse(any("failed" in line for line in live.logs))
        finally:
            sys.modules.pop("RemoteScripts.Launch", None)
            if previous is not None:
                sys.modules["RemoteScripts.Launch"] = previous

    def test_production_launch_sends_nothing_before_device_requests_sync(self):
        previous = sys.modules.pop("RemoteScripts.Launch", None)
        try:
            production = importlib.import_module("RemoteScripts.Launch")
            live = FakeLiveInstance()
            script = production.create_instance(live)
            for _ in range(5):
                script._poll()
            self.assertEqual(live.midi_out, [])
        finally:
            sys.modules.pop("RemoteScripts.Launch", None)
            if previous is not None:
                sys.modules["RemoteScripts.Launch"] = previous

    def test_production_launch_sends_only_changed_track_after_action(self):
        previous = sys.modules.pop("RemoteScripts.Launch", None)
        try:
            production = importlib.import_module("RemoteScripts.Launch")
            live = FakeLiveInstance()
            track = types.SimpleNamespace(color=0x404040, can_be_armed=True,
                                          arm=False, mute=False, solo=False, clip_slots=[])
            live.song.tracks = [track]
            script = production.create_instance(live)
            codec = importlib.import_module("RemoteScripts.Launch.protocol")
            clock = [1.0]
            with patch.object(production, "_clock", lambda: clock[0], create=True):
                sync_id = self._complete_production_sync(production, script, live, clock)
            live.midi_out.clear()
            script.receive_midi(codec.encode_frame(
                production.TRACK_ACTION, 2, (0, 1, 0, 0, 0, 0)
                + production.split_u14(sync_id)))
            self.assertTrue(track.arm)
            messages = [codec.decode_frame(value)[0] for value in live.midi_out]
            self.assertEqual(messages, [production.TRACK_STATE])
        finally:
            sys.modules.pop("RemoteScripts.Launch", None)
            if previous is not None:
                sys.modules["RemoteScripts.Launch"] = previous

    def test_production_launch_stops_output_after_device_goes_silent(self):
        previous = sys.modules.pop("RemoteScripts.Launch", None)
        try:
            production = importlib.import_module("RemoteScripts.Launch")
            live = FakeLiveInstance()
            clock = [0.0]
            with patch.object(production, "_clock", lambda: clock[0], create=True):
                script = production.create_instance(live)
                script.receive_midi(production.encode_frame(production.REQUEST_FULL_SYNC, 1, ()))
                live.midi_out.clear()
                clock[0] = 4.0
                for _ in range(5):
                    script._poll()
                self.assertEqual(live.midi_out, [])
        finally:
            sys.modules.pop("RemoteScripts.Launch", None)
            if previous is not None:
                sys.modules["RemoteScripts.Launch"] = previous

    def test_production_launch_keeps_link_with_device_heartbeats_and_coalesces_sync(self):
        previous = sys.modules.pop("RemoteScripts.Launch", None)
        try:
            production = importlib.import_module("RemoteScripts.Launch")
            live = FakeLiveInstance()
            clock = [0.0]
            with patch.object(production, "_clock", lambda: clock[0], create=True):
                script = production.create_instance(live)
                self._complete_production_sync(production, script, live, clock)
                script.receive_midi(production.encode_frame(production.REQUEST_FULL_SYNC, 2, ()))
                script.receive_midi(production.encode_frame(production.REQUEST_FULL_SYNC, 3, ()))
                codec = importlib.import_module("RemoteScripts.Launch.protocol")
                types_sent = [codec.decode_frame(value)[0] for value in live.midi_out]
                self.assertEqual(types_sent.count(production.SYNC_BEGIN), 1)
                live.midi_out.clear()
                for second in (1.0, 2.0, 3.0, 4.0):
                    clock[0] = second
                    script.receive_midi(production.encode_frame(production.HEARTBEAT, int(second), ()))
                    script._poll()
                types_sent = [codec.decode_frame(value)[0] for value in live.midi_out]
                self.assertEqual(types_sent, [production.HEARTBEAT])
        finally:
            sys.modules.pop("RemoteScripts.Launch", None)
            if previous is not None:
                sys.modules["RemoteScripts.Launch"] = previous

    def test_production_scene_launch_uses_native_scene_fire_and_scene_stop_targets_row(self):
        previous = sys.modules.pop("RemoteScripts.Launch", None)
        try:
            production = importlib.import_module("RemoteScripts.Launch")
            live = FakeLiveInstance()

            def make_track(active_row=None, recording_row=None):
                slots = []
                for row in range(2):
                    clip = types.SimpleNamespace(
                        is_playing=(row == active_row),
                        is_recording=(row == recording_row),
                        playing_position=0.0,
                        looping=False,
                    )
                    slot = types.SimpleNamespace(
                        has_clip=True, clip=clip, is_group_slot=False,
                        stopped=False,
                    )
                    slot.stop = lambda slot=slot: setattr(slot, "stopped", True)
                    clip.stop = lambda slot=slot: setattr(slot, "stopped", True)
                    slots.append(slot)
                stop = types.SimpleNamespace(has_clip=False, has_stop_button=True,
                                             is_group_slot=False, calls=[])
                stop.fire = lambda stop=stop, **kwargs: stop.calls.append(kwargs)
                slots.append(stop)
                track = types.SimpleNamespace(
                    color=0, arm=False, mute=False, solo=False,
                    playing_slot_index=active_row if active_row is not None else -1,
                    fired_slot_index=-1, can_be_armed=True, clip_slots=slots,
                    stop_calls=[],
                )
                track.stop_all_clips = lambda quantized=True, track=track: \
                    track.stop_calls.append(quantized)
                return track

            live.song.tracks = [make_track(active_row=0), make_track(recording_row=0)] + [
                make_track() for _ in range(7)] + [make_track(active_row=0)]
            live.song.scenes = [types.SimpleNamespace(fired=0, is_triggered=False),
                                types.SimpleNamespace(fired=0, is_triggered=False)]
            for scene in live.song.scenes:
                scene.fire = lambda scene=scene: setattr(scene, "fired", scene.fired + 1)
            live.song.is_playing = True
            live.song.current_song_time = 1.0
            live.song.signature_numerator = 4
            live.song.signature_denominator = 4
            live.song.tempo = 120.0

            script = production.create_instance(live)
            self.assertTrue(script._scene_action(0, 1))
            self.assertEqual(live.song.scenes[0].fired, 1)
            live.song.scenes[0].is_triggered = True
            self.assertFalse(script._scene_action(0, 1))
            self.assertEqual(live.song.scenes[0].fired, 1)
            live.song.scenes[0].is_triggered = False
            self.assertTrue(script._scene_action(0, 2))
            task = script._bar_pending[("scene", 0)]
            self.assertEqual([(target["track_index"], target["slot_index"])
                              for target in task["targets"]], [(0, 0), (1, 0), (9, 0)])
            self.assertEqual(live.song.tracks[1].clip_slots[0].clip.is_recording, True)
            script._process_bar_pending(live.song)
            self.assertEqual([track.stop_calls for track in live.song.tracks[:2]],
                             [[], []])
            live.song.current_song_time = 4.0
            with patch.object(production, "_clock", return_value=1.5):
                script._process_bar_pending(live.song)
            self.assertEqual(live.song.tracks[0].stop_calls, [False])
            self.assertEqual(live.song.tracks[1].stop_calls, [False])
            self.assertFalse(live.song.tracks[0].clip_slots[1].stopped)
            self.assertEqual(live.song.tracks[9].stop_calls, [False])
            self.assertNotIn(("scene", 0), script._bar_pending)
        finally:
            sys.modules.pop("RemoteScripts.Launch", None)
            if previous is not None:
                sys.modules["RemoteScripts.Launch"] = previous

    def test_scene_stop_targets_active_scene_without_requiring_empty_stop_slots(self):
        previous = sys.modules.pop("RemoteScripts.Launch", None)
        try:
            production = importlib.import_module("RemoteScripts.Launch")
            live = FakeLiveInstance()

            def make_track(active_row):
                slots = []
                for row in range(3):
                    clip = types.SimpleNamespace(
                        is_playing=(row == active_row),
                        is_recording=False,
                    )
                    slots.append(types.SimpleNamespace(
                        has_clip=True, clip=clip, is_group_slot=False,
                    ))
                track = types.SimpleNamespace(
                    playing_slot_index=active_row, fired_slot_index=-1,
                    clip_slots=slots, stopped_calls=[],
                )
                def stop_all_clips(quantized=True):
                    track.stopped_calls.append(quantized)
                    for slot in track.clip_slots:
                        slot.clip.is_playing = False
                        slot.clip.is_recording = False
                track.stop_all_clips = stop_all_clips
                return track

            live.song.tracks = [make_track(0), make_track(2), make_track(0)]
            live.song.scenes = [object(), object(), object()]
            live.song.is_playing = True
            live.song.current_song_time = 5.0
            live.song.signature_numerator = 4
            live.song.signature_denominator = 4
            script = production.create_instance(live)

            self.assertTrue(script._scene_action(0, 2))
            task = script._bar_pending[("scene", 0)]
            self.assertEqual(task["target_time"], 8.0)
            self.assertEqual([target["track_index"] for target in task["targets"]],
                             [0, 2])
            self.assertTrue(all(target["mode"] == "scene_scheduler"
                                for target in task["targets"]))
            script._process_bar_pending(live.song)
            self.assertEqual([track.stopped_calls for track in live.song.tracks],
                             [[], [], []])

            live.song.current_song_time = 8.0
            simulated_now = task["previous_sample_at"] + 1.5
            with patch.object(production, "_clock", return_value=simulated_now):
                script._process_bar_pending(live.song)
            self.assertEqual([track.stopped_calls for track in live.song.tracks],
                             [[False], [], [False]])
            self.assertNotIn(("scene", 0), script._bar_pending)
        finally:
            sys.modules.pop("RemoteScripts.Launch", None)
            if previous is not None:
                sys.modules["RemoteScripts.Launch"] = previous

    def test_unarmed_empty_slot_queues_current_clip_for_current_bar_end_and_repeated_press_is_ignored(self):
        previous = sys.modules.pop("RemoteScripts.Launch", None)
        try:
            production = importlib.import_module("RemoteScripts.Launch")
            live = FakeLiveInstance()
            active_clip = types.SimpleNamespace(
                is_playing=True, is_recording=False, playing_position=1.0,
                looping=True,
            )
            active_slot = types.SimpleNamespace(has_clip=True, clip=active_clip,
                                                is_group_slot=False, stopped=False)
            active_clip.stop = lambda: setattr(active_slot, "stopped", True)
            empty_slot = types.SimpleNamespace(has_clip=False, is_group_slot=False,
                                               has_stop_button=True, calls=[])
            empty_slot.fire = lambda **kwargs: empty_slot.calls.append(kwargs)
            track = types.SimpleNamespace(
                arm=False, playing_slot_index=0, fired_slot_index=-1,
                clip_slots=[active_slot, empty_slot],
            )
            live.song.tracks = [track]
            live.song.scenes = [object(), object()]
            live.song.is_playing = True
            live.song.current_song_time = 1.0
            live.song.signature_numerator = 4
            live.song.signature_denominator = 4
            live.song.tempo = 120.0
            script = production.create_instance(live)

            script._grid_press(8)
            task = script._bar_pending[("slot", 0, 0)]
            self.assertIs(task["targets"][0]["clip"], active_clip)
            self.assertEqual(empty_slot.calls, [{"launch_quantization": 5}])
            live.song.current_song_time = 2.0
            script._grid_press(8)
            self.assertEqual(empty_slot.calls, [{"launch_quantization": 5}])
            self.assertFalse(active_slot.stopped)
        finally:
            sys.modules.pop("RemoteScripts.Launch", None)
            if previous is not None:
                sys.modules["RemoteScripts.Launch"] = previous

    def test_current_bar_stop_fails_safely_when_track_has_no_empty_stop_button(self):
        previous = sys.modules.pop("RemoteScripts.Launch", None)
        try:
            production = importlib.import_module("RemoteScripts.Launch")
            live = FakeLiveInstance()
            clip = types.SimpleNamespace(is_playing=True, is_recording=False)
            active = types.SimpleNamespace(has_clip=True, clip=clip,
                                           is_group_slot=False)
            empty = types.SimpleNamespace(has_clip=False, is_group_slot=False,
                                          has_stop_button=False)
            track = types.SimpleNamespace(arm=False, playing_slot_index=0,
                                          fired_slot_index=-1,
                                          clip_slots=[active, empty])
            live.song.tracks = [track]
            live.song.scenes = [object(), object()]
            live.song.is_playing = True
            script = production.create_instance(live)

            script._grid_press(8)

            self.assertFalse(script._bar_pending)
            self.assertTrue(any("has no empty Stop Button slot" in line
                                for line in live.logs))
            self.assertTrue(clip.is_playing)
        finally:
            sys.modules.pop("RemoteScripts.Launch", None)
            if previous is not None:
                sys.modules["RemoteScripts.Launch"] = previous

    def test_scene_stop_survives_fresh_python_wrappers_for_same_live_objects(self):
        previous = sys.modules.pop("RemoteScripts.Launch", None)
        previous_base = sys.modules.get("ableton.v2.base")
        base = types.ModuleType("ableton.v2.base")
        base.liveobj_changed = lambda first, second: first != second
        base.liveobj_valid = lambda value: value is not None
        sys.modules["ableton.v2.base"] = base
        try:
            production = importlib.import_module("RemoteScripts.Launch")
            live = FakeLiveInstance()
            stopped = []
            clip = types.SimpleNamespace(is_playing=True, is_recording=False)
            clip.stop = lambda: stopped.append("clip")
            slot = types.SimpleNamespace(has_clip=True, clip=clip, is_group_slot=False)
            stop_slot = types.SimpleNamespace(has_clip=False, has_stop_button=True,
                                              is_group_slot=False, calls=[])
            stop_slot.fire = lambda **kwargs: stop_slot.calls.append(kwargs)
            track = types.SimpleNamespace(
                arm=False, playing_slot_index=0, fired_slot_index=-1,
                clip_slots=[slot, stop_slot],
                stopped_calls=[],
            )
            track.stop_all_clips = lambda quantized=True: track.stopped_calls.append(quantized)
            song = types.SimpleNamespace(
                tracks=[track], scenes=[object()], is_playing=True,
                current_song_time=1.0, signature_numerator=4,
                signature_denominator=4, tempo=120.0,
            )
            live.song = RewrappingLiveObject(song, ("song", id(song)))
            script = production.create_instance(live)
            self.assertTrue(script._scene_action(0, 2))
            task = script._bar_pending[("scene", 0)]
            script._process_bar_pending(live.song)
            self.assertEqual(stop_slot.calls, [])
            self.assertTrue(script._bar_pending)
            live.song.current_song_time = 4.0
            with patch.object(production, "_clock", return_value=1.5):
                script._process_bar_pending(live.song)
            self.assertEqual(track.stopped_calls, [False])
            self.assertNotIn(("scene", 0), script._bar_pending)
        finally:
            sys.modules.pop("RemoteScripts.Launch", None)
            sys.modules.pop("ableton.v2.base", None)
            if previous_base is not None:
                sys.modules["ableton.v2.base"] = previous_base
            if previous is not None:
                sys.modules["RemoteScripts.Launch"] = previous

    def test_unarmed_empty_slot_stop_survives_fresh_python_wrappers(self):
        previous = sys.modules.pop("RemoteScripts.Launch", None)
        previous_base = sys.modules.get("ableton.v2.base")
        base = types.ModuleType("ableton.v2.base")
        base.liveobj_changed = lambda first, second: first != second
        base.liveobj_valid = lambda value: value is not None
        sys.modules["ableton.v2.base"] = base
        try:
            production = importlib.import_module("RemoteScripts.Launch")
            live = FakeLiveInstance()
            stopped = []
            clip = types.SimpleNamespace(is_playing=True, is_recording=False)
            clip.stop = lambda: stopped.append("clip")
            active_slot = types.SimpleNamespace(
                has_clip=True, clip=clip, is_group_slot=False,
            )
            empty_slot = types.SimpleNamespace(has_clip=False, is_group_slot=False,
                                               has_stop_button=True, calls=[])
            empty_slot.fire = lambda **kwargs: empty_slot.calls.append(kwargs)
            track = types.SimpleNamespace(
                arm=False, playing_slot_index=0, fired_slot_index=-1,
                clip_slots=[active_slot, empty_slot],
            )
            song = types.SimpleNamespace(
                tracks=[track], scenes=[object(), object()], is_playing=True,
                current_song_time=1.0, signature_numerator=4,
                signature_denominator=4, tempo=120.0,
            )
            live.song = RewrappingLiveObject(song, ("song", id(song)))
            script = production.create_instance(live)
            script._grid_press(8)
            task = script._bar_pending[("slot", 0, 0)]
            script._process_bar_pending(live.song)
            self.assertEqual(empty_slot.calls, [{"launch_quantization": 5}])
            self.assertTrue(script._bar_pending)
        finally:
            sys.modules.pop("RemoteScripts.Launch", None)
            sys.modules.pop("ableton.v2.base", None)
            if previous_base is not None:
                sys.modules["ableton.v2.base"] = previous_base
            if previous is not None:
                sys.modules["RemoteScripts.Launch"] = previous

    def test_live_native_bar_stop_survives_transport_changes_and_clears_replaced_target(self):
        previous = sys.modules.pop("RemoteScripts.Launch", None)
        try:
            production = importlib.import_module("RemoteScripts.Launch")
            clock = [0.0]
            with patch.object(production, "_clock", lambda: clock[0]):
              for change in ("seek", "signature", "replacement", "tempo"):
                with self.subTest(change=change):
                    clock[0] = 0.0
                    live = FakeLiveInstance()
                    clip = types.SimpleNamespace(is_playing=True, is_recording=False)
                    slot = types.SimpleNamespace(has_clip=True, clip=clip, is_group_slot=False)
                    stop = types.SimpleNamespace(has_clip=False, has_stop_button=True,
                                                 is_group_slot=False, calls=[])
                    stop.fire = lambda stop=stop, **kwargs: stop.calls.append(kwargs)
                    track = types.SimpleNamespace(playing_slot_index=0, fired_slot_index=-1,
                                                  clip_slots=[slot, stop])
                    live.song.tracks = [track]
                    live.song.scenes = [object()]
                    live.song.is_playing = True
                    live.song.current_song_time = 1.0
                    live.song.signature_numerator = 4
                    live.song.signature_denominator = 4
                    live.song.tempo = 120.0
                    script = production.create_instance(live)
                    self.assertTrue(script._scene_action(0, 2))
                    if change == "seek":
                        live.song.current_song_time = 1.5
                    elif change == "signature":
                        live.song.current_song_time = 1.1
                        live.song.signature_numerator = 3
                    elif change == "tempo":
                        live.song.current_song_time = 1.1
                        live.song.tempo = 90.0
                    elif change == "replacement":
                        replacement = types.SimpleNamespace(is_playing=True,
                                                            is_recording=False)
                        slot.clip = replacement
                    if change != "seek":
                        live.song.current_song_time = 1.2
                    clock[0] = 0.1
                    script._process_bar_pending(live.song)
                    if change in ("replacement", "seek", "signature"):
                        self.assertNotIn(("scene", 0), script._bar_pending)
                    else:
                        self.assertIn(("scene", 0), script._bar_pending, live.logs)
        finally:
            sys.modules.pop("RemoteScripts.Launch", None)
            if previous is not None:
                sys.modules["RemoteScripts.Launch"] = previous

    def test_empty_slot_stop_ignores_stopped_transport_and_cancels_newly_started_clip(self):
        previous = sys.modules.pop("RemoteScripts.Launch", None)
        try:
            production = importlib.import_module("RemoteScripts.Launch")
            live = FakeLiveInstance()
            old_clip = types.SimpleNamespace(is_playing=True, is_recording=False)
            new_clip = types.SimpleNamespace(is_playing=True, is_recording=False)
            old_slot = types.SimpleNamespace(has_clip=True, clip=old_clip,
                                             is_group_slot=False)
            new_slot = types.SimpleNamespace(has_clip=True, clip=new_clip,
                                             is_group_slot=False)
            empty_slot = types.SimpleNamespace(has_clip=False, is_group_slot=False,
                                               has_stop_button=True, calls=[])
            empty_slot.fire = lambda **kwargs: empty_slot.calls.append(kwargs)
            track = types.SimpleNamespace(arm=False, playing_slot_index=0,
                                          fired_slot_index=-1,
                                          clip_slots=[old_slot, new_slot, empty_slot])
            live.song.tracks = [track]
            live.song.scenes = [object(), object(), object()]
            live.song.is_playing = False
            live.song.current_song_time = 1.0
            live.song.signature_numerator = 4
            live.song.signature_denominator = 4
            live.song.tempo = 120.0
            script = production.create_instance(live)
            script._grid_press(16)
            self.assertFalse(script._bar_pending)

            live.song.is_playing = True
            script._grid_press(16)
            self.assertIn(("slot", 0, 0), script._bar_pending)
            track.playing_slot_index = 1
            old_clip.is_playing = True
            new_clip.is_playing = True
            live.song.current_song_time = 1.1
            script._process_bar_pending(live.song)
            self.assertNotIn(("slot", 0, 0), script._bar_pending)
        finally:
            sys.modules.pop("RemoteScripts.Launch", None)
            if previous is not None:
                sys.modules["RemoteScripts.Launch"] = previous

    def test_bar_stop_is_cancelled_when_live_set_track_identity_changes(self):
        previous = sys.modules.pop("RemoteScripts.Launch", None)
        try:
            production = importlib.import_module("RemoteScripts.Launch")
            live = FakeLiveInstance()
            clip = types.SimpleNamespace(is_playing=True, is_recording=False)
            slot = types.SimpleNamespace(has_clip=True, clip=clip, is_group_slot=False)
            stop = types.SimpleNamespace(has_clip=False, has_stop_button=True,
                                         is_group_slot=False, calls=[])
            stop.fire = lambda **kwargs: stop.calls.append(kwargs)
            track = types.SimpleNamespace(playing_slot_index=0, fired_slot_index=-1,
                                          clip_slots=[slot, stop])
            live.song.tracks = [track]
            live.song.scenes = [object()]
            live.song.is_playing = True
            live.song.current_song_time = 1.0
            live.song.signature_numerator = 4
            live.song.signature_denominator = 4
            live.song.tempo = 120.0
            script = production.create_instance(live)
            self.assertTrue(script._scene_action(0, 2))

            live.song.tracks = [types.SimpleNamespace(clip_slots=[])]
            live.song.current_song_time = 1.1
            script._process_bar_pending(live.song)
            self.assertNotIn(("scene", 0), script._bar_pending)
            self.assertTrue(clip.is_playing)
        finally:
            sys.modules.pop("RemoteScripts.Launch", None)
            if previous is not None:
                sys.modules["RemoteScripts.Launch"] = previous

    def test_production_launch_spreads_many_live_changes_over_poll_cycles(self):
        previous = sys.modules.pop("RemoteScripts.Launch", None)
        try:
            production = importlib.import_module("RemoteScripts.Launch")
            live = FakeLiveInstance()
            live.song.tracks = [types.SimpleNamespace(
                color=0, arm=False, mute=False, solo=False, clip_slots=[])
                for _ in range(8)]
            script = production.create_instance(live)
            clock = [1.0]
            with patch.object(production, "_clock", lambda: clock[0], create=True):
                self._complete_production_sync(production, script, live, clock)
            live.midi_out.clear()
            for track in live.song.tracks:
                track.color = 0x404040
                track.arm = True
            with patch.object(production, "_clock", lambda: clock[0], create=True):
                script._poll()
                clock[0] += 0.1
                script._poll()
            self.assertEqual(len(live.midi_out), 16)
            codec = importlib.import_module("RemoteScripts.Launch.protocol")
            types_sent = [codec.decode_frame(value)[0] for value in live.midi_out]
            self.assertEqual(types_sent.count(production.TRACK_COLOR), 8)
            self.assertEqual(types_sent.count(production.TRACK_STATE), 8)
        finally:
            sys.modules.pop("RemoteScripts.Launch", None)
            if previous is not None:
                sys.modules["RemoteScripts.Launch"] = previous

    def test_late_duplicate_hello_does_not_break_an_established_link(self):
        previous = sys.modules.pop("RemoteScripts.Launch", None)
        try:
            production = importlib.import_module("RemoteScripts.Launch")
            live = FakeLiveInstance()
            script = production.create_instance(live)
            script.receive_midi(production.encode_frame(production.HELLO, 1, ()))
            script.receive_midi(production.encode_frame(production.REQUEST_FULL_SYNC, 2, ()))
            script.receive_midi(production.encode_frame(production.HELLO, 3, ()))
            live.midi_out.clear()
            for _ in range(4):
                script._poll()
            codec = importlib.import_module("RemoteScripts.Launch.protocol")
            self.assertIn(production.HEARTBEAT,
                          [codec.decode_frame(value)[0] for value in live.midi_out])
        finally:
            sys.modules.pop("RemoteScripts.Launch", None)
            if previous is not None:
                sys.modules["RemoteScripts.Launch"] = previous

    def test_initialization_survives_unavailable_live_logger(self):
        live = types.SimpleNamespace(send_midi=lambda _message: True)
        script = self.module.create_instance(live)
        self.assertIs(script._launch_host, live)

    def test_disconnect_does_not_send_a_sysex_reset_value(self):
        script = self.module.create_instance(FakeLiveInstance())
        script.disconnect()

    def test_codec_matches_both_production_endpoints(self):
        from RemoteScripts.Launch.protocol import encode_frame as main_encode
        from PythonApps.Launch.protocol import encode as device_encode, decode as device_decode
        frame = self.module.encode_frame(17, 3, ())
        self.assertEqual(frame, main_encode(17, 3, ()))
        self.assertEqual(frame, device_encode(17, 3, ()))
        self.assertEqual(device_decode(frame), (17, 3, ()))


if __name__ == "__main__":
    unittest.main()
