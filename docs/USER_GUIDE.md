# User Guide

## Grid coordinates

Each 8×8 page shows eight Tracks by eight Scenes. The top-left pad is the first visible Track and Scene. Columns advance through Tracks from left to right; rows advance through Scenes from top to bottom. The initial window is Tracks 1–8 and Scenes 1–8.

## Fn pages

| Gesture | Result |
| --- | --- |
| Short Fn press on Session | Open Track page |
| Short Fn press on Track or Scene | Return to Session |
| Second Fn press within 450 ms, with no pad press in between | Open Scene page |
| Hold Fn for more than 3 seconds | MatrixOS exits the app |

## Session page

| Slot state | Press result |
| --- | --- |
| Empty slot on an armed Track | Start Session recording using Live's count-in/quantization |
| Empty slot on an unarmed Track while another clip plays on that Track | Queue the active clip to stop at the end of the current bar |
| Stopped clip | Launch using Live Clip Launch Quantization |
| Recording clip | Queue the end of recording |
| Playing looped clip | Queue stop at the loop end |
| Playing non-looped clip | Stop at the natural end of the clip |

An empty slot on an unarmed Track flashes white briefly as feedback. It does not arm the Track or start recording.

## Track page

Rows 1–4 are the control area.

| Pads | Action |
| --- | --- |
| Rows 1–4, columns 1–4 | Set recording length: Unlimited, 1, 2, 4, 6, 8, 12, or 16 bars |
| Rows 1–4, columns 5–8 | Up, Left, Home, Right, and Down navigation |
| Row 5 | Toggle Arm |
| Row 6 | Toggle Mute |
| Row 7 | Toggle Solo |
| Row 8 | Stop the Track immediately |

Short navigation moves the visible window by eight cells. Holding a direction performs one eight-cell jump. Home returns to Track 1 / Scene 1.

## Scene page

The rightmost column launches the whole Live Scene. The column immediately to its left queues a stop for active clips in that Scene row at the end of the current bar. Other Scene rows continue playing.

Scene Stop also targets Tracks outside the visible 8×8 window. A recording clip ends at the boundary and remains in Live; LaunchApp does not delete it.

## LED states

| Live state | Device feedback |
| --- | --- |
| Empty, unarmed | Dim Track colour |
| Empty, armed | Smooth breathing between off and dim Track colour, every two beats |
| Stopped clip | Bright Track colour |
| Playing clip | Track-colour breathing, one cycle per beat |
| Queued launch/stop/end | Faster breathing, two cycles per beat |
| Recording | Red on the beat, Track colour off the beat |
| Scene Launch / Scene Stop | Green / red using the shared musical phase |

Playback animation follows Live's musical phase. While Live is stopped, armed-empty breathing continues from the last valid tempo on the host clock and relocks to Live on playback. The renderer targets up to 25 frames per second; exact sub-frame synchronization across LEDs is not guaranteed.

## Tips

- Keep the Mystrix App and Live Remote Script on the same release.
- The Session grid controls Live clips; it does not edit or delete clip content.
- Use a backed-up or disposable Live Set for first-time acceptance.
