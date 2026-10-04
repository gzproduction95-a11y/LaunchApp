# Validation

## Evidence levels

- **Automated:** CPython tests with fake MatrixOS and Live APIs.
- **Live:** Remote Script loaded in Ableton Live and actions checked in a disposable or backed-up Set.
- **Hardware:** User observes Mystrix LEDs, USB MIDI, timing, and stability.

A result at one level does not prove the next level.

## V2.2.2 release evidence

- Automated suite: 187 tests passed in the release worktree.
- Package: V2.2.2 paired device/host archive, 40 ms initial packet gap.
- Physical acceptance: user installed the matched package on Mystrix Pro with Ableton Live 12.4.6. The controller remained usable; count-in LED indication and Fn page response were reported improved, with no obvious issue observed in the latest round.
- Limits: human visual feedback is qualitative, not instrumented latency or colorimetric measurement. This report does not claim validation on other firmware, Live, or hardware versions.

## Repeat the essential checks

1. Verify both installed halves came from one V2.2.2 archive and Live reports protocol v11 connected.
2. Check pad-to-track/scene position on an isolated Set before launching clips.
3. With transport stopped, arm a track and trigger its first empty slot. Observe count-in indication, then the transition to recording.
4. Try single and double Fn gestures repeatedly and check the displayed page.
5. Test clip launch/stop, recording retention, Track controls, Scene launch, and current-bar Scene Stop.
6. Observe LEDs under multi-track Arm/recording load and confirm the animation remains stable and follows tempo.
7. Leave the app connected during a longer session; check for app exit/restart, disconnects, or persistent frame errors.

## Stop conditions

Stop testing if Mystrix restarts or exits Launch, MIDI disconnects, a wrong clip responds, recording content disappears, an unintended clip stops, page mapping is visibly wrong, or Live reports persistent NACKs/timeouts. Record timestamps and preserve relevant logs with personal information removed.
