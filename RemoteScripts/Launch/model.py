"""Pure Live-object adapters used by the verified Live 12.4.6 integration."""

EMPTY, STOPPED, PLAYING, RECORDING = 0, 1, 2, 3
STOP_QUEUED, RECORD_END_QUEUED = 4, 5
LAUNCH_QUEUED = 6
TRACK_PRESENT = 16
SCENE_PRESENT = 1
SCENE_ACTIVE = 2
SCENE_STOP_QUEUED = 4

def _tracks(song):
    try:
        return list(song.tracks)
    except Exception:
        return []

def _slots(track):
    try:
        return list(track.clip_slots)
    except Exception:
        return []

def _color(color):
    value = int(color)
    return ((value >> 17) & 0x7F, (value >> 9) & 0x7F, (value >> 1) & 0x7F)

def _slot_state(track, slot_index, slot, transport_running=True):
    try:
        clip = slot.clip if slot.has_clip else None
    except Exception:
        clip = None
    if not transport_running:
        return STOPPED if clip is not None else EMPTY
    try:
        triggered = bool(slot.is_triggered)
    except Exception:
        triggered = False
    try:
        fired_index = int(track.fired_slot_index)
    except Exception:
        fired_index = -1
    try:
        recording = clip is not None and bool(clip.is_recording)
    except Exception:
        recording = False
    try:
        playing = clip is not None and bool(clip.is_playing)
    except Exception:
        playing = False
    if recording:
        if triggered:
            return RECORD_END_QUEUED
        return RECORDING
    if playing:
        if triggered:
            if fired_index == slot_index:
                return LAUNCH_QUEUED
            return STOP_QUEUED
        return PLAYING
    if triggered or fired_index == slot_index:
        return LAUNCH_QUEUED
    if clip is None:
        return EMPTY
    return STOPPED

def _track_active(track, transport_running=True):
    if not transport_running:
        return False
    try:
        if int(track.playing_slot_index) >= 0:
            return True
    except Exception:
        pass
    for index, slot in enumerate(_slots(track)):
        try:
            clip = slot.clip if slot.has_clip else None
        except Exception:
            clip = None
        if clip is not None:
            try:
                if bool(clip.is_playing) or bool(clip.is_recording):
                    return True
            except Exception:
                pass
        if _slot_state(track, index, slot) in (STOP_QUEUED, RECORD_END_QUEUED):
            return True
    return False

def snapshot_payloads(song, scene_stop_queued=(), track_offset=0, scene_offset=0):
    """Return an 8x8 state window projected from absolute Live indices."""
    tracks = _tracks(song)
    all_tracks = tracks
    try:
        scenes = list(song.scenes)
    except Exception:
        scenes = []
    track_offset = max(0, min(int(track_offset), max(0, len(tracks) - 8)))
    scene_offset = max(0, min(int(scene_offset), max(0, len(scenes) - 8)))
    try:
        transport_running = bool(song.is_playing)
    except Exception:
        transport_running = True
    messages = []
    for index in range(8):
        absolute_track = track_offset + index
        if absolute_track < len(tracks):
            track = tracks[absolute_track]
            try:
                rgb = _color(track.color)
            except Exception:
                rgb = (0, 0, 0)
            messages.append(("color", index, rgb))
            flags = TRACK_PRESENT
            for bit, name in ((1, "arm"), (2, "mute"), (4, "solo")):
                try:
                    if bool(getattr(track, name)):
                        flags |= bit
                except Exception:
                    pass
            if _track_active(track, transport_running):
                flags |= 8
            messages.append(("flags", index, flags))
        else:
            messages.append(("color", index, (0, 0, 0)))
            messages.append(("flags", index, 0))
    for slot_id in range(64):
        track_index = track_offset + slot_id % 8
        slot_index = scene_offset + slot_id // 8
        status = EMPTY
        if track_index < len(tracks):
            slots = _slots(tracks[track_index])
            if slot_index < len(slots):
                status = _slot_state(tracks[track_index], slot_index, slots[slot_index],
                                     transport_running)
        messages.append(("slot", slot_id, status))
    queued_scenes = set(scene_stop_queued)
    for local_scene in range(8):
        scene_index = scene_offset + local_scene
        flags = 0
        if scene_index < len(scenes):
            flags |= SCENE_PRESENT
            if transport_running:
                for track in all_tracks:
                    slots = _slots_all(track)
                    if scene_index >= len(slots):
                        continue
                    slot = slots[scene_index]
                    try:
                        if bool(getattr(slot, "is_group_slot", False)):
                            active = bool(slot.is_playing) or bool(slot.is_recording)
                        else:
                            clip = slot.clip if slot.has_clip else None
                            active = clip is not None and (
                                bool(clip.is_playing) or bool(clip.is_recording))
                    except Exception:
                        active = False
                    if active:
                        flags |= SCENE_ACTIVE
                        break
        if scene_index in queued_scenes:
            flags |= SCENE_STOP_QUEUED
        messages.append(("scene", local_scene, flags))
    return messages


def _slots_all(track):
    try:
        return list(track.clip_slots)
    except Exception:
        return []


def active_clip_in_track(track):
    """Return (slot_index, clip) for the active non-group Session Clip."""
    slots = _slots_all(track)
    try:
        playing_index = int(track.playing_slot_index)
    except Exception:
        playing_index = -1
    indexes = ([playing_index] if 0 <= playing_index < len(slots)
               else list(range(len(slots))))
    for index in indexes:
        slot = slots[index]
        try:
            if bool(getattr(slot, "is_group_slot", False)) or not bool(slot.has_clip):
                continue
            clip = slot.clip
            if bool(clip.is_playing) or bool(clip.is_recording):
                return index, clip
        except Exception:
            continue
    if indexes != list(range(len(slots))):
        for index, slot in enumerate(slots):
            if index in indexes:
                continue
            try:
                if bool(getattr(slot, "is_group_slot", False)) or not bool(slot.has_clip):
                    continue
                clip = slot.clip
                if bool(clip.is_playing) or bool(clip.is_recording):
                    return index, clip
            except Exception:
                continue
    return None


def collect_scene_targets(song, scene_index):
    """Capture active Clip identities in one Session row across all tracks."""
    try:
        scenes = list(song.scenes)
        tracks = list(song.tracks)
        transport_running = bool(song.is_playing)
    except Exception:
        return []
    if not 0 <= int(scene_index) < len(scenes) or not transport_running:
        return []
    targets = []
    for track_index, track in enumerate(tracks):
        slots = _slots_all(track)
        if scene_index >= len(slots):
            continue
        slot = slots[scene_index]
        try:
            if bool(getattr(slot, "is_group_slot", False)) or not bool(slot.has_clip):
                continue
            clip = slot.clip
            # Recording Clips are stopped at the boundary but remain in Live;
            # Launch never calls a delete API or discards their audio/MIDI.
            if bool(clip.is_playing) or bool(clip.is_recording):
                targets.append((track_index, scene_index, track, slot, clip, id(clip)))
        except Exception:
            continue
    return targets

def pack_sync_records(records, max_payload=46):
    """Pack typed records without splitting one record across a SysEx frame."""
    chunks = []
    current = []
    tags = {"color": 0, "flags": 1, "slot": 2, "scene": 3}
    for kind, record_id, value in records:
        if kind not in tags:
            continue
        item = [tags[kind], record_id]
        item.extend(value if kind == "color" else (value,))
        if len(item) > max_payload:
            raise ValueError("record is larger than a sync frame")
        if current and len(current) + len(item) > max_payload:
            chunks.append(tuple(current))
            current = []
        current.extend(item)
    if current:
        chunks.append(tuple(current))
    return chunks

def apply_track_action(song, track_index, action):
    tracks = _tracks(song)
    if not isinstance(track_index, int) or not 0 <= track_index < len(tracks):
        return False
    track = tracks[track_index]
    try:
        if action == 1 and bool(track.can_be_armed):
            track.arm = not bool(track.arm)
        elif action == 2:
            track.mute = not bool(track.mute)
        elif action == 3:
            track.solo = not bool(track.solo)
        elif action == 4:
            track.stop_all_clips()
        else:
            return False
        return True
    except Exception:
        return False
