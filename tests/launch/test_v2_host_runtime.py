import importlib
import types
import unittest
from contextlib import nullcontext
from unittest.mock import patch

from RemoteScripts.Launch.input_events import decode_input_event
from RemoteScripts.Launch.protocol_v2 import (
    FRAME_ACK, FRAME_TABLE_BEGIN, FRAME_TABLE_COLOR_CHUNK,
    INPUT_EVENT, LINK_ACK, LINK_HELLO, decode_frame,
    encode_frame, split_u14, split_u28,
)


class FakeSurface:
    def __init__(self, live):
        self._c_instance = live
        self.components = []

    @property
    def song(self):
        return self._c_instance.song

    def component_guard(self):
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
        self.offsets = (0, 0)

    def set_offsets(self, track, scene):
        self.offsets = (track, scene)


class HostRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.module = importlib.import_module("RemoteScripts.Launch.__init___v2")
        self.legacy = importlib.import_module("RemoteScripts.Launch.legacy")
        self.old_bases = self.legacy.Launch.__bases__
        self.old_ring = self.legacy.SessionRingComponent
        self.legacy.Launch.__bases__ = (FakeSurface,)
        self.legacy.SessionRingComponent = FakeRing
        self.now = [10.0]
        self.clock_patch = patch.object(self.module, "_clock", lambda: self.now[0])
        self.clock_patch.start()
        self.live = types.SimpleNamespace(
            logs=[], midi_out=[], highlights=[],
            song=types.SimpleNamespace(
                tracks=[self.make_track() for _ in range(10)],
                scenes=[types.SimpleNamespace(is_triggered=False, fire=lambda: None)
                        for _ in range(10)],
                is_playing=False, current_song_time=0.0,
                signature_numerator=4, signature_denominator=4, tempo=120.0,
            ),
        )
        self.live.log_message = lambda message: self.live.logs.append(message)
        self.live.set_session_highlight = lambda *args: self.live.highlights.append(args)
        self.script = self.module.create_instance(self.live)
        self.session = 0x1234567
        self.device_boot = 123
        self.script.receive_midi(self.module.encode_frame(
            LINK_HELLO, 1, split_u28(self.device_boot)))
        self.assertTrue(self.script._link_active)
        self.session = self.script._host_session
        self.assertGreater(self.session, 0)

    def tearDown(self):
        self.clock_patch.stop()
        self.legacy.Launch.__bases__ = self.old_bases
        self.legacy.SessionRingComponent = self.old_ring

    @staticmethod
    def make_track():
        slots = []
        for _ in range(12):
            slot = types.SimpleNamespace(has_clip=False, is_group_slot=False,
                                         calls=[], has_stop_button=True)
            slot.fire = lambda slot=slot, **kwargs: slot.calls.append(kwargs)
            slots.append(slot)
        track = types.SimpleNamespace(
            color=0x336699, arm=False, mute=False, solo=False, can_be_armed=True,
            playing_slot_index=-1, fired_slot_index=-1, clip_slots=slots,
        )
        track.stop_all_clips = lambda *_args: None
        return track

    def send_input(self, event_id, time_ms, function=False, pressed=False,
                   released=False, held=False, x=None, y=None):
        from PythonApps.Launch.input_events import encode_input_event
        payload = encode_input_event(self.session, event_id, time_ms, function,
                                     pressed, released, held, x, y)
        self.script.receive_midi(self.module.encode_frame(INPUT_EVENT, event_id & 0x7F,
                                                          payload))

    def test_repeated_device_hello_resets_session_and_forces_full_frame(self):
        self.script._host_controller.gesture.page = "track"
        previous_session = self.script._host_session
        self.now[0] += 1.0
        self.script.receive_midi(self.module.encode_frame(
            LINK_HELLO, 2, split_u28(self.device_boot)))
        self.assertNotEqual(self.script._host_session, previous_session)
        self.assertIsNone(self.script._frame_sender.acknowledged_colors)
        self.assertIsNone(self.script._frame_sender.in_flight)
        self.now[0] += 0.04
        self.script._display_timer_tick()
        self.assertIsNotNone(self.script._frame_sender.in_flight)
        self.assertEqual(self.script._host_controller.gesture.page, "track",
                         "a transport retry from the same App keeps the current page")

    def test_device_app_restart_returns_to_v1_default_session_page(self):
        self.send_input(1, 1000, function=True, pressed=True)
        self.send_input(2, 1010, function=True, released=True)
        self.assertEqual(self.script._host_controller.gesture.page, "track")
        self.device_boot += 1
        self.now[0] += 1.0
        self.script.receive_midi(self.module.encode_frame(
            LINK_HELLO, 3, split_u28(self.device_boot)))
        self.assertEqual(self.script._host_controller.gesture.page, "session")

    def test_host_requests_10ms_transport_ticks(self):
        original_live = self.module._Live
        timers = []

        class FakeTimer:
            def __init__(self, callback, interval, repeat=False, start=False):
                if not isinstance(interval, int):
                    raise TypeError("Live Timer interval must be an integer number of milliseconds")
                self.callback = callback
                self.interval = interval
                self.repeat = repeat
                self.started = start
                timers.append(self)

            def start(self):
                self.started = True

            def stop(self):
                self.started = False

        self.module._Live = types.SimpleNamespace(
            Base=types.SimpleNamespace(Timer=FakeTimer))
        try:
            self.script._start_display_timer()
        finally:
            self.module._Live = original_live
        self.assertIs(self.script._display_timer, timers[0] if timers else None)
        self.assertTrue(timers, "Live rejected the timer constructor")
        self.assertTrue(timers[0].started)
        self.assertEqual(timers[0].interval, 10)
        self.assertTrue(timers[0].repeat)

    def test_display_render_counter_is_per_metrics_window(self):
        self.script._display_ready = True
        self.script._last_device_message = self.now[0]
        self.script._display_metrics_started = self.now[0] - 10.0
        self.script._display_metrics_renders = 7
        self.script._display_metrics_ticks = 10
        self.script._display_metrics_last_tick = self.now[0] - 0.04
        self.script._last_render_at = self.now[0] - 0.04
        self.script._display_timer_tick()

        self.assertEqual(self.script._display_metrics_renders, 0)
        self.assertEqual(self.script._display_metrics_ticks, 0)

    def test_stopped_arm_clock_survives_live_state_refreshes(self):
        clock = self.script._display_state.phase_clock
        clock.update(phase_u14=2048, tempo=120.0, playing=True, now_ms=10000)
        clock.update(phase_u14=2048, tempo=120.0, playing=False, now_ms=10000)
        self.now[0] = 10.25
        self.script._refresh_display_state(self.live.song)
        self.assertIs(self.script._display_state.phase_clock, clock)
        self.assertAlmostEqual(clock.phase_at(10250, continue_when_stopped=True), 1.0)

    def test_transport_ticks_send_one_packet_each_without_rendering_every_tick(self):
        rendered = []
        original = self.script._render_colors

        def count_render(now=None):
            rendered.append(now)
            return original(now)

        self.script._render_colors = count_render
        for step in range(1, 10):
            self.now[0] = 10.0 + step * 0.01
            self.script._display_timer_tick()
        outgoing = [decode_frame(frame) for frame in self.live.midi_out]
        self.assertEqual([frame[0] for frame in outgoing[:3]],
                         [LINK_ACK, FRAME_TABLE_BEGIN, FRAME_TABLE_COLOR_CHUNK],
                         "10 ms service ticks should send frame packets no faster than the configured 40 ms gap")
        self.assertEqual(len(rendered), 3,
                         "the full 8x8 colors should render at a 40 ms cadence across this 90 ms window")

    def test_device_hello_gets_session_and_initial_full_frame(self):
        outgoing = [decode_frame(frame) for frame in self.live.midi_out]
        ack = next(frame for frame in outgoing if frame[0] == LINK_ACK)
        self.assertEqual(ack[2], split_u28(self.device_boot) + split_u28(self.session))
        self.assertEqual([frame[0] for frame in outgoing], [LINK_ACK],
                         "the host must not burst-send a frame with the handshake")
        self.now[0] += 0.04
        self.script._display_timer_tick()
        outgoing = [decode_frame(frame) for frame in self.live.midi_out]
        self.assertEqual(outgoing[-1][0], FRAME_TABLE_BEGIN,
                         "the next timer tick begins the computer-rendered frame")

    def test_first_paced_packet_consumes_the_full_frame_request(self):
        self.assertTrue(self.script._display_force_full)
        self.now[0] += 0.04
        self.script._display_timer_tick()
        self.assertFalse(self.script._display_force_full,
                         "timer must not keep requesting full frames after sending")

    def test_page_change_uses_incremental_frame_after_initial_frame_is_acknowledged(self):
        sender = self.script._frame_sender
        sender.acknowledged_colors = (0,) * 64
        sender.acknowledged_slots = tuple(range(64))
        sender.acknowledged_frame_id = 17
        sender.in_flight = None
        sender._pending_packets = ()
        sender._force_full = False
        self.script._display_force_full = False
        sender._last_packet_at = None

        self.send_input(1, 1000, function=True, pressed=True)
        self.send_input(2, 1010, function=True, released=True)

        self.assertEqual(self.script._host_controller.gesture.page, "track")
        self.assertIsNotNone(sender.in_flight)
        self.assertNotEqual(sender.in_flight["kind"], "table_full")

    def test_armed_empty_slot_press_logs_live_count_in_state_after_fire(self):
        track = self.live.song.tracks[0]
        slot = track.clip_slots[0]
        track.arm = True
        slot.is_triggered = False
        slot.fire = lambda: setattr(slot, "is_triggered", True)

        self.send_input(1, 1000, x=0, y=0, pressed=True)

        self.assertTrue(any("Armed empty slot fire state: track=1 scene=1 "
                            "transport=False triggered=True" in line
                            for line in self.live.logs), self.live.logs)

    def test_raw_fn_and_pad_events_drive_v1_live_action_path_once(self):
        # Confirm the initial frame so page changes can enqueue the next frame.
        self.script.receive_midi(self.module.encode_frame(
            FRAME_ACK, 4, split_u28(self.session) + split_u14(0) + (1,)))
        self.send_input(1, 1000, function=True, pressed=True)
        self.send_input(2, 1010, function=True, released=True)
        self.assertEqual(self.script._host_controller.gesture.page, "track")
        self.send_input(3, 1020, x=0, y=4, pressed=True)
        self.send_input(3, 1020, x=0, y=4, pressed=True)
        self.assertTrue(self.live.song.tracks[0].arm,
                        "duplicate raw event must not toggle the Track twice")
        self.assertEqual(self.script._display_page, "track")

    def test_nonprefix_session_change_rebuilds_snapshot_and_forces_full_frame(self):
        self.script._update_session_shape(self.live.song, send_sync=False)
        old_first_track = self.live.song.tracks[0]
        replacement = self.make_track()
        replacement.color = 0xFE0000
        self.live.song.tracks[0] = replacement

        changed = self.script._update_session_shape(self.live.song)

        self.assertTrue(changed)
        self.assertEqual(self.script._display_state.tracks[0]["color"], (127, 0, 0))
        self.assertTrue(self.script._frame_sender.in_flight["full"])
        self.assertNotEqual(self.script._window_tracks[0], old_first_track)
        self.assertTrue(any("display refresh applied: session shape changed" in line
                            for line in self.live.logs))

    def test_navigation_keeps_host_state_polling_enabled(self):
        self.send_input(1, 1000, function=True, pressed=True)
        self.send_input(2, 1010, function=True, released=True)
        self.send_input(3, 1020, x=7, y=1, pressed=True)
        self.send_input(4, 1030, x=7, y=1, released=True)
        self.assertEqual(self.script._track_offset, 1)
        self.assertFalse(self.script._sync_pending)

    def test_input_gap_cancels_pending_gesture_before_accepting_later_events(self):
        self.send_input(20, 2000, function=True, pressed=True)
        self.send_input(22, 2010, function=True, released=True)
        self.assertEqual(self.script._host_controller.gesture.page, "session")
        self.assertTrue(any("sequence gap" in message for message in self.live.logs))


if __name__ == "__main__":
    unittest.main()
