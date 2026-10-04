"""Three-page Fn gesture state machine shared by the app and host tests."""


class FnPageGesture:
    def __init__(self, double_click_ms=450):
        self.page = "session"
        self.double_click_ms = int(double_click_ms)
        self._fn_down_at = None
        self._last_release_at = None
        self._second_tap_candidate = False

    @property
    def track_page(self):
        return self.page == "track"

    def fn_press(self, now_ms):
        if self._fn_down_at is not None:
            return
        elapsed = None if self._last_release_at is None else now_ms - self._last_release_at
        self._second_tap_candidate = (
            elapsed is not None and 0 <= elapsed < self.double_click_ms
        )
        self._fn_down_at = now_ms

    def fn_release(self, now_ms):
        if self._fn_down_at is None:
            return False
        held_ms = now_ms - self._fn_down_at
        self._fn_down_at = None
        if held_ms > 3000:
            self._last_release_at = None
            self._second_tap_candidate = False
            return False

        if self._second_tap_candidate:
            self.page = "scene"
            self._last_release_at = None
            self._second_tap_candidate = False
            return True

        self.page = "track" if self.page == "session" else "session"
        self._last_release_at = now_ms
        self._second_tap_candidate = False
        return True

    def pad_press(self):
        self._last_release_at = None
        self._second_tap_candidate = False
