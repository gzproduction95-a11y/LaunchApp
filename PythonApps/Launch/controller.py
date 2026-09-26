"""Map MatrixOS input events to Launch page and Live requests."""

try:
    from .gestures import FnPageGesture
except ImportError:  # MatrixOS stages app files as top-level siblings.
    from gestures import FnPageGesture


class LaunchController:
    def __init__(self, fn_input_id):
        self.fn_input_id = fn_input_id
        self.gesture = FnPageGesture()
        self._nav_pending = {}

    @staticmethod
    def _navigation_at(x, y):
        return {
            (6, 0): "up",
            (5, 1): "left",
            (6, 1): "home",
            (7, 1): "right",
            (6, 2): "down",
        }.get((x, y))

    @staticmethod
    def _record_length_at(x, y):
        index = y * 4 + x
        return {0: 1, 1: 2, 3: 4, 5: 6, 7: 8, 11: 12, 15: 16}.get(index)

    def handle_event(self, event, now_ms):
        keypad = event.get("keypad") or {}
        input_id = event.get("id")

        if input_id == self.fn_input_id:
            if keypad.get("pressed"):
                self.gesture.fn_press(now_ms)
                return []
            if keypad.get("released") and self.gesture.fn_release(now_ms):
                return [("page", self.gesture.page)]
            return []

        point = event.get("point")
        x = y = None
        if point is not None and len(point) == 2:
            x, y = point

        pressed = bool(keypad.get("pressed"))
        released = bool(keypad.get("released"))
        held = bool(keypad.get("hold"))
        if pressed:
            self.gesture.pad_press()
        if x is None or not (0 <= x < 8 and 0 <= y < 8):
            return []

        if self.gesture.page == "track" and y < 4:
            if x < 4:
                bars = self._record_length_at(x, y)
                if pressed and bars is not None:
                    return [("record_length", bars)]
                return []

            direction = self._navigation_at(x, y)
            if direction is None:
                return []
            key = (x, y)
            pending = self._nav_pending.get(key)
            if pressed:
                if direction == "home":
                    return [("navigate", "home", 0)]
                self._nav_pending[key] = {"direction": direction, "held": False}
                return [("nav_preview", direction)]
            if held and pending is not None and not pending["held"]:
                pending["held"] = True
                return [("navigate", direction, 8)]
            if released and pending is not None:
                self._nav_pending.pop(key, None)
                if not pending["held"]:
                    return [("navigate", pending["direction"], 1)]
            return []

        if not pressed:
            return []

        if self.gesture.page == "session":
            return [("grid", y * 8 + x)]

        if self.gesture.page == "track":
            if y < 4:
                return []
            action = ("arm", "mute", "solo", "stop")[y - 4]
            return [("track", x, action)]

        if self.gesture.page == "scene":
            if x == 7:
                return [("scene_launch", y)]
            if x == 6:
                return [("scene_stop", y)]
            return []

        return []
