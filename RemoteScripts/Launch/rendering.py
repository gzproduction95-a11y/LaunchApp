"""Pure Launch LED state mapping driven by shared Live and UI animation phases."""

from math import sin, pi

try:
    from .state import EMPTY, STOPPED, PLAYING, RECORDING, STOP_QUEUED, RECORD_END_QUEUED, LAUNCH_QUEUED
except ImportError:
    from state import EMPTY, STOPPED, PLAYING, RECORDING, STOP_QUEUED, RECORD_END_QUEUED, LAUNCH_QUEUED
try:
    from .navigation import bars_for_code
except ImportError:
    from navigation import bars_for_code

DIM = 8
ARM_RED = (0xFF0000, 0x080000)
MUTE_YELLOW = (0xFFFF00, 0x080800)
SOLO_BLUE = (0x0000FF, 0x000008)
STOP_MAGENTA = 0xFF0060
RECORD_RED = 0xFF0000
EMPTY_LEVEL = 25
REC_LENGTH_FILL = 0x0080FF
REC_LENGTH_ENDPOINT = 0x40C0FF
NAVIGATION_COLOR = 0x00A0A0
NAVIGATION_DISABLED = 0x001010
NAVIGATION_HOME = 0xFFFFFF
NAVIGATION_HOME_MOVED = 0x4040FF


def _cycle_gain(phase_beats, period_beats, minimum, maximum):
    cycle_phase = (float(phase_beats) % float(period_beats)) / float(period_beats)
    wave = (1.0 - sin(2.0 * pi * cycle_phase + pi / 2.0)) / 2.0
    return float(minimum) + (float(maximum) - float(minimum)) * wave


def _animation_gains(phase_beats, tempo=None):
    """Return arm/playing/queued gains from one Live-anchored beat phase.

    `tempo` is retained for call compatibility; phase already advances at the
    Live tempo, so each animation uses only a period multiplier.
    """
    return (_cycle_gain(phase_beats, 2.0, 0, EMPTY_LEVEL),
            _cycle_gain(phase_beats, 1.0, 31, 255),
            _cycle_gain(phase_beats, 0.5, 31, 255))


def _track_rgb(track, gain):
    red, green, blue = track.get("color", (0, 0, 0))
    red = max(0, min(127, int(red)))
    green = max(0, min(127, int(green)))
    blue = max(0, min(127, int(blue)))
    if float(gain) >= 255.0:
        red = red * 255 // 127
        green = green * 255 // 127
        blue = blue * 255 // 127
    else:
        red = int(red * float(gain) / 127.0 + 0.5)
        green = int(green * float(gain) / 127.0 + 0.5)
        blue = int(blue * float(gain) / 127.0 + 0.5)
    # Avoid a one-channel, one-count tail near black (most visibly red).
    if max(red, green, blue) <= 1:
        return 0
    return (red << 16) | (green << 8) | blue


def _solid_rgb(color, gain):
    if float(gain) >= 255.0:
        red = (color >> 16) & 0xFF
        green = (color >> 8) & 0xFF
        blue = color & 0xFF
    else:
        red = int(((color >> 16) & 0xFF) * float(gain) / 255.0 + 0.5)
        green = int(((color >> 8) & 0xFF) * float(gain) / 255.0 + 0.5)
        blue = int((color & 0xFF) * float(gain) / 255.0 + 0.5)
    return (red << 16) | (green << 8) | blue


def control_color_for_cell(row, column, rec_length_code, track_offset,
                           scene_offset, track_count, scene_count,
                           feedback=None):
    """Render the 4x4 Rec Length and Navigation regions on the Track page."""
    if not (0 <= int(row) < 4 and 0 <= int(column) < 8):
        return 0
    row, column = int(row), int(column)
    if column < 4:
        bars = bars_for_code(rec_length_code)
        index = row * 4 + column
        if bars == 0 or index >= bars:
            return 0
        return REC_LENGTH_ENDPOINT if index == bars - 1 else REC_LENGTH_FILL

    direction = {
        (6, 0): "up", (5, 1): "left", (6, 1): "home",
        (7, 1): "right", (6, 2): "down",
    }.get((column, row))
    if direction is None:
        return 0
    if direction == "home":
        return NAVIGATION_HOME if (track_offset, scene_offset) == (0, 0) else NAVIGATION_HOME_MOVED
    if feedback == direction:
        return 0xFFFFFF
    max_track = max(0, int(track_count) - 8)
    max_scene = max(0, int(scene_count) - 8)
    available = {
        "left": int(track_offset) > 0,
        "right": int(track_offset) < max_track,
        "up": int(scene_offset) > 0,
        "down": int(scene_offset) < max_scene,
    }[direction]
    return NAVIGATION_COLOR if available else NAVIGATION_DISABLED


def color_for_cell(page, row, track, slot, phase_beats, tempo=None, column=0, scene=None,
                   flash=False, arm_phase_beats=None, queued_phase_beats=None):
    """Return a 24-bit LED color for one cell on the selected Launch page."""
    if page is True:
        page = "track"
    elif page is False:
        page = "session"

    if page == "scene":
        scene = scene or {}
        if not scene.get("valid", False):
            return 0
        _arm_empty_gain, playing_gain, queued_gain = _animation_gains(phase_beats)
        if column == 7:
            return _solid_rgb(0x00FF00, playing_gain) if scene.get("active", False) else 0x001000
        if column == 6:
            return _solid_rgb(0xFF0000, queued_gain) if scene.get("stop_queued", False) else 0x100000
        return 0

    if page == "track":
        if row < 4 or not track.get("valid", False):
            return 0
        enabled = {
            4: track.get("arm", False),
            5: track.get("mute", False),
            6: track.get("solo", False),
        }
        if row == 4:
            return ARM_RED[0] if enabled[row] else ARM_RED[1]
        if row == 5:
            return MUTE_YELLOW[1] if enabled[row] else MUTE_YELLOW[0]
        if row == 6:
            return SOLO_BLUE[0] if enabled[row] else SOLO_BLUE[1]
        if row == 7:
            return STOP_MAGENTA if track.get("active", False) else 0
        return 0

    if not track.get("valid", False):
        return 0
    if scene is not None and not scene.get("valid", False):
        return 0
    arm_empty_gain, playing_gain, queued_gain = _animation_gains(phase_beats)
    if arm_phase_beats is not None:
        arm_empty_gain = _cycle_gain(arm_phase_beats, 2.0, 0, EMPTY_LEVEL)
    if queued_phase_beats is not None:
        queued_gain = _cycle_gain(queued_phase_beats, 0.5, 31, 255)
    status = slot.get("status", EMPTY) if slot.get("valid", False) else EMPTY
    if (flash and page == "session" and status == EMPTY
            and not track.get("arm", False)):
        return 0xFFFFFF
    if status == RECORDING:
        return (RECORD_RED if (float(phase_beats) % 1.0) < 0.5
                else _track_rgb(track, 255))
    base_gain = 255
    if status == EMPTY:
        if track.get("arm", False):
            base_gain = arm_empty_gain
        else:
            base_gain = EMPTY_LEVEL
    elif status == STOPPED:
        base_gain = 255
    elif status == PLAYING:
        base_gain = playing_gain
    elif status in (STOP_QUEUED, RECORD_END_QUEUED, LAUNCH_QUEUED):
        base_gain = queued_gain
        if status == RECORD_END_QUEUED:
            return _solid_rgb(RECORD_RED, base_gain)
    else:
        return 0
    return _track_rgb(track, base_gain)


def has_animated_state(page, tracks, slots, scenes=None):
    if page is True:
        page = "track"
    elif page is False:
        page = "session"
    if page == "track":
        return False
    if page == "scene":
        return any(scene.get("active", False) or scene.get("stop_queued", False)
                   for scene in (scenes or ()))
    for track_index, track in enumerate(tracks):
        if not track.get("valid", False):
            continue
        for scene_index in range(8):
            if scenes is not None and (scene_index >= len(scenes)
                                       or not scenes[scene_index].get("valid", False)):
                continue
            slot = slots[scene_index * 8 + track_index]
            status = slot.get("status", EMPTY) if slot.get("valid", False) else EMPTY
            if track.get("arm", False) and status == EMPTY:
                return True
            if slot.get("valid", False) and status in (
                PLAYING, STOP_QUEUED, RECORD_END_QUEUED, LAUNCH_QUEUED,
            ):
                return True
    return False


def color_role_for_cell(page, row, column, track, slot, scene=None,
                        flash=False, fixed_color=None):
    """Stable visual identity for a cell, independent of its current RGB value."""
    if page is True:
        page = "track"
    elif page is False:
        page = "session"
    row, column = int(row), int(column)
    if fixed_color is not None:
        return ("fixed", int(fixed_color))
    if page == "scene":
        scene = scene or {}
        if not scene.get("valid", False):
            return ("fixed", 0)
        if column == 7:
            return ("scene-active",) if scene.get("active", False) else ("fixed", 0x001000)
        if column == 6:
            return ("scene-stop",) if scene.get("stop_queued", False) else ("fixed", 0x100000)
        return ("fixed", 0)
    if page == "track":
        if row < 4 or not track.get("valid", False):
            return ("fixed", 0)
        if row == 4:
            return ("fixed", ARM_RED[0] if track.get("arm", False) else ARM_RED[1])
        if row == 5:
            return ("fixed", MUTE_YELLOW[1] if track.get("mute", False) else MUTE_YELLOW[0])
        if row == 6:
            return ("fixed", SOLO_BLUE[0] if track.get("solo", False) else SOLO_BLUE[1])
        if row == 7:
            return ("fixed", STOP_MAGENTA if track.get("active", False) else 0)
        return ("fixed", 0)
    if (not track.get("valid", False)
            or (scene is not None and not scene.get("valid", False))):
        return ("fixed", 0)
    status = slot.get("status", EMPTY) if slot.get("valid", False) else EMPTY
    if flash and page == "session" and status == EMPTY and not track.get("arm", False):
        return ("fixed", 0xFFFFFF)
    if status == RECORDING:
        return ("recording", column)
    if status == EMPTY:
        return (("arm-empty", column) if track.get("arm", False)
                else ("empty", column))
    if status == STOPPED:
        return ("stopped", column)
    if status == PLAYING:
        return ("playing", column)
    if status == RECORD_END_QUEUED:
        return ("record-end",)
    if status in (STOP_QUEUED, LAUNCH_QUEUED):
        return ("queued", column)
    return ("fixed", 0)
