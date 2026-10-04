"""One Live-anchored musical phase shared by every animated LED."""


class MusicalPhaseClock:
    """Extrapolate Live's modulo-four-beat phase between clock messages."""

    PHASE_U14_PER_BEAT = 4096.0
    PHASE_BEATS = 4.0
    MILLIS_WRAP = 1 << 32

    def __init__(self):
        self._phase_beats = 0.0
        self._tempo = 120.0
        self._playing = False
        self._anchor_ms = 0
        self._valid = False

    def update(self, phase_u14, tempo, playing, now_ms):
        phase_u14 = int(phase_u14)
        tempo = float(tempo)
        if not 0 <= phase_u14 <= 0x3FFF or not 20.0 <= tempo <= 999.9:
            return False
        if self._valid and not self._playing and not playing:
            phase_beats = self.phase_at(now_ms, continue_when_stopped=True)
        else:
            phase_beats = phase_u14 / self.PHASE_U14_PER_BEAT
        self._phase_beats = phase_beats
        self._tempo = tempo
        self._playing = bool(playing)
        self._anchor_ms = int(now_ms) & 0xFFFFFFFF
        self._valid = True
        return True

    def phase_at(self, now_ms, continue_when_stopped=False):
        if not self._valid:
            return 0.0
        phase = self._phase_beats
        if self._playing or continue_when_stopped:
            elapsed_ms = ((int(now_ms) & 0xFFFFFFFF) - self._anchor_ms) % self.MILLIS_WRAP
            if elapsed_ms < self.MILLIS_WRAP // 2:
                phase += elapsed_ms * self._tempo / 60000.0
        return phase % self.PHASE_BEATS
