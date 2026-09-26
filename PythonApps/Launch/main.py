"""Launch standalone MatrixOS 4.0 Python App."""

import MatrixOS
from controller import LaunchController
from rendering import color_for_cell, control_color_for_cell, has_animated_state
from protocol import (HELLO, REQUEST_FULL_SYNC, GRID_PRESS, TRACK_ACTION,
                     HELLO_ACK, SYNC_BEGIN, TRACK_COLOR, TRACK_STATE,
                     SLOT_STATE, SYNC_END, SYNC_DATA, HEARTBEAT, SCENE_ACTION,
                     SCENE_STATE, NAVIGATION, REC_LENGTH, SYNC_ACK, WINDOW_META,
                     REC_LENGTH_STATE, encode, decode)
from state import SessionState
from navigation import record_length_code, split_u14, join_u14

Input = MatrixOS.Input
LED = MatrixOS.LED
MIDI = MatrixOS.MIDI
SYS = MatrixOS.SYS
Logging = MatrixOS.Logging
USB_PORT = MIDI.PORT_USB

controller = LaunchController(Input.function_key())
state = SessionState()
sequence = 0
connected = False
last_hello = -10000
hello_attempts = 0
last_response = -10000
last_keepalive = -10000
sync_id = None
sync_started_at = None
sync_failed = False
last_sync_request = -10000
sysex_buffer = []
last_animation_render = -1000
nav_feedback = None
nav_feedback_until = -1
press_flash_cell = None
press_flash_until = -1
ANIMATION_FRAME_MS = 40
rendered_colors = [[None for _ in range(8)] for _ in range(8)]

def diagnostic(message):
    Logging.info("Launch", message)

def send(message, payload=()):
    global sequence
    sequence = (sequence + 1) & 0x7F
    sent = MIDI.send_sysex(USB_PORT, bytes(encode(message, sequence, payload)), True)
    if not sent:
        diagnostic("MIDI send failed: type={} sequence={}".format(message, sequence))
    return sent

def send_hello():
    global hello_attempts
    hello_attempts += 1
    if hello_attempts == 1 or hello_attempts % 10 == 0:
        diagnostic("HELLO send attempt {} on USB MIDI port 1".format(hello_attempts))
    return send(HELLO)

def request_full_sync():
    global last_sync_request
    now = SYS.millis()
    if now - last_sync_request < 750:
        return False
    last_sync_request = now
    return send(REQUEST_FULL_SYNC)

def render():
    now = SYS.millis()
    phase_beats = state.phase_clock.phase_at(now)
    changed = False
    for y in range(8):
        for x in range(8):
            track = state.tracks[x]
            slot = state.slots[y * 8 + x]
            scene = state.scenes[y]
            color = color_for_cell(controller.gesture.page, y, track, slot,
                                   phase_beats, state.tempo, column=x, scene=scene,
                                   flash=(press_flash_cell == (x, y)
                                          and now < press_flash_until))
            if controller.gesture.page == "track" and y < 4:
                feedback = nav_feedback if now < nav_feedback_until else None
                color = control_color_for_cell(
                    y, x, state.rec_length_code, state.track_offset,
                    state.scene_offset, state.track_count, state.scene_count,
                    feedback=feedback)
            if rendered_colors[y][x] != color:
                rendered_colors[y][x] = color
                LED.set_xy(x, y, color)
                changed = True
    if changed:
        LED.update()

def handle_midi(packet):
    global connected, sync_id, sync_started_at, sync_failed
    global sysex_buffer, last_response, last_keepalive
    if packet is None or not packet.is_sysex():
        return
    # MatrixOS 4.0 exposes the first payload byte as packet.status() for SysEx.
    # Its Python packet.length() consequently returns 0 for ordinary fragments.
    raw = tuple(packet.data())
    if packet.is_sysex_start():
        sysex_buffer = []
    try:
        end = raw.index(0xF7)
    except ValueError:
        sysex_buffer.extend(raw)
        if len(sysex_buffer) > 256:
            sysex_buffer = []
        return
    sysex_buffer.extend(raw[:end + 1])
    if len(sysex_buffer) > 256:
        sysex_buffer = []
        return
    raw = tuple(sysex_buffer)
    sysex_buffer = []
    decoded = decode(raw)
    if decoded is None:
        return
    message, seq, payload = decoded
    last_response = SYS.millis()
    if message == HELLO_ACK:
        if not connected:
            connected = True
            last_keepalive = last_response
            diagnostic("HELLO_ACK received; requesting full sync")
            request_full_sync()
    elif message == HEARTBEAT:
        connected = True
        if len(payload) == 5:
            tempo = (payload[0] << 7) | payload[1]
            phase_u14 = join_u14(payload[2], payload[3])
            playing = payload[4]
            if 200 <= tempo <= 9999 and playing in (0, 1):
                state.tempo = tempo / 10.0
                state.phase_clock.update(phase_u14, state.tempo,
                                         playing == 1, SYS.millis())
    elif message == SYNC_BEGIN and len(payload) == 12:
        sync_id = join_u14(payload[0], payload[1])
        (count, track_hi, track_lo, scene_hi, scene_lo, tracks_hi, tracks_lo,
         scenes_hi, scenes_lo, rec_code) = payload[2:]
        track_offset = join_u14(track_hi, track_lo)
        scene_offset = join_u14(scene_hi, scene_lo)
        track_count = join_u14(tracks_hi, tracks_lo)
        scene_count = join_u14(scenes_hi, scenes_lo)
        if not state.begin_sync(sync_id, count, track_offset, scene_offset,
                                track_count, scene_count, rec_code):
            diagnostic("invalid SYNC_BEGIN metadata id={} count={}".format(sync_id, count))
            state.abort_sync()
            state.synced = False
            send(SYNC_ACK, split_u14(sync_id) + (0, seq))
            sync_id = None
            sync_started_at = None
        else:
            sync_started_at = SYS.millis()
            sync_failed = False
            diagnostic("SYNC_BEGIN id={} records={} window=({}, {}) rec={}".format(
                sync_id, count, track_offset, scene_offset, rec_code))
            send(SYNC_ACK, split_u14(sync_id) + (2, seq))
    elif message == SYNC_DATA and sync_id is not None and len(payload) >= 2:
        if join_u14(payload[0], payload[1]) != sync_id:
            return
        index = 2
        while index < len(payload):
            if index + 2 > len(payload):
                break
            tag, record_id = payload[index], payload[index + 1]
            index += 2
            if tag == 0 and index + 3 <= len(payload):
                staged = state.stage_track_color(record_id, payload[index:index + 3])
                index += 3
            elif tag == 1 and index < len(payload):
                staged = state.stage_track_flags(record_id, payload[index])
                index += 1
            elif tag == 2 and index < len(payload):
                staged = state.stage_slot(record_id, payload[index])
                index += 1
            elif tag == 3 and index < len(payload):
                staged = state.stage_scene(record_id, payload[index])
                index += 1
            else:
                sync_failed = True
                break
            if not staged:
                sync_failed = True
        send(SYNC_ACK, split_u14(sync_id) + (0 if sync_failed else 2, seq))
    elif message in (TRACK_COLOR, TRACK_STATE, SLOT_STATE, SCENE_STATE):
        applied = state.apply_incremental(message, payload)
        diagnostic("incremental type={} applied={}".format(message, applied))
        if applied:
            render()
    elif message == WINDOW_META and len(payload) == 10:
        generation = join_u14(payload[0], payload[1])
        values = [join_u14(payload[index], payload[index + 1])
                  for index in (2, 4, 6, 8)]
        if state.synced and state._sync is None and state.update_window_meta(
                generation, values[0], values[1], values[2], values[3]):
            diagnostic("WINDOW_META applied tracks={} scenes={}".format(
                values[2], values[3]))
            render()
    elif message == REC_LENGTH_STATE and len(payload) == 3:
        generation = join_u14(payload[0], payload[1])
        code = payload[2]
        if (state.synced and state._sync is None and generation == state.sync_id
                and 0 <= code <= 7):
            state.rec_length_code = code
            diagnostic("REC_LENGTH_STATE applied code={}".format(code))
            render()
    elif message == SYNC_END and len(payload) == 2:
        ending_id = join_u14(payload[0], payload[1])
        if sync_id is None or ending_id != sync_id:
            send(SYNC_ACK, split_u14(ending_id) + (0, seq))
            diagnostic("ignored stale SYNC_END id={}".format(ending_id))
            return
        completed = False if sync_failed else state.end_sync(ending_id)
        if sync_failed:
            state.abort_sync(ending_id)
        if not completed:
            state.synced = False
        sync_id = None
        sync_started_at = None
        send(SYNC_ACK, split_u14(ending_id) + (1 if completed else 0,))
        diagnostic("SYNC_END id={} complete={}".format(ending_id, completed))
        if completed:
            render()

def startup():
    global last_hello
    Input.clear()
    last_hello = SYS.millis()
    diagnostic("started")
    send_hello()
    render()

def loop():
    global last_hello, last_keepalive, connected, state, last_animation_render
    global sync_id, sync_started_at, sync_failed
    global nav_feedback, nav_feedback_until, press_flash_cell, press_flash_until
    now = SYS.millis()
    event = Input.get_event(0)
    if event is not None:
        actions = controller.handle_event(event, now)
        for action in actions:
            if action[0] == "page":
                render()
            elif action[0] == "grid":
                if state.synced and state._sync is None:
                    local_track = action[1] % 8
                    slot = state.slots[action[1]]
                    track = state.tracks[local_track]
                    if (track.get("valid", False) and not track.get("arm", False)
                            and track.get("active", False)
                            and slot.get("valid", False)
                            and slot.get("status") == 0):
                        press_flash_cell = (local_track, action[1] // 8)
                        press_flash_until = now + 120
                        render()
                    send(GRID_PRESS, (action[1],) + split_u14(state.track_offset)
                         + split_u14(state.scene_offset) + split_u14(state.sync_id))
            elif action[0] == "track":
                code = {"arm": 1, "mute": 2, "solo": 3, "stop": 4}[action[2]]
                if state.synced and state._sync is None:
                    send(TRACK_ACTION, (action[1], code) + split_u14(state.track_offset)
                         + split_u14(state.scene_offset) + split_u14(state.sync_id))
            elif action[0] == "scene_launch":
                if state.synced and state._sync is None:
                    send(SCENE_ACTION, (action[1], 1) + split_u14(state.track_offset)
                         + split_u14(state.scene_offset) + split_u14(state.sync_id))
            elif action[0] == "scene_stop":
                if state.synced and state._sync is None:
                    send(SCENE_ACTION, (action[1], 2) + split_u14(state.track_offset)
                         + split_u14(state.scene_offset) + split_u14(state.sync_id))
            elif action[0] == "navigate":
                if state.synced and state._sync is None:
                    nav_codes = {"left": 1, "right": 2, "up": 3, "down": 4, "home": 5}
                    send(NAVIGATION, (nav_codes[action[1]], action[2])
                         + split_u14(state.track_offset) + split_u14(state.scene_offset)
                         + split_u14(state.sync_id))
                    if action[2] == 8:
                        nav_feedback = action[1]
                        nav_feedback_until = now + 180
                        render()
            elif action[0] == "nav_preview":
                nav_feedback = action[1]
                nav_feedback_until = now + 180
                render()
            elif action[0] == "record_length":
                if state.synced and state._sync is None:
                    selected = record_length_code(action[1])
                    observed = state.rec_length_code
                    state.rec_length_code = (0 if selected == observed else selected)
                    render()
                    send(REC_LENGTH, (selected, observed)
                         + split_u14(state.sync_id))
    for _ in range(8):
        packet = MIDI.get(0)
        if packet is None:
            break
        handle_midi(packet)
    if connected and now - last_response > 3000:
        connected = False
        state = SessionState()
        sync_id = None
        sync_started_at = None
        sync_failed = False
        diagnostic("Live response timeout; mirror cleared")
        render()
    if sync_id is not None and sync_started_at is not None and now - sync_started_at > 2000:
        expired_id = sync_id
        state.abort_sync(expired_id)
        state.synced = False
        sync_id = None
        sync_started_at = None
        sync_failed = False
        diagnostic("SYNC timeout id={}; requesting a fresh snapshot".format(expired_id))
        request_full_sync()
    if connected and now - last_keepalive >= 1000:
        send(HEARTBEAT)
        last_keepalive = now
    if now - last_hello >= 1000 and not connected:
        send_hello()
        last_hello = now
    if now - last_animation_render >= ANIMATION_FRAME_MS:
        last_animation_render = now
        if has_animated_state(controller.gesture.page, state.tracks, state.slots,
                              state.scenes) or press_flash_cell is not None:
            render()
    if press_flash_cell is not None and now >= press_flash_until:
        press_flash_cell = None
        press_flash_until = -1
        render()
    if nav_feedback is not None and now >= nav_feedback_until:
        nav_feedback = None
        render()
