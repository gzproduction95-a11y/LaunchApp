"""Launch MIDI Remote Script for Ableton Live 12.4.6.

The supported behaviour has been manually accepted on Live 12.4.6 and
Mystrix Pro. This script never deletes Clips.
"""

import logging
from time import monotonic as _clock

try:
    from ableton.v2.base import liveobj_changed as _liveobj_changed
    from ableton.v2.base import liveobj_valid as _liveobj_valid
except ImportError:  # Keeps the Live-object model testable in ordinary CPython.
    def _liveobj_changed(previous, current):
        return previous is not current

    def _liveobj_valid(value):
        return value is not None

try:
    from ableton.v2.control_surface import ControlSurface
    from ableton.v2.control_surface.elements import SysexElement
except ImportError:  # Lets CPython run pure protocol/model tests outside Live.
    class ControlSurface(object):
        pass
    SysexElement = None

try:
    from ableton.v3.control_surface.components.session_ring import SessionRingComponent
except ImportError:  # Lets CPython run pure protocol/model tests outside Live.
    SessionRingComponent = None

from .model import (EMPTY, STOPPED, PLAYING, RECORDING, STOP_QUEUED,
                    RECORD_END_QUEUED, LAUNCH_QUEUED, apply_track_action,
                    snapshot_payloads, pack_sync_records, _slot_state,
                    collect_scene_targets, active_clip_in_track)
from .protocol import (HELLO, REQUEST_FULL_SYNC, GRID_PRESS, TRACK_ACTION, NAVIGATION,
                       HELLO_ACK, SYNC_BEGIN, TRACK_COLOR, TRACK_STATE,
                       SLOT_STATE, SYNC_END, SYNC_DATA, HEARTBEAT,
                       SCENE_ACTION, SCENE_STATE, REC_LENGTH,
                       SYNC_ACK, WINDOW_META, REC_LENGTH_STATE,
                       decode_frame, encode_frame, split_u14, join_u14)
from .timing import record_length_beats
from .timing import current_bar_end_boundary

RECORD_LENGTHS = (1, 2, 4, 6, 8, 12, 16)

SYSEX_PREFIX = (0xF0, 0x00, 0x02, 0x03, 0x4D, 0x58)
SYSEX_IDENTIFIER = SYSEX_PREFIX
SYNC_DEBOUNCE_SECONDS = 0.15
SYNC_MIN_INTERVAL_SECONDS = 0.15
SYNC_FRAME_INTERVAL_SECONDS = 0.01
SYNC_ACK_TIMEOUT_SECONDS = 2.0
SYNC_DATA_BUDGET = 100
try:
    import Live as _Live
    BAR_LAUNCH_QUANTIZATION = _Live.Song.Quantization.q_bar
except ImportError:
    # Live's Song quantization enum uses q_bar=4; q_half=5.
    # Keep pure-Python tests importable without Ableton's runtime.
    BAR_LAUNCH_QUANTIZATION = 4
_logger = logging.getLogger("Launch")


class Launch(ControlSurface):
    def __init__(self, c_instance):
        super(Launch, self).__init__(c_instance)
        self._launch_host = c_instance
        self._sequence = 0
        self._sync_id = 0
        self._sync_pending = False
        self._sync_due_at = 0.0
        self._sync_reason = ""
        self._sync_in_flight = None
        self._next_sync_frame_at = 0.0
        self._active_sync_id = None
        self._active_shape_revision = -1
        self._shape_revision = 0
        self._window_tracks = None
        self._window_scenes = None
        self._pending = {}
        self._bar_pending = {}
        self._last_snapshot = {}
        self._poll_count = 0
        self._link_active = False
        self._last_device_message = 0.0
        self._last_full_sync_at = -10000.0
        self._track_offset = 0
        self._scene_offset = 0
        self._track_count = 0
        self._scene_count = 0
        self._record_length_code = 0
        self._sysex_input = None
        self._session_ring = None
        if SysexElement is not None:
            with self.component_guard():
                self._sysex_input = SysexElement(sysex_identifier=SYSEX_IDENTIFIER)
                self._sysex_input.add_value_listener(self._on_sysex)
        self._create_session_ring()
        self.schedule_message(1, self._poll)
        self._log("Launch Remote Script initialized")

    def _create_session_ring(self):
        """Register the fixed 8x8 Live highlight without owning pad controls."""
        if SessionRingComponent is None:
            return
        try:
            with self.component_guard():
                self._session_ring = SessionRingComponent(
                    name="Launch_Session_Ring",
                    num_tracks=8,
                    num_scenes=8,
                    include_returns=False,
                    include_master=False,
                    right_align_non_player_tracks=False,
                    tracks_to_use=None,
                    snap_track_offset=False,
                    set_session_highlight=self._set_session_highlight,
                    is_private=False,
                )
                self._session_ring.set_offsets(0, 0)
                self._register_component(self._session_ring)
            self._log("Launch Session Ring registered: 8x8 at track=0 scene=0")
        except Exception as exc:
            self._session_ring = None
            self._log("Launch Session Ring setup failed: {}".format(exc))

    def _set_session_highlight(self, track_offset, scene_offset, num_tracks,
                               num_scenes, is_visible):
        """Forward the v3 component's highlight request to Live's host API."""
        try:
            self._c_instance.set_session_highlight(
                track_offset, scene_offset, num_tracks, num_scenes, is_visible)
        except Exception as exc:
            self._log("Launch Session Highlight update failed: {}".format(exc))

    def _session_counts(self, song):
        tracks = min(0x3FFF, len(list(getattr(song, "tracks", ()))))
        scenes = min(0x3FFF, len(list(getattr(song, "scenes", ()))))
        return tracks, scenes

    def _set_ring_offsets(self, track_offset, scene_offset):
        if self._session_ring is None:
            self._log("Navigation unavailable: Session Ring was not registered")
            return False
        try:
            with self.component_guard():
                self._session_ring.set_offsets(track_offset, scene_offset)
            return True
        except Exception as exc:
            self._log("Launch Session Ring offset update failed: {}".format(exc))
            return False

    def _update_session_shape(self, song, send_sync=True):
        try:
            tracks = list(getattr(song, "tracks", ()))
            scenes = list(getattr(song, "scenes", ()))
            track_count, scene_count = min(0x3FFF, len(tracks)), min(0x3FFF, len(scenes))
        except Exception as exc:
            self._log("Cannot read Live Session size: {}".format(exc))
            return False
        track_offset = min(self._track_offset, max(0, track_count - 8))
        scene_offset = min(self._scene_offset, max(0, scene_count - 8))
        window_tracks = tracks[track_offset:track_offset + 8]
        window_scenes = scenes[scene_offset:scene_offset + 8]
        tracks_changed = not self._same_live_objects(self._window_tracks, window_tracks)
        scenes_changed = not self._same_live_objects(self._window_scenes, window_scenes)
        changed = (track_count != self._track_count or scene_count != self._scene_count
                   or track_offset != self._track_offset
                   or scene_offset != self._scene_offset
                   or tracks_changed or scenes_changed)
        if not changed:
            return False
        offset_changed = (track_offset, scene_offset) != (self._track_offset,
                                                          self._scene_offset)
        append_or_trim_only = (
            not offset_changed
            and self._window_objects_are_prefix_compatible(self._window_tracks, window_tracks)
            and self._window_objects_are_prefix_compatible(self._window_scenes, window_scenes)
        )
        if offset_changed and not self._set_ring_offsets(track_offset, scene_offset):
            return False
        self._track_count, self._scene_count = track_count, scene_count
        self._track_offset, self._scene_offset = track_offset, scene_offset
        self._window_tracks, self._window_scenes = window_tracks, window_scenes
        self._shape_revision += 1
        self._log("Live Session window shape tracks={} scenes={} offset=({}, {})".format(
            track_count, scene_count, track_offset, scene_offset))
        if append_or_trim_only and self._active_sync_id is not None and not self._sync_pending:
            self._active_shape_revision = self._shape_revision
            self._send_window_meta()
            self._send_changed_records(song)
            self._log("Live Session shape updated incrementally")
        else:
            self._active_sync_id = None
            self._active_shape_revision = -1
        if send_sync and self._link_active and not append_or_trim_only:
            self._request_full_sync("session shape changed", immediate=False)
        return True

    @staticmethod
    def _window_objects_are_prefix_compatible(previous, current):
        if previous is None:
            return False
        shorter, longer = (previous, current) if len(previous) <= len(current) else (current, previous)
        return Launch._same_live_objects(shorter, longer[:len(shorter)])

    @staticmethod
    def _same_live_objects(previous, current):
        if previous is None or len(previous) != len(current):
            return False
        for old, new in zip(previous, current):
            try:
                if (not _liveobj_valid(old) or not _liveobj_valid(new)
                        or _liveobj_changed(old, new)):
                    return False
            except Exception:
                return False
        return True

    def _payload_window_matches(self, track_hi, track_lo, scene_hi, scene_lo):
        return (join_u14(track_hi, track_lo) == self._track_offset
                and join_u14(scene_hi, scene_lo) == self._scene_offset)

    def _payload_generation_matches(self, high, low):
        return (self._active_sync_id is not None
                and not self._sync_pending
                and self._sync_in_flight is None
                and self._shape_revision == self._active_shape_revision
                and join_u14(high, low) == self._active_sync_id)

    def _navigate(self, direction, step):
        if direction not in (1, 2, 3, 4, 5) or step not in (0, 1, 8):
            return False
        if (direction == 5) != (step == 0):
            return False
        self._update_session_shape(self.song, send_sync=False)
        if self._session_ring is None:
            self._log("Navigation ignored because Session Ring is unavailable")
            return False
        track_offset, scene_offset = self._track_offset, self._scene_offset
        if direction == 1:
            track_offset -= step
        elif direction == 2:
            track_offset += step
        elif direction == 3:
            scene_offset -= step
        elif direction == 4:
            scene_offset += step
        else:
            track_offset = scene_offset = 0
        track_offset = min(max(0, track_offset), max(0, self._track_count - 8))
        scene_offset = min(max(0, scene_offset), max(0, self._scene_count - 8))
        if (track_offset, scene_offset) == (self._track_offset, self._scene_offset):
            return False
        if not self._set_ring_offsets(track_offset, scene_offset):
            return False
        self._track_offset, self._scene_offset = track_offset, scene_offset
        tracks = list(getattr(self.song, "tracks", ()))
        scenes = list(getattr(self.song, "scenes", ()))
        self._window_tracks = tracks[track_offset:track_offset + 8]
        self._window_scenes = scenes[scene_offset:scene_offset + 8]
        self._log("Navigation updated Session Ring to track={} scene={}".format(
            track_offset, scene_offset))
        self._shape_revision += 1
        self._active_sync_id = None
        self._active_shape_revision = -1
        self._request_full_sync("navigation", immediate=True)
        return True

    def _set_record_length(self, selected_code, observed_code):
        if (not isinstance(selected_code, int) or not 0 <= selected_code <= 7
                or observed_code != self._record_length_code):
            self._log("Ignored stale or invalid Rec Length request")
            if self._active_sync_id is not None:
                self._send(REC_LENGTH_STATE, split_u14(self._active_sync_id)
                           + (self._record_length_code,))
            return False
        self._record_length_code = (0 if selected_code == observed_code
                                    else selected_code)
        self._log("Rec Length changed to {} Bars".format(
            0 if self._record_length_code == 0
            else RECORD_LENGTHS[self._record_length_code - 1]))
        if self._active_sync_id is not None:
            self._send(REC_LENGTH_STATE, split_u14(self._active_sync_id)
                       + (self._record_length_code,))
        return True

    def _send_window_meta(self):
        if self._active_sync_id is None:
            return False
        payload = split_u14(self._active_sync_id)
        for value in (self._track_offset, self._scene_offset,
                      self._track_count, self._scene_count):
            payload += split_u14(value)
        return self._send(WINDOW_META, payload)

    def _log(self, message):
        try:
            self._launch_host.log_message(message)
        except Exception:
            # A diagnostic logger must not prevent Live from loading the script.
            try:
                _logger.info(message)
            except Exception:
                pass

    def _send(self, message, payload=()):
        self._sequence = (self._sequence + 1) & 0x7F
        frame = encode_frame(message, self._sequence, payload)
        sent = self._send_midi(SYSEX_PREFIX + frame + (0xF7,))
        if sent is False:
            self._log("Launch MIDI send failed: type={} sequence={}".format(message, self._sequence))
        return sent

    def receive_midi(self, midi_bytes):
        """Keep a direct parser entry for isolated tests; Live uses the element."""
        self._handle_protocol_message(midi_bytes)

    def _on_sysex(self, midi_bytes):
        self._handle_protocol_message(midi_bytes)

    def _handle_protocol_message(self, midi_bytes):
        decoded = decode_frame(midi_bytes)
        if decoded is None:
            return
        message, _sequence, payload = decoded
        now = _clock()
        if message == HELLO:
            self._last_device_message = now
            self._log("Launch received HELLO; sending HELLO_ACK")
            self._send(HELLO_ACK)
        elif message == REQUEST_FULL_SYNC:
            self._last_device_message = now
            self._link_active = True
            self._log("Launch received REQUEST_FULL_SYNC")
            if (self._sync_in_flight is None and self._active_sync_id is None
                    and not self._sync_pending):
                self._request_full_sync("device request", immediate=True)
        elif message == HEARTBEAT:
            if self._link_active:
                self._last_device_message = now
        elif self._link_active and message == SYNC_ACK and len(payload) == 3:
            sync_id = join_u14(payload[0], payload[1])
            task = self._sync_in_flight
            if (task is None or task["id"] != sync_id or not task["awaiting_ack"]
                    or not task["awaiting_final_ack"]):
                self._log("Ignored stale SYNC_ACK id={}".format(sync_id))
                return
            self._last_device_message = now
            if (payload[2] == 1 and task["shape_revision"] == self._shape_revision
                    and not self._sync_pending):
                self._active_sync_id = sync_id
                self._active_shape_revision = self._shape_revision
                self._last_snapshot = task["snapshot"]
                self._sync_in_flight = None
                self._log("Launch sync committed by device id={}".format(sync_id))
            else:
                self._log("Device rejected or superseded sync id={}".format(sync_id))
                self._sync_in_flight = None
                self._active_sync_id = None
                self._active_shape_revision = -1
                self._sync_pending = True
                self._sync_due_at = now + SYNC_MIN_INTERVAL_SECONDS
        elif self._link_active and message == SYNC_ACK and len(payload) == 4:
            sync_id = join_u14(payload[0], payload[1])
            task = self._sync_in_flight
            if (task is None or task["id"] != sync_id or not task["awaiting_ack"]
                    or payload[3] != task["expected_sequence"]):
                self._log("Ignored stale SYNC_CREDIT id={} sequence={}".format(
                    sync_id, payload[3]))
                return
            self._last_device_message = now
            if (payload[2] == 2 and not task["awaiting_final_ack"]
                    and task["shape_revision"] == self._shape_revision):
                task["awaiting_ack"] = False
                task["deadline"] = 0.0
                self._next_sync_frame_at = now + SYNC_FRAME_INTERVAL_SECONDS
            else:
                self._log("Device rejected sync frame id={} sequence={}".format(
                    sync_id, payload[3]))
                self._sync_in_flight = None
                self._sync_pending = True
                self._sync_due_at = now + SYNC_MIN_INTERVAL_SECONDS
                self._active_sync_id = None
                self._active_shape_revision = -1
        elif self._link_active and message == GRID_PRESS and len(payload) == 7 and payload[0] < 64:
            self._last_device_message = now
            if (self._payload_generation_matches(payload[5], payload[6])
                    and self._payload_window_matches(payload[1], payload[2], payload[3], payload[4])):
                self._grid_press(payload[0])
            else:
                self._log("Ignored stale Clip action for previous Ring window")
        elif self._link_active and message == TRACK_ACTION and len(payload) == 8:
            self._last_device_message = now
            if (not self._payload_generation_matches(payload[6], payload[7])
                    or not self._payload_window_matches(payload[2], payload[3], payload[4], payload[5])):
                self._log("Ignored stale Track action for previous Ring window")
                return
            track_index = self._track_offset + payload[0]
            if payload[0] >= 8 or track_index >= self._track_count:
                return
            if payload[1] == 4:
                self._cancel_track_pending(track_index)
            if apply_track_action(self.song, track_index, payload[1]):
                self._send_changed_records(self.song)
        elif self._link_active and message == SCENE_ACTION and len(payload) == 8:
            self._last_device_message = now
            if (self._payload_generation_matches(payload[6], payload[7])
                    and self._payload_window_matches(payload[2], payload[3], payload[4], payload[5])):
                if payload[0] < 8:
                    self._scene_action(self._scene_offset + payload[0], payload[1])
            else:
                self._log("Ignored stale Scene action for previous Ring window")
        elif self._link_active and message == NAVIGATION and len(payload) == 8:
            self._last_device_message = now
            if (self._payload_generation_matches(payload[6], payload[7])
                    and self._payload_window_matches(payload[2], payload[3], payload[4], payload[5])):
                self._navigate(payload[0], payload[1])
            else:
                self._log("Ignored stale Navigation action for previous Ring window")
        elif self._link_active and message == REC_LENGTH and len(payload) == 4:
            self._last_device_message = now
            if self._payload_generation_matches(payload[2], payload[3]):
                self._set_record_length(payload[0], payload[1])
            else:
                self._log("Ignored stale Rec Length action")

    def _send_full_sync(self):
        self._request_full_sync("explicit request", immediate=True)

    def _request_full_sync(self, reason, immediate=False):
        now = _clock()
        self._sync_pending = True
        self._sync_reason = reason
        self._sync_due_at = now if immediate else now + SYNC_DEBOUNCE_SECONDS
        self._active_sync_id = None
        self._active_shape_revision = -1

    def _start_full_sync(self, now):
        if self._sync_in_flight is not None:
            return False
        self._update_session_shape(self.song, send_sync=False)
        self._sync_id = (self._sync_id + 1) & 0x3FFF
        records = self._snapshot_records()
        sync_id = self._sync_id
        metadata = split_u14(sync_id) + (len(records),)
        for value in (self._track_offset, self._scene_offset,
                      self._track_count, self._scene_count):
            metadata += split_u14(value)
        metadata += (self._record_length_code,)
        frames = [(SYNC_BEGIN, metadata)]
        frames.extend((SYNC_DATA, split_u14(sync_id) + chunk)
                      for chunk in pack_sync_records(records, SYNC_DATA_BUDGET))
        frames.append((SYNC_END, split_u14(sync_id)))
        self._sync_in_flight = {
            "id": sync_id,
            "frames": frames,
            "snapshot": {(kind, record_id): value
                         for kind, record_id, value in records},
            "shape_revision": self._shape_revision,
            "awaiting_ack": False,
            "awaiting_final_ack": False,
            "expected_sequence": None,
            "deadline": 0.0,
        }
        self._sync_pending = False
        self._last_full_sync_at = now
        self._log("Launch sync queued id={} records={} frames={} reason={}".format(
            sync_id, len(records), len(frames), self._sync_reason))
        return True

    def _service_full_sync(self, now):
        task = self._sync_in_flight
        if task is not None and task["awaiting_ack"]:
            if now < task["deadline"]:
                return
            self._log("Launch sync credit timeout id={} sequence={}; scheduling retry".format(
                task["id"], task["expected_sequence"]))
            self._sync_in_flight = None
            self._sync_pending = True
            self._sync_due_at = now + SYNC_MIN_INTERVAL_SECONDS
            self._active_sync_id = None
            self._active_shape_revision = -1
            return
        if task is not None:
            if not task["frames"] or now < self._next_sync_frame_at:
                return
            message, payload = task["frames"].pop(0)
            self._send(message, payload)
            task["expected_sequence"] = self._sequence
            task["awaiting_ack"] = True
            task["awaiting_final_ack"] = message == SYNC_END
            task["deadline"] = now + SYNC_ACK_TIMEOUT_SECONDS
            self._next_sync_frame_at = now + SYNC_FRAME_INTERVAL_SECONDS
            if message == SYNC_END:
                self._log("Launch sync frames sent id={}; awaiting device commit".format(
                    task["id"]))
            else:
                self._log("Launch sync frame sent id={} type={} sequence={}; awaiting credit".format(
                    task["id"], message, self._sequence))
            return
        if not self._sync_pending or now < self._sync_due_at:
            return
        if now - self._last_full_sync_at < SYNC_MIN_INTERVAL_SECONDS:
            self._sync_due_at = self._last_full_sync_at + SYNC_MIN_INTERVAL_SECONDS
            return
        if self._start_full_sync(now):
            task = self._sync_in_flight
            message, payload = task["frames"].pop(0)
            self._send(message, payload)
            task["expected_sequence"] = self._sequence
            task["awaiting_ack"] = True
            task["awaiting_final_ack"] = message == SYNC_END
            task["deadline"] = now + SYNC_ACK_TIMEOUT_SECONDS
            self._next_sync_frame_at = now + SYNC_FRAME_INTERVAL_SECONDS
            self._log("Launch sync frame sent id={} type={} sequence={}; awaiting {}".format(
                task["id"], message, self._sequence,
                "device commit" if message == SYNC_END else "credit"))

    def _send_record(self, kind, record_id, value):
        if self._active_sync_id is None:
            return
        generation = split_u14(self._active_sync_id)
        if kind == "color":
            self._send(TRACK_COLOR, generation + (record_id,) + tuple(value))
        elif kind == "flags":
            self._send(TRACK_STATE, generation + (record_id, value))
        elif kind == "scene":
            self._send(SCENE_STATE, generation + (record_id, value))
        else:
            self._send(SLOT_STATE, generation + (record_id, value))

    def _send_changed_records(self, song):
        if (self._active_sync_id is None or self._sync_pending
                or self._sync_in_flight is not None):
            return
        records = self._snapshot_records(song)
        current = {(kind, record_id): value for kind, record_id, value in records}
        sent = 0
        for key, value in current.items():
            if self._last_snapshot.get(key) != value:
                self._send_record(key[0], key[1], value)
                self._last_snapshot[key] = value
                sent += 1
                if sent >= 8:
                    break

    def _snapshot_records(self, song=None):
        song = song if song is not None else self.song
        queued_scenes = tuple(key[1] for key in self._bar_pending
                              if key[0] == "scene")
        records = snapshot_payloads(song, queued_scenes,
                                    self._track_offset, self._scene_offset)
        overrides = {}
        for (track_index, scene_index), (_clip_id, kind, _previous) in self._pending.items():
            if (self._track_offset <= track_index < self._track_offset + 8
                    and self._scene_offset <= scene_index < self._scene_offset + 8):
                local_slot = ((scene_index - self._scene_offset) * 8
                              + track_index - self._track_offset)
                overrides[local_slot] = (RECORD_END_QUEUED if kind == "record_end"
                                         else STOP_QUEUED)
        for task in self._bar_pending.values():
            for target in task["targets"]:
                track_index, scene_index = target["track_index"], target["slot_index"]
                if (self._track_offset <= track_index < self._track_offset + 8
                        and self._scene_offset <= scene_index < self._scene_offset + 8):
                    local_slot = ((scene_index - self._scene_offset) * 8
                                  + track_index - self._track_offset)
                    overrides[local_slot] = STOP_QUEUED
        return [(kind, record_id, overrides.get(record_id, value) if kind == "slot" else value)
                for kind, record_id, value in records]

    def _cancel_track_pending(self, track_index):
        for key in list(self._pending):
            if key[0] == track_index:
                self._pending.pop(key, None)
        self._remove_bar_targets(lambda target: target["track_index"] == track_index)

    def _remove_bar_targets(self, predicate):
        for key, task in list(self._bar_pending.items()):
            task["targets"] = [target for target in task["targets"]
                               if not predicate(target)]
            if not task["targets"]:
                self._bar_pending.pop(key, None)

    def _scene_action(self, scene_index, action):
        try:
            song = self.song
            scenes = list(song.scenes)
            if not isinstance(scene_index, int) or not 0 <= scene_index < len(scenes):
                return False
            scene = scenes[scene_index]
            if action == 1:
                try:
                    if bool(scene.is_triggered):
                        return False
                except Exception as exc:
                    self._log("Cannot verify Scene launch queue: {}".format(exc))
                    return False
                scene.fire()
                self._log("Scene {} launch requested".format(scene_index + 1))
            elif action == 2:
                key = ("scene", scene_index)
                if key in self._bar_pending:
                    return False
                targets = collect_scene_targets(song, scene_index)
                if not targets:
                    return False
                for target in targets:
                    track_index, slot_index = target[:2]
                    self._pending.pop((track_index, slot_index), None)
                target_keys = set((target[0], target[1]) for target in targets)
                self._remove_bar_targets(lambda target: (
                    target["track_index"], target["slot_index"]) in target_keys)
                if not self._queue_scene_bar_stop(song, key, targets):
                    return False
                self._log("Scene {} stop queued targets={}".format(
                    scene_index + 1, len(targets)))
            else:
                return False
            self._send_changed_records(song)
            return True
        except Exception as exc:
            self._log("Scene action failed: {}".format(exc))
            return False

    def _queue_scene_bar_stop(self, song, key, targets):
        """Queue identity-checked Scene targets for the next Live bar boundary."""
        try:
            song_time = float(song.current_song_time)
            numerator = int(song.signature_numerator)
            denominator = int(song.signature_denominator)
            target_time = current_bar_end_boundary(song_time, numerator, denominator)
        except Exception as exc:
            self._log("Cannot schedule Scene stop at Live bar boundary: {}".format(exc))
            return False

        packed_targets = []
        for track_index, slot_index, track, slot, clip, _clip_id in targets:
            packed_targets.append({
                "track_index": track_index,
                "slot_index": slot_index,
                "track": track,
                "slot": slot,
                "clip": clip,
                "mode": "scene_scheduler",
            })
        self._bar_pending[key] = {
            "kind": "scene_stop",
            "targets": packed_targets,
            "target_time": target_time,
            "signature": (numerator, denominator),
            "previous_song_time": song_time,
            "previous_sample_at": _clock(),
            "previous_tempo": float(getattr(song, "tempo", 120.0)),
        }
        self._log("Scene stop scheduled at bar boundary: scene={} time={:.6f} targets={}".format(
            key[1] + 1, target_time, len(packed_targets)))
        return True

    def _queue_bar_stop(self, song, key, targets, kind):
        prepared = []
        packed_targets = []
        for target in targets:
            track_index, slot_index, track, slot, clip, _clip_id = target
            stop_slot = self._find_track_stop_slot(track)
            if stop_slot is None:
                self._log("Cannot queue current-bar stop: track {} has no empty Stop Button slot".format(
                    track_index + 1))
                return False
            slots = list(track.clip_slots)
            stop_slot_index = next((index for index, candidate in enumerate(slots)
                                    if not _liveobj_changed(candidate, stop_slot)), -1)
            if stop_slot_index < 0:
                self._log("Cannot resolve Stop Button slot index for track {}".format(
                    track_index + 1))
                return False
            prepared.append((track_index, stop_slot, stop_slot_index))
            packed_targets.append({
                "track_index": track_index,
                "slot_index": slot_index,
                "track": track,
                "slot": slot,
                "clip": clip,
                "stop_slot": stop_slot,
                "stop_slot_index": stop_slot_index,
            })
        fired = []
        for track_index, stop_slot, _stop_slot_index in prepared:
            try:
                stop_slot.fire(launch_quantization=BAR_LAUNCH_QUANTIZATION)
                fired.append(track_index)
            except Exception as exc:
                self._log("Native quantized Stop Button failed track={}: {}".format(
                    track_index + 1, exc))
                if fired:
                    self._log("Partial native stop queue: tracks={}".format(
                        ",".join(str(index + 1) for index in fired)))
                return False
        self._bar_pending[key] = {
            "kind": kind,
            "targets": packed_targets,
            "queued_at": _clock(),
        }
        try:
            song_time = float(song.current_song_time)
            signature = "{}/{}".format(int(song.signature_numerator),
                                        int(song.signature_denominator))
        except Exception:
            song_time = -1.0
            signature = "unknown"
        self._log("Native one-bar stop fired kind={} targets={} quantization={} "
                  "song_time={:.6f} signature={}".format(
                      kind, len(packed_targets), BAR_LAUNCH_QUANTIZATION,
                      song_time, signature))
        return True

    @staticmethod
    def _find_track_stop_slot(track):
        try:
            for slot in list(track.clip_slots):
                if bool(getattr(slot, "is_group_slot", False)) or bool(slot.has_clip):
                    continue
                if bool(slot.has_stop_button):
                    return slot
        except Exception:
            return None
        return None

    def _process_bar_pending(self, song):
        if not self._bar_pending:
            return
        try:
            if not bool(song.is_playing):
                self._bar_pending.clear()
                return
            tracks = list(song.tracks)
            song_time = float(song.current_song_time)
            signature = (int(song.signature_numerator),
                         int(song.signature_denominator))
        except Exception as exc:
            self._log("Cannot validate queued bar stop: {}".format(exc))
            self._bar_pending.clear()
            return

        for key, task in list(self._bar_pending.items()):
            scene_scheduler = task.get("kind") == "scene_stop"
            if scene_scheduler:
                if signature != task["signature"]:
                    self._bar_pending.pop(key, None)
                    self._log("Cancelled Scene stop after time signature changed")
                    continue
                previous_time = task["previous_song_time"]
                if song_time < previous_time - 0.001:
                    self._bar_pending.pop(key, None)
                    self._log("Cancelled Scene stop after Song Position moved backward")
                    continue
                now = _clock()
                elapsed = max(0.0, now - task["previous_sample_at"])
                try:
                    tempo = max(float(song.tempo), 20.0)
                except Exception:
                    tempo = 120.0
                actual_advance = song_time - previous_time
                expected_advance = elapsed * (
                    task["previous_tempo"] + tempo) / 120.0
                allowed_advance_error = max(0.12, expected_advance * 0.30)
                if abs(actual_advance - expected_advance) > allowed_advance_error:
                    self._bar_pending.pop(key, None)
                    self._log("Cancelled Scene stop after Song Position jump: actual={:.4f} expected={:.4f} tolerance={:.4f}".format(
                        actual_advance, expected_advance, allowed_advance_error))
                    continue
                task["previous_song_time"] = song_time
                task["previous_sample_at"] = now
                task["previous_tempo"] = tempo
            live_targets = []
            for target in task["targets"]:
                track_index = target["track_index"]
                slot_index = target["slot_index"]
                if track_index >= len(tracks):
                    continue
                track = tracks[track_index]
                try:
                    if (not _liveobj_valid(target["track"])
                            or _liveobj_changed(target["track"], track)):
                        continue
                except Exception:
                    continue
                slots = list(track.clip_slots)
                if slot_index >= len(slots):
                    continue
                slot = slots[slot_index]
                try:
                    if (not _liveobj_valid(target["slot"])
                            or _liveobj_changed(target["slot"], slot)):
                        continue
                    if (not bool(slot.has_clip)
                            or not _liveobj_valid(target["clip"])
                            or _liveobj_changed(target["clip"], slot.clip)
                            or not (bool(target["clip"].is_playing)
                                    or bool(target["clip"].is_recording))):
                        continue
                    try:
                        active_index = int(track.playing_slot_index)
                    except Exception:
                        active_index = -1
                    if active_index >= 0 and active_index != slot_index:
                        continue
                    if scene_scheduler and active_index != slot_index:
                        if not (active_index < 0 and bool(target["clip"].is_recording)):
                            continue
                    try:
                        fired_index = int(track.fired_slot_index)
                    except Exception:
                        fired_index = -1
                    if scene_scheduler:
                        if fired_index not in (-1, slot_index):
                            continue
                    elif (fired_index >= 0 and fired_index != slot_index
                          and fired_index != target["stop_slot_index"]):
                        continue
                except Exception:
                    continue
                live_targets.append(target)

            task["targets"] = live_targets
            if not live_targets:
                self._bar_pending.pop(key, None)
                self._log("Cleared queued stop after original target ended or changed")
            elif scene_scheduler and song_time >= task["target_time"]:
                stopped = []
                for target in live_targets:
                    try:
                        target["track"].stop_all_clips(False)
                        stopped.append(target["track_index"] + 1)
                    except Exception as exc:
                        self._log("Scene stop failed at bar boundary track={}: {}".format(
                            target["track_index"] + 1, exc))
                self._bar_pending.pop(key, None)
                self._log("Scene stop boundary processed scene={} tracks={}".format(
                    key[1] + 1, ",".join(str(index) for index in stopped)))
            else:
                task["targets"] = live_targets

    def _grid_press(self, slot_id):
        local_track, local_scene = slot_id % 8, slot_id // 8
        track_index = self._track_offset + local_track
        scene_index = self._scene_offset + local_scene
        try:
            song = self.song
            tracks = list(song.tracks)
            if track_index >= len(tracks):
                return
            track = tracks[track_index]
            slots = list(track.clip_slots)
            if scene_index >= len(slots):
                return
            slot = slots[scene_index]
            clip = slot.clip if slot.has_clip else None
            try:
                transport_running = bool(song.is_playing)
            except Exception:
                transport_running = True
            status = self._slot_status(track, scene_index, slot, clip, transport_running)
            key = (track_index, scene_index)
            if key in self._pending or status in (STOP_QUEUED, RECORD_END_QUEUED, LAUNCH_QUEUED):
                return
            if clip is None:
                if bool(track.arm):
                    if self._record_length_code:
                        bars = RECORD_LENGTHS[self._record_length_code - 1]
                        numerator = int(song.signature_numerator)
                        denominator = int(song.signature_denominator)
                        beats = record_length_beats(bars, numerator, denominator)
                        slot.fire(record_length=beats)
                        self._log("Started fixed recording: track={} scene={} bars={} beats={}".format(
                            track_index, scene_index, bars, beats))
                        self._log_empty_record_state(song, track, slot, track_index,
                                                     scene_index, transport_running)
                    else:
                        slot.fire()
                        self._log_empty_record_state(song, track, slot, track_index,
                                                     scene_index, transport_running)
                else:
                    try:
                        transport_running = bool(song.is_playing)
                    except Exception:
                        transport_running = True
                    active = active_clip_in_track(track) if transport_running else None
                    if active is not None and not bool(active[1].is_recording):
                        active_index, active_clip = active
                        all_slots = list(track.clip_slots)
                        if active_index >= len(all_slots):
                            return
                        active_slot = all_slots[active_index]
                        key = ("slot", track_index, active_index)
                        if key in self._bar_pending:
                            return
                        self._pending.pop((track_index, active_index), None)
                        self._remove_bar_targets(lambda target: (
                            target["track_index"] == track_index
                            and target["slot_index"] == active_index))
                        target = (track_index, active_index, track, active_slot,
                                  active_clip, id(active_clip))
                        if self._queue_bar_stop(song, key, [target], "slot_stop"):
                            self._log("Current-bar stop queued track={} scene={}".format(
                                track_index + 1, scene_index + 1))
                            self._send_changed_records(song)
            elif status == STOPPED:
                slot.fire()
            elif status == PLAYING:
                self._pending[key] = (id(clip), "stop", None)
            elif status == RECORDING:
                slot.fire()
                self._pending[key] = (id(clip), "record_end", None)
                self._send_changed_records(song)
        except Exception as exc:
            self._log("Launch grid request failed: {}".format(exc))

    def _log_empty_record_state(self, song, track, slot, track_index,
                                scene_index, transport_running):
        try:
            triggered = bool(slot.is_triggered)
        except Exception:
            triggered = "unavailable"
        try:
            fired_index = int(track.fired_slot_index)
        except Exception:
            fired_index = "unavailable"
        try:
            song_time = float(song.current_song_time)
        except Exception:
            song_time = "unavailable"
        try:
            tempo = float(song.tempo)
        except Exception:
            tempo = "unavailable"
        self._log("Armed empty slot fire state: track={} scene={} transport={} "
                  "triggered={} fired_slot={} tempo={} song_time={}".format(
                      track_index + 1, scene_index + 1, transport_running,
                      triggered, fired_index, tempo, song_time))

    @staticmethod
    def _slot_status(track, scene_index, slot, clip, transport_running=True):
        return _slot_state(track, scene_index, slot, transport_running)

    def _poll(self):
        try:
            song = self.song
            try:
                transport_running = bool(song.is_playing)
            except Exception:
                transport_running = True
            if not transport_running and self._pending:
                self._log("Live transport stopped; clearing {} pending task(s)".format(
                    len(self._pending)))
                self._pending.clear()
            self._update_session_shape(song)
            tracks = list(song.tracks)
            for key, (clip_id, kind, previous) in list(self._pending.items()):
                track_index, scene_index = key
                if track_index >= len(tracks):
                    self._pending.pop(key, None)
                    continue
                track = tracks[track_index]
                slots = list(track.clip_slots)
                if scene_index >= len(slots):
                    self._pending.pop(key, None)
                    continue
                slot = slots[scene_index]
                clip = slot.clip if slot.has_clip else None
                if clip is None or id(clip) != clip_id:
                    self._pending.pop(key, None)
                    continue
                if kind == "stop":
                    try:
                        position = float(clip.playing_position)
                        if not bool(clip.is_playing):
                            self._pending.pop(key, None)
                        elif previous is not None and position < previous and bool(clip.looping):
                            slot.stop()
                            self._pending.pop(key, None)
                        else:
                            self._pending[key] = (clip_id, kind, position)
                    except Exception:
                        self._pending.pop(key, None)
                elif kind == "record_end" and not bool(clip.is_recording):
                    self._pending.pop(key, None)
            self._process_bar_pending(song)
            if self._link_active and _clock() - self._last_device_message <= 3.0:
                self._service_full_sync(_clock())
                if self._sync_in_flight is None and not self._sync_pending:
                    self._send_changed_records(song)
                self._poll_count += 1
                if self._poll_count >= 4:
                    self._poll_count = 0
                    try:
                        tempo = int(round(float(song.tempo) * 10.0))
                    except Exception:
                        tempo = 1200
                    tempo = max(200, min(9999, tempo))
                    try:
                        phase_u14 = int((float(song.current_song_time) % 4.0)
                                        * 4096.0 + 0.5) % 0x4000
                    except Exception:
                        phase_u14 = 0
                    try:
                        playing = 1 if bool(song.is_playing) else 0
                    except Exception:
                        playing = 0
                    self._send(HEARTBEAT, (tempo >> 7, tempo & 0x7F,
                                           phase_u14 >> 7, phase_u14 & 0x7F,
                                           playing))
            else:
                self._link_active = False
                self._poll_count = 0
                self._sync_pending = False
                self._sync_in_flight = None
                self._active_sync_id = None
                self._active_shape_revision = -1
        except Exception as exc:
            self._log("Launch poll failed: {}".format(exc))
        self.schedule_message(1, self._poll)


def create_instance(c_instance):
    return Launch(c_instance)
