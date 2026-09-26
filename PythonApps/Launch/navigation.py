"""Pure coordinate, viewport and recording-length helpers for Launch."""

BAR_OPTIONS = (1, 2, 4, 6, 8, 12, 16)


def record_length_code(bars):
    if bars in (None, 0, "unlimited"):
        return 0
    try:
        return BAR_OPTIONS.index(int(bars)) + 1
    except (TypeError, ValueError):
        raise ValueError("unsupported fixed recording length")


def bars_for_code(code):
    if not isinstance(code, int) or not 0 <= code <= len(BAR_OPTIONS):
        raise ValueError("invalid recording length code")
    return 0 if code == 0 else BAR_OPTIONS[code - 1]


def beats_for_bars(bars, numerator, denominator):
    bars = int(bars)
    numerator = int(numerator)
    denominator = int(denominator)
    if bars not in BAR_OPTIONS or numerator <= 0 or denominator <= 0:
        raise ValueError("invalid bar length or time signature")
    return float(bars * numerator * 4) / denominator


def split_u14(value):
    value = int(value)
    if not 0 <= value <= 0x3FFF:
        raise ValueError("value is outside unsigned 14-bit range")
    return (value >> 7, value & 0x7F)


def join_u14(high, low):
    if any(not isinstance(part, int) or not 0 <= part <= 0x7F
           for part in (high, low)):
        raise ValueError("14-bit parts must be 7-bit values")
    return high * 128 + low


def clamp_offsets(track_offset, scene_offset, track_count, scene_count):
    track_max = max(0, int(track_count) - 8)
    scene_max = max(0, int(scene_count) - 8)
    return (max(0, min(int(track_offset), track_max)),
            max(0, min(int(scene_offset), scene_max)))


def viewport_target(local_track, local_scene, track_offset, scene_offset,
                    track_count, scene_count):
    if not 0 <= int(local_track) < 8 or not 0 <= int(local_scene) < 8:
        return None
    track_index = int(track_offset) + int(local_track)
    scene_index = int(scene_offset) + int(local_scene)
    if track_index >= int(track_count) or scene_index >= int(scene_count):
        return None
    return track_index, scene_index
