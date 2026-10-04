"""Thin MatrixOS Launch V2.2.1 client: forward controls and display host RGB frames."""

import MatrixOS

try:
    from .protocol_v2 import (FRAME_ACK, FRAME_TABLE_BEGIN,
                              FRAME_TABLE_COLOR_CHUNK, FRAME_TABLE_MAP_CHUNK,
                              FRAME_TABLE_COMMIT, FRAME_SLOT_DELTA, HEARTBEAT,
                              INPUT_EVENT, LINK_ACK, LINK_HELLO, PROTOCOL_VERSION,
                              decode_frame, encode_frame, join_u14, join_u28,
                              split_u14, split_u28)
    from .input_events import encode_input_event
    from .display_receiver import FrameReceiver
except ImportError:  # MatrixOS stages app files as top-level siblings.
    from protocol_v2 import (FRAME_ACK, FRAME_TABLE_BEGIN,
                             FRAME_TABLE_COLOR_CHUNK, FRAME_TABLE_MAP_CHUNK,
                             FRAME_TABLE_COMMIT, FRAME_SLOT_DELTA, HEARTBEAT,
                             INPUT_EVENT, LINK_ACK, LINK_HELLO, PROTOCOL_VERSION,
                             decode_frame, encode_frame, join_u14, join_u28,
                             split_u14, split_u28)
    from input_events import encode_input_event
    from display_receiver import FrameReceiver

Input = MatrixOS.Input
LED = MatrixOS.LED
MIDI = MatrixOS.MIDI
SYS = MatrixOS.SYS
Logging = MatrixOS.Logging
USB_PORT = MIDI.PORT_USB
FN_INPUT_ID = Input.function_key()
MAX_SYSEX_BYTES = 256

_sequence = 0
event_sequence = 0
slot_delta_count = 0
connected = False
boot_id = 0
session_id = None
last_hello = -10000
last_response = -10000
last_heartbeat = -10000
hello_attempts = 0
sysex_buffer = []
frame_receiver = FrameReceiver()


def diagnostic(message):
    Logging.info("Launch", message)


def send(message_type, payload=()):
    global _sequence
    _sequence = (_sequence + 1) & 0x7F
    data = bytes(encode_frame(message_type, _sequence, payload))
    sent = MIDI.send_sysex(USB_PORT, data, True)
    if not sent:
        diagnostic("MIDI send failed type={} sequence={}".format(message_type, _sequence))
    return sent


def send_hello():
    global hello_attempts
    hello_attempts += 1
    if hello_attempts == 1 or hello_attempts % 10 == 0:
        diagnostic("V2.2.1 HELLO attempt {} on USB MIDI port 1".format(hello_attempts))
    return send(LINK_HELLO, split_u28(boot_id))


def _clear_leds(force=False):
    previous = frame_receiver.colors
    if force or any(previous):
        for index in range(64):
            if force or previous[index]:
                LED.set_xy(index % 8, index // 8, 0)
        LED.update()
    frame_receiver.colors = (0,) * 64
    frame_receiver.last_frame_id = None


def _apply_frame(old, colors):
    changed = False
    for index, color in enumerate(colors):
        if old[index] != color:
            LED.set_xy(index % 8, index // 8, color)
            changed = True
    if changed:
        LED.update()


def _display_digest(colors):
    """FNV-1a over canonical 24-bit RGB values; matches the Live-side trace."""
    value = 0x811C9DC5
    for color in colors:
        for shift in (16, 8, 0):
            value = ((value ^ ((int(color) >> shift) & 0xFF))
                     * 0x01000193) & 0xFFFFFFFF
    return value


def handle_midi(packet):
    global connected, session_id, last_response, sysex_buffer, slot_delta_count
    if packet is None or not packet.is_sysex():
        return
    raw = tuple(packet.data())
    if packet.is_sysex_start():
        sysex_buffer = []
    try:
        end = raw.index(0xF7)
    except ValueError:
        sysex_buffer.extend(raw)
        if len(sysex_buffer) > MAX_SYSEX_BYTES:
            sysex_buffer = []
        return
    sysex_buffer.extend(raw[:end + 1])
    if len(sysex_buffer) > MAX_SYSEX_BYTES:
        sysex_buffer = []
        return
    decoded = decode_frame(tuple(sysex_buffer))
    sysex_buffer = []
    if decoded is None:
        return
    message, _sequence, payload = decoded
    now = SYS.millis()
    last_response = now
    if message == LINK_ACK and len(payload) == 8:
        acknowledged_boot = join_u28(payload[:4])
        new_session = join_u28(payload[4:])
        if acknowledged_boot != boot_id or new_session == 0:
            return
        if not connected or session_id != new_session:
            connected = True
            session_id = new_session
            _clear_leds()
            frame_receiver.set_session(session_id)
            diagnostic("V2.2.1 LINK_ACK accepted; session={}".format(session_id))
    elif message == HEARTBEAT and len(payload) == 4:
        if connected and join_u28(payload) == session_id:
            last_heartbeat = now
    elif message in (FRAME_TABLE_BEGIN, FRAME_TABLE_COLOR_CHUNK,
                     FRAME_TABLE_MAP_CHUNK, FRAME_TABLE_COMMIT,
                     FRAME_SLOT_DELTA) and connected:
        previous = frame_receiver.colors
        table_pending = frame_receiver._table_pending
        committing_table_full = (message == FRAME_TABLE_COMMIT
                                 and table_pending is not None
                                 and table_pending.get("full", False))
        committing_frame_id = (table_pending.get("id")
                               if committing_table_full else None)
        try:
            ack = frame_receiver.receive(decoded)
        except Exception as error:
            ack = None
            if len(payload) >= 6:
                try:
                    ack = (FRAME_ACK, join_u14(payload[4], payload[5]), 0)
                except (TypeError, ValueError):
                    ack = None
            diagnostic("display decode error type={}".format(type(error).__name__))
        if ack is not None:
            frame_id, status = ack[1], ack[2]
            if status == 1:
                _apply_frame(previous, frame_receiver.colors)
                if committing_table_full:
                    diagnostic("V2.2.1 full-table applied id={} digest={:08x}".format(
                        committing_frame_id, _display_digest(frame_receiver.colors)))
                elif message == FRAME_TABLE_COMMIT:
                    diagnostic("V2.2.1 table mapping applied id={} digest={:08x}".format(
                        frame_id, _display_digest(frame_receiver.colors)))
                elif message == FRAME_SLOT_DELTA:
                    slot_delta_count += 1
                    if slot_delta_count % 64 == 0:
                        diagnostic("V2.2.1 color-slot frames applied count={} last_id={} digest={:08x}".format(
                            slot_delta_count, frame_id,
                            _display_digest(frame_receiver.colors)))
            send(FRAME_ACK, split_u28(session_id) + split_u14(frame_id) + (status,))


def _send_input(event, now):
    global event_sequence
    if not connected or session_id is None:
        return False
    keypad = event.get("keypad") or {}
    event_id = event.get("id")
    is_function = event_id == FN_INPUT_ID
    point = event.get("point")
    if is_function:
        x = y = None
    elif point is not None and len(point) == 2:
        x, y = point
        if not (isinstance(x, int) and isinstance(y, int)
                and 0 <= x < 8 and 0 <= y < 8):
            return False
    else:
        return False
    event_sequence = (event_sequence + 1) & 0x3FFF
    payload = encode_input_event(
        session_id, event_sequence, now, is_function,
        bool(keypad.get("pressed")), bool(keypad.get("released")),
        bool(keypad.get("hold")), x, y)
    return send(INPUT_EVENT, payload)


def startup():
    global boot_id, last_hello, last_response, last_heartbeat, event_sequence, slot_delta_count
    Input.clear()
    _clear_leds(force=True)
    boot_id = ((int(SYS.millis()) << 14) ^ id(frame_receiver)) & 0x0FFFFFFF
    last_hello = int(SYS.millis())
    last_response = last_hello
    last_heartbeat = last_hello
    event_sequence = 0
    slot_delta_count = 0
    diagnostic("Launch V2.2.1 thin controller started; protocol={}".format(PROTOCOL_VERSION))
    send_hello()


def loop():
    global connected, session_id, last_hello, last_heartbeat
    now = int(SYS.millis())
    event = Input.get_event(0)
    if event is not None:
        _send_input(event, now)
    for _ in range(8):
        packet = MIDI.get(0)
        if packet is None:
            break
        handle_midi(packet)
    if connected and now - last_response > 3000:
        connected = False
        session_id = None
        _clear_leds()
        diagnostic("computer connection timed out; display cleared")
    if not connected and now - last_hello >= 1000:
        send_hello()
        last_hello = now
    if connected and now - last_heartbeat >= 1000:
        send(HEARTBEAT, split_u28(session_id))
        last_heartbeat = now


if __name__ == "__main__":
    startup()
    while True:
        loop()
