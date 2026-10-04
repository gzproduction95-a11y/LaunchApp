"""Launch V2.2 / protocol v11 Remote Script: Live control and computer-side rendering."""

from time import monotonic as _clock

from .legacy import Launch as _LegacyLaunch
from . import protocol as _legacy_protocol
from .slot_sender import ColorTableSender
from .slot_stream import assign_role_slots
from .input_events import decode_input_event, extend_device_millis
from .model import apply_track_action
from .navigation import record_length_code
from .protocol_v2 import (FRAME_ACK, FRAME_REQUEST, HEARTBEAT, INPUT_EVENT,
                          LINK_ACK, LINK_HELLO, PROTOCOL_VERSION, encode_frame,
                          join_u14, join_u28, split_u28)
from .rendering import color_for_cell, color_role_for_cell, control_color_for_cell
from .state import SessionState
from .controller import LaunchController

try:
    import Live as _Live
except ImportError:
    _Live = None

SYSEX_PREFIX = (0xF0, 0x00, 0x02, 0x03, 0x4D, 0x58)
TRANSPORT_INTERVAL_MS = 10
PROTOCOL_BUILD = "V2.2 / protocol v11"
FRAME_PACKET_GAP_MS = 40
FRAME_PACKET_GAP_SECONDS = FRAME_PACKET_GAP_MS / 1000.0
DISPLAY_RENDER_INTERVAL_SECONDS = 0.04
FN_INPUT_ID = (0, 99)
PAD_INPUT_ID = (1, 4)
NAVIGATION_CODES = {"left": 1, "right": 2, "up": 3, "down": 4, "home": 5}
TRACK_ACTION_CODES = {"arm": 1, "mute": 2, "solo": 3, "stop": 4}


class LaunchV2(_LegacyLaunch):
    """Keep the accepted Live actions; move raw input and LED calculation to Live."""

    def __init__(self, c_instance):
        super(LaunchV2, self).__init__(c_instance)
        self._host_session = None
        self._device_boot_id = None
        self._host_controller = LaunchController(FN_INPUT_ID)
        self._frame_sender = ColorTableSender(packet_gap_seconds=FRAME_PACKET_GAP_SECONDS)
        self._display_state = SessionState()
        self._display_ready = False
        self._display_sequence = 0
        self._last_input_id = None
        self._device_time_raw = None
        self._device_time_absolute = None
        self._display_force_full = True
        self._display_page = "session"
        self._nav_feedback = None
        self._nav_feedback_until = 0.0
        self._press_flash_cell = None
        self._press_flash_until = 0.0
        self._desired_colors = (0,) * 64
        self._desired_slot_colors = (0,) * 64
        self._desired_cell_slots = (0,) * 64
        self._display_role_slots = {}
        self._last_render_roles = ()
        self._display_timer = None
        self._last_render_at = None
        self._display_metrics_renders = 0
        self._display_metrics_started = _clock()
        self._display_metrics_ticks = 0
        self._display_metrics_last_tick = None
        self._display_metrics_max_gap = 0.0
        self._display_metrics_last_ack_count = 0
        self._start_display_timer()
        self._log("Launch V2.2 / protocol v11 host color-table renderer initialized; service={} ms, frame packet gap={} ms".format(
            TRANSPORT_INTERVAL_MS, FRAME_PACKET_GAP_MS))

    def _start_display_timer(self):
        """Service one MIDI packet per transport tick; render every 40 ms."""
        try:
            timer_type = _Live.Base.Timer
            self._display_timer = timer_type(self._display_timer_tick,
                                             TRANSPORT_INTERVAL_MS, True)
            self._display_timer.start()
            self._log("Launch transport timer started at {} ms; frame packet gap={} ms; display target 40 ms".format(
                TRANSPORT_INTERVAL_MS, FRAME_PACKET_GAP_MS))
        except Exception as exc:
            self._display_timer = None
            self._log("Launch display timer unavailable: {}".format(exc))

    def disconnect(self):
        timer = self._display_timer
        if timer is not None:
            try:
                timer.stop()
            except Exception:
                pass
        self._display_timer = None
        super(LaunchV2, self).disconnect()

    def _send(self, message, payload=()):
        # The inherited 100 ms poll emits the old HEARTBEAT constant. Translate
        # only that one call; all V1 state-sync messages are intentionally muted.
        if message == _legacy_protocol.HEARTBEAT:
            message = HEARTBEAT
            payload = split_u28(self._host_session) if self._host_session is not None else ()
        elif message in (
            _legacy_protocol.HELLO_ACK, _legacy_protocol.SYNC_BEGIN,
            _legacy_protocol.SYNC_DATA, _legacy_protocol.SYNC_END,
            _legacy_protocol.TRACK_COLOR, _legacy_protocol.TRACK_STATE,
            _legacy_protocol.SLOT_STATE, _legacy_protocol.SCENE_STATE,
            _legacy_protocol.WINDOW_META, _legacy_protocol.REC_LENGTH_STATE,
            _legacy_protocol.SYNC_ACK,
        ):
            return False
        self._sequence = (self._sequence + 1) & 0x7F
        frame = encode_frame(message, self._sequence, payload)
        sent = self._send_midi(SYSEX_PREFIX + frame + (0xF7,))
        if sent is False:
            self._log("Launch V2.2 / protocol v11 MIDI send failed: type={} sequence={}".format(
                message, self._sequence))
        return sent

    def _on_sysex(self, midi_bytes):
        self._handle_protocol_message(midi_bytes)

    def receive_midi(self, midi_bytes):
        self._handle_protocol_message(midi_bytes)

    def _handle_protocol_message(self, midi_bytes):
        from .protocol_v2 import decode_frame
        decoded = decode_frame(midi_bytes)
        if decoded is None:
            return
        message, _sequence, payload = decoded
        now = _clock()
        if message == LINK_HELLO and len(payload) == 4:
            boot_id = join_u28(payload)
            # A HELLO is emitted only by device startup/retry. Treat each one as
            # a new epoch so a fast restart cannot reuse a stale LED baseline.
            device_restarted = (self._device_boot_id is None
                                or boot_id != self._device_boot_id)
            self._device_boot_id = boot_id
            self._host_session = int(now * 1000.0) & 0x0FFFFFFF
            if self._host_session == 0:
                self._host_session = 1
            self._frame_sender.reset(self._host_session)
            self._display_role_slots = {}
            self._last_input_id = None
            if device_restarted:
                self._host_controller = LaunchController(FN_INPUT_ID)
                self._display_page = "session"
            else:
                self._clear_gesture_state()
            self._device_time_raw = None
            self._device_time_absolute = None
            self._display_ready = False
            self._display_force_full = True
            self._display_metrics_last_ack_count = 0
            self._display_metrics_started = now
            self._display_metrics_ticks = 0
            self._display_metrics_renders = 0
            self._display_metrics_max_gap = 0.0
            self._display_metrics_last_tick = None
            self._display_metrics_renders = 0
            self._last_render_at = None
            self._log("Launch V2.2 / protocol v11 device connected; opening session")
            self._link_active = True
            self._last_device_message = now
            self._send(LINK_ACK, split_u28(boot_id) + split_u28(self._host_session))
            self._refresh_display_state(self.song)
            # The next display tick starts the frame after the handshake packet.
        elif message == HEARTBEAT and len(payload) == 4:
            if self._link_active and join_u28(payload) == self._host_session:
                self._last_device_message = now
        elif message == INPUT_EVENT:
            self._last_device_message = now
            self._handle_input_event(payload)
        elif message == FRAME_ACK and len(payload) == 7:
            session_id = join_u28(payload[:4])
            frame_id = join_u14(payload[4], payload[5])
            if self._frame_sender.acknowledge(session_id, frame_id, payload[6], now):
                acknowledged = self._frame_sender.last_acknowledged
                if acknowledged and (acknowledged["full"] or payload[6] != 1):
                    context = acknowledged["context"] or {}
                    self._log("Launch V2.2 / protocol v11 table-frame ack id={} status={} "
                              "digest={} page={} offset={} valid_columns={}".format(
                                  acknowledged["id"], acknowledged["status"],
                                  context.get("digest", "?"), context.get("page", "?"),
                                  context.get("offset", "?"),
                                  context.get("valid_columns", "?")))
                self._frame_sender.offer(self._desired_slot_colors,
                                         self._desired_cell_slots,
                                         self._send_encoded, now,
                                         force=self._display_force_full,
                                         context=self._display_context())
                self._display_force_full = False
        elif message == FRAME_REQUEST and len(payload) == 4:
            if self._link_active and join_u28(payload) == self._host_session:
                self._display_force_full = True
                self._render_display(force=True)

    def _send_encoded(self, frame):
        return self._send_midi(SYSEX_PREFIX + tuple(frame) + (0xF7,))

    def _clear_gesture_state(self):
        gesture = self._host_controller.gesture
        gesture._fn_down_at = None
        gesture._last_release_at = None
        gesture._second_tap_candidate = False
        self._host_controller._nav_pending.clear()

    def _handle_input_event(self, payload):
        callback_started = _clock()
        if not self._link_active or not self._display_ready:
            return
        event = decode_input_event(payload)
        if event is None or event["session_id"] != self._host_session:
            return
        event_id = event["event_id"]
        if self._last_input_id is not None:
            distance = (event_id - self._last_input_id) & 0x3FFF
            if distance == 0 or distance >= 0x2000:
                return
            if distance != 1:
                self._clear_gesture_state()
                self._last_input_id = event_id
                self._log("Launch V2.2 / protocol v11 input sequence gap; cancelled pending gesture")
                return
        self._last_input_id = event_id
        unwrapped = extend_device_millis(event["device_ms"], self._device_time_raw,
                                         self._device_time_absolute)
        if unwrapped is None:
            self._clear_gesture_state()
            return
        self._device_time_raw, self._device_time_absolute = unwrapped
        if event["is_function"]:
            input_id, point = FN_INPUT_ID, None
        else:
            input_id, point = PAD_INPUT_ID, (event["x"], event["y"])
        host_event = {
            "id": input_id,
            "point": point,
            "keypad": {"pressed": event["pressed"],
                       "released": event["released"],
                       "hold": event["held"]},
        }
        controller_started = _clock()
        actions = self._host_controller.handle_event(host_event,
                                                      self._device_time_absolute)
        controller_finished = _clock()
        for action in actions:
            self._dispatch_host_action(action)
        callback_finished = _clock()
        self._log("Launch input timing id={} controller_ms={:.3f} "
                  "actions={} dispatch_ms={:.3f} callback_ms={:.3f}".format(
                      event_id,
                      (controller_finished - controller_started) * 1000.0,
                      len(actions),
                      (callback_finished - controller_finished) * 1000.0,
                      (callback_finished - callback_started) * 1000.0))

    def _dispatch_host_action(self, action):
        kind = action[0]
        if kind == "page":
            self._display_page = action[1]
            self._log("Launch V2.2 / protocol v11 page changed to {}; {}".format(
                action[1], self._display_context_text()))
            self._render_display()
        elif kind == "grid":
            slot_id = action[1]
            if self._should_flash_slot(slot_id):
                self._press_flash_cell = (slot_id % 8, slot_id // 8)
                self._press_flash_until = _clock() + 0.12
            self._grid_press(slot_id)
            self._send_changed_records(self.song)
        elif kind == "track":
            track_index = self._track_offset + action[1]
            code = TRACK_ACTION_CODES.get(action[2])
            if code == 4:
                self._cancel_track_pending(track_index)
            if code is not None and apply_track_action(self.song, track_index, code):
                self._send_changed_records(self.song)
        elif kind in ("scene_launch", "scene_stop"):
            scene_index = self._scene_offset + action[1]
            self._scene_action(scene_index, 1 if kind == "scene_launch" else 2)
        elif kind == "navigate":
            code = NAVIGATION_CODES.get(action[1])
            if code is not None and self._navigate(code, action[2]):
                self._display_force_full = True
                self._send_changed_records(self.song)
        elif kind == "nav_preview":
            self._nav_feedback = action[1]
            self._nav_feedback_until = _clock() + 0.18
            self._render_display()
        elif kind == "record_length":
            selected = record_length_code(action[1])
            observed = self._record_length_code
            self._set_record_length(selected, observed)
            self._send_changed_records(self.song)

    def _should_flash_slot(self, slot_id):
        if not self._display_ready or not 0 <= slot_id < 64:
            return False
        track = self._display_state.tracks[slot_id % 8]
        slot = self._display_state.slots[slot_id]
        return (track.get("valid", False) and not track.get("arm", False)
                and track.get("active", False) and slot.get("valid", False)
                and slot.get("status") == 0)

    def _refresh_display_state(self, song):
        if song is None:
            return False
        state = SessionState()
        state.phase_clock = self._display_state.phase_clock
        for kind, record_id, value in self._snapshot_records(song):
            if kind == "color":
                state.update_track_color(record_id, value)
            elif kind == "flags":
                state.update_track_flags(record_id, value)
            elif kind == "slot":
                state.update_slot(record_id, value)
            elif kind == "scene":
                state.update_scene(record_id, value)
        state.track_offset = self._track_offset
        state.scene_offset = self._scene_offset
        state.track_count, state.scene_count = self._session_counts(song)
        state.rec_length_code = self._record_length_code
        state.tempo = float(getattr(song, "tempo", 120.0))
        state.synced = True
        state.sync_id = self._active_sync_id
        try:
            phase = int((float(song.current_song_time) % 4.0)
                        * 4096.0 + 0.5) % 0x4000
            playing = bool(song.is_playing)
        except Exception:
            phase, playing = 0, False
        state.phase_clock.update(phase, state.tempo, playing,
                                 int(_clock() * 1000.0) & 0xFFFFFFFF)
        self._display_state = state
        self._display_ready = True
        return True

    def _render_colors(self, now=None):
        now = _clock() if now is None else float(now)
        state = self._display_state
        now_ms = int(now * 1000.0) & 0xFFFFFFFF
        phase = state.phase_clock.phase_at(now_ms)
        arm_phase = state.phase_clock.phase_at(
            now_ms, continue_when_stopped=True)
        colors = []
        roles = []
        page = self._host_controller.gesture.page
        for y in range(8):
            for x in range(8):
                track, slot, scene = state.tracks[x], state.slots[y * 8 + x], state.scenes[y]
                flash = (self._press_flash_cell == (x, y)
                         and now < self._press_flash_until)
                color = color_for_cell(
                    page, y, track, slot, phase, state.tempo,
                    column=x, scene=scene, flash=flash,
                    arm_phase_beats=arm_phase,
                    queued_phase_beats=state.phase_clock.phase_at(
                        now_ms, continue_when_stopped=True))
                fixed_color = None
                if page == "track" and y < 4:
                    feedback = self._nav_feedback if now < self._nav_feedback_until else None
                    color = control_color_for_cell(
                        y, x, state.rec_length_code, state.track_offset,
                        state.scene_offset, state.track_count, state.scene_count,
                        feedback=feedback)
                    fixed_color = color
                colors.append(color)
                roles.append(color_role_for_cell(page, y, x, track, slot, scene,
                                                 flash=flash, fixed_color=fixed_color))
        self._last_render_roles = tuple(roles)
        return tuple(colors)

    def _render_slot_data(self, colors):
        slot_colors, cell_slots, roles = assign_role_slots(
            self._last_render_roles, colors, self._display_role_slots)
        self._display_role_slots = roles
        return slot_colors, cell_slots

    def _render_display(self, force=False):
        if not self._link_active or self._host_session is None:
            return False
        now = _clock()
        if self._display_ready:
            self._desired_colors = self._render_colors(now)
            (self._desired_slot_colors,
             self._desired_cell_slots) = self._render_slot_data(self._desired_colors)
            self._display_metrics_renders += 1
            self._last_render_at = now
        force = bool(force or self._display_force_full)
        sent = self._frame_sender.offer(self._desired_slot_colors,
                                        self._desired_cell_slots,
                                        self._send_encoded, now, force=force,
                                        context=self._display_context())
        if sent:
            self._display_force_full = False
        return sent

    def _display_timer_tick(self):
        if not self._link_active or self._host_session is None:
            return
        now = _clock()
        if now - self._last_device_message > 3.0:
            return
        if self._display_metrics_last_tick is not None:
            gap = now - self._display_metrics_last_tick
            self._display_metrics_max_gap = max(self._display_metrics_max_gap, gap)
        self._display_metrics_last_tick = now
        self._display_metrics_ticks += 1
        if (self._display_ready and
                (self._last_render_at is None
                 or now - self._last_render_at + 1e-9
                 >= DISPLAY_RENDER_INTERVAL_SECONDS)):
            self._desired_colors = self._render_colors(now)
            (self._desired_slot_colors,
             self._desired_cell_slots) = self._render_slot_data(self._desired_colors)
            self._display_metrics_renders += 1
            self._last_render_at = now
        sent = self._frame_sender.offer(self._desired_slot_colors,
                                        self._desired_cell_slots,
                                        self._send_encoded, now,
                                        force=self._display_force_full,
                                        context=self._display_context())
        if sent:
            self._display_force_full = False
        elapsed = now - self._display_metrics_started
        if elapsed >= 10.0:
            ack_count = self._frame_sender.ack_count
            acks = ack_count - self._display_metrics_last_ack_count
            self._log("Launch V2.2 / protocol v11 display metrics timer_hz={:.1f} render_hz={:.1f} "
                      "max_gap_ms={:.1f} frame_acks_per_s={:.1f} "
                      "ack_last_ms={:.1f} ack_max_ms={:.1f} "
                      "render_to_ack_ms={:.1f} render_to_ack_max_ms={:.1f} "
                      "nacks={} timeouts={}".format(
                          self._display_metrics_ticks / elapsed,
                          self._display_metrics_renders / elapsed,
                          self._display_metrics_max_gap * 1000.0,
                          acks / elapsed,
                          (self._frame_sender.last_ack_latency or 0.0) * 1000.0,
                          self._frame_sender.max_ack_latency * 1000.0,
                          (self._frame_sender.last_ack_render_age or 0.0) * 1000.0,
                          self._frame_sender.max_ack_render_age * 1000.0,
                          self._frame_sender.nack_count,
                          self._frame_sender.timeout_count))
            self._display_metrics_started = now
            self._display_metrics_ticks = 0
            self._display_metrics_renders = 0
            self._display_metrics_renders = 0
            self._display_metrics_max_gap = 0.0
            self._display_metrics_last_ack_count = ack_count

    def _send_changed_records(self, song):
        self._refresh_display_state(song)
        self._render_display()

    @staticmethod
    def _display_digest(colors):
        """FNV-1a over canonical 24-bit RGB values, shared with the device log."""
        value = 0x811C9DC5
        for color in colors:
            for shift in (16, 8, 0):
                value = ((value ^ ((int(color) >> shift) & 0xFF))
                         * 0x01000193) & 0xFFFFFFFF
        return value

    def _display_context(self):
        state = self._display_state
        valid_columns = tuple(index for index, track in enumerate(state.tracks)
                              if track.get("valid", False))
        return {
            "page": self._host_controller.gesture.page,
            "offset": "{},{}".format(state.track_offset, state.scene_offset),
            "track_count": state.track_count,
            "scene_count": state.scene_count,
            "valid_columns": ",".join(str(value) for value in valid_columns) or "-",
            "digest": "{:08x}".format(self._display_digest(self._desired_colors)),
            "render_at": self._last_render_at,
        }

    def _display_context_text(self):
        context = self._display_context()
        return "offset={} valid_columns={} digest={:08x}".format(
            context["offset"], context["valid_columns"],
            self._display_digest(self._render_colors()))

    def _request_full_sync(self, reason, immediate=False):
        # V2 replaces the V1 state-sync transaction with a fresh host-rendered
        # frame. Rebuild the snapshot here; logging a request alone leaves stale
        # track/slot positions after non-prefix Session changes.
        self._sync_pending = False
        self._sync_in_flight = None
        self._active_sync_id = None
        self._active_shape_revision = -1
        self._refresh_display_state(self.song)
        self._display_force_full = True
        self._log("Launch V2.2 / protocol v11 display refresh applied: {}; {}".format(
            reason, self._display_context_text()))
        self._render_display(force=True)

    def _service_full_sync(self, now):
        # V2 sends computer-rendered frames instead of the V1 device state mirror.
        return None


def create_instance(c_instance):
    return LaunchV2(c_instance)
