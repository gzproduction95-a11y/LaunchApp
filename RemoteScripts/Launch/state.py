"""Device-side mirror of the current Live Session Ring window."""

EMPTY = 0
STOPPED = 1
PLAYING = 2
RECORDING = 3
STOP_QUEUED = 4
RECORD_END_QUEUED = 5
LAUNCH_QUEUED = 6

try:
    from .phase import MusicalPhaseClock
except ImportError:
    from phase import MusicalPhaseClock


def join_u14(high, low):
    if (not isinstance(high, int) or not isinstance(low, int)
            or not 0 <= high <= 127 or not 0 <= low <= 127):
        return -1
    return high * 128 + low


class SessionState:
    def __init__(self):
        self.tempo = 120.0
        self.phase_clock = MusicalPhaseClock()
        self.tracks = [{"valid": False, "color": (0, 0, 0), "arm": False, "mute": False, "solo": False, "active": False} for _ in range(8)]
        self.slots = [{"valid": False, "status": EMPTY} for _ in range(64)]
        self.scenes = [self._scene_from_flags(0) for _ in range(8)]
        self._sync = None
        self.sync_id = None
        self.track_offset = 0
        self.scene_offset = 0
        self.track_count = 0
        self.scene_count = 0
        self.rec_length_code = 0
        self.synced = False

    def update_track_color(self, track_id, color):
        if not self._valid_track(track_id) or not self._valid_color(color):
            return False
        self.tracks[track_id]["color"] = tuple(color)
        return True

    def update_track_flags(self, track_id, flags):
        if not self._valid_track(track_id) or not isinstance(flags, int) or flags < 0 or flags > 31:
            return False
        track = self.tracks[track_id]
        track["valid"] = bool(flags & 16)
        track["arm"] = bool(flags & 1)
        track["mute"] = bool(flags & 2)
        track["solo"] = bool(flags & 4)
        track["active"] = bool(flags & 8)
        return True

    def update_slot(self, slot_id, status):
        if not self._valid_slot(slot_id, status):
            return False
        self.slots[slot_id]["valid"] = True
        self.slots[slot_id]["status"] = status
        return True

    def apply_incremental(self, message_type, payload):
        """Apply one Live update directly to the committed display mirror."""
        if self._sync is not None or self.sync_id is None or len(payload) < 3:
            return False
        if join_u14(payload[0], payload[1]) != self.sync_id:
            return False
        payload = payload[2:]
        if message_type == 19 and len(payload) == 4:
            return self.update_track_color(payload[0], payload[1:4])
        if message_type == 20 and len(payload) == 2:
            return self.update_track_flags(payload[0], payload[1])
        if message_type == 21 and len(payload) == 2:
            return self.update_slot(payload[0], payload[1])
        if message_type == 25 and len(payload) == 2:
            return self.update_scene(payload[0], payload[1])
        return False

    def update_window_meta(self, sync_id, track_offset, scene_offset,
                           track_count, scene_count):
        if (self.sync_id != sync_id
                or any(not isinstance(value, int) or not 0 <= value <= 0x3FFF
                       for value in (track_offset, scene_offset, track_count, scene_count))
                or track_offset > max(0, track_count - 8)
                or scene_offset > max(0, scene_count - 8)):
            return False
        self.track_offset = track_offset
        self.scene_offset = scene_offset
        self.track_count = track_count
        self.scene_count = scene_count
        return True

    def begin_sync(self, sync_id, expected_count, track_offset=0, scene_offset=0,
                   track_count=8, scene_count=8, rec_length_code=0):
        if not isinstance(sync_id, int) or not 0 <= sync_id <= 0x3FFF:
            return False
        if not isinstance(expected_count, int) or not 1 <= expected_count <= 88:
            return False
        values = (track_offset, scene_offset, track_count, scene_count)
        if any(not isinstance(value, int) or not 0 <= value <= 0x3FFF
               for value in values):
            return False
        if not isinstance(rec_length_code, int) or not 0 <= rec_length_code <= 7:
            return False
        if track_offset > max(0, track_count - 8):
            return False
        if scene_offset > max(0, scene_count - 8):
            return False
        self._sync = {
            "id": sync_id,
            "expected": expected_count,
            "track_offset": track_offset,
            "scene_offset": scene_offset,
            "track_count": track_count,
            "scene_count": scene_count,
            "rec_length_code": rec_length_code,
            "seen": set(),
            "tracks": [{"valid": False, "color": (0, 0, 0), "arm": False, "mute": False, "solo": False, "active": False} for _ in range(8)],
            "slots": [{"valid": False, "status": EMPTY} for _ in range(64)],
            "scenes": [self._scene_from_flags(0) for _ in range(8)],
        }
        return True

    def stage_track_color(self, track_id, color):
        if self._sync is None or not self._valid_track(track_id) or not self._valid_color(color):
            return False
        track = self._sync["tracks"][track_id]
        track["color"] = tuple(color)
        self._sync["seen"].add(("color", track_id))
        return True

    def stage_track_flags(self, track_id, flags):
        if self._sync is None or not self._valid_track(track_id) or not isinstance(flags, int) or flags < 0 or flags > 31:
            return False
        track = self._sync["tracks"][track_id]
        track["valid"] = bool(flags & 16)
        track["arm"] = bool(flags & 1)
        track["mute"] = bool(flags & 2)
        track["solo"] = bool(flags & 4)
        track["active"] = bool(flags & 8)
        self._sync["seen"].add(("flags", track_id))
        return True

    def stage_slot(self, slot_id, status):
        if self._sync is None or not self._valid_slot(slot_id, status):
            return False
        self._sync["slots"][slot_id]["valid"] = True
        self._sync["slots"][slot_id]["status"] = status
        self._sync["seen"].add(("slot", slot_id))
        return True

    def update_scene(self, scene_id, flags):
        if not self._valid_scene(scene_id, flags):
            return False
        self.scenes[scene_id] = self._scene_from_flags(flags)
        return True

    def stage_scene(self, scene_id, flags):
        if self._sync is None or not self._valid_scene(scene_id, flags):
            return False
        self._sync["scenes"][scene_id] = self._scene_from_flags(flags)
        self._sync["seen"].add(("scene", scene_id))
        return True

    def end_sync(self, sync_id):
        if self._sync is None or sync_id != self._sync["id"]:
            return False
        if len(self._sync["seen"]) != self._sync["expected"]:
            self._sync = None
            return False
        self.tracks = self._sync["tracks"]
        self.slots = self._sync["slots"]
        self.scenes = self._sync["scenes"]
        self.track_offset = self._sync["track_offset"]
        self.scene_offset = self._sync["scene_offset"]
        self.track_count = self._sync["track_count"]
        self.scene_count = self._sync["scene_count"]
        self.rec_length_code = self._sync["rec_length_code"]
        self.sync_id = self._sync["id"]
        self._sync = None
        self.synced = True
        return True

    def abort_sync(self, sync_id=None):
        if self._sync is None:
            return False
        if sync_id is not None and sync_id != self._sync["id"]:
            return False
        self._sync = None
        return True


    @staticmethod
    def _valid_track(track_id):
        return isinstance(track_id, int) and 0 <= track_id < 8

    @staticmethod
    def _valid_color(color):
        return (
            isinstance(color, (tuple, list))
            and len(color) == 3
            and all(isinstance(value, int) and 0 <= value <= 127 for value in color)
        )

    @staticmethod
    def _valid_slot(slot_id, status):
        return isinstance(slot_id, int) and 0 <= slot_id < 64 and isinstance(status, int) and EMPTY <= status <= LAUNCH_QUEUED

    @staticmethod
    def _valid_scene(scene_id, flags):
        return (isinstance(scene_id, int) and 0 <= scene_id < 8
                and isinstance(flags, int) and 0 <= flags <= 7)

    @staticmethod
    def _scene_from_flags(flags):
        return {
            "valid": bool(flags & 1),
            "active": bool(flags & 2),
            "stop_queued": bool(flags & 4),
        }
