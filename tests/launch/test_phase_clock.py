import unittest

from PythonApps.Launch.phase import MusicalPhaseClock


class MusicalPhaseClockTests(unittest.TestCase):
    def test_phase_follows_live_time_and_tempo_from_one_anchor(self):
        clock = MusicalPhaseClock()
        clock.update(phase_u14=0, tempo=120.0, playing=True, now_ms=1000)
        self.assertAlmostEqual(clock.phase_at(1250), 0.5)

        # A tempo update re-anchors all LEDs at the same Live musical phase.
        clock.update(phase_u14=4096, tempo=60.0, playing=True, now_ms=1250)
        self.assertAlmostEqual(clock.phase_at(1750), 1.5)

    def test_transport_stop_freezes_phase_and_start_relocks_to_live_position(self):
        clock = MusicalPhaseClock()
        clock.update(phase_u14=4096, tempo=120.0, playing=True, now_ms=1000)
        clock.update(phase_u14=6144, tempo=120.0, playing=False, now_ms=1250)
        self.assertAlmostEqual(clock.phase_at(5000), 1.5)

        # Position jumps replace the anchor instead of retaining local phase.
        clock.update(phase_u14=1024, tempo=120.0, playing=True, now_ms=5000)
        self.assertAlmostEqual(clock.phase_at(5000), 0.25)
        self.assertAlmostEqual(clock.phase_at(5250), 0.75)

    def test_phase_wraps_without_discontinuity(self):
        clock = MusicalPhaseClock()
        clock.update(phase_u14=16300, tempo=120.0, playing=True, now_ms=0)
        self.assertAlmostEqual(clock.phase_at(50), (16300 / 4096.0 + 0.1) % 4)


if __name__ == "__main__":
    unittest.main()
