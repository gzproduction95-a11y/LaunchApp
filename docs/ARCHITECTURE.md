# Architecture

## Responsibility split

LaunchApp remains a standalone MatrixOS application on Mystrix. The device forwards raw key transitions and displays RGB colours received from the computer. Ableton Live and its Remote Script own page gestures, Live actions, state classification, RGB rendering, and animation phase.

    Mystrix App  -- raw input events --> Live Remote Script and Live API
    Mystrix LEDs <-- acknowledged RGB frames -- host renderer

## Components

- Device bootstrap: starts the application and isolates imports for constrained MicroPython memory.
- Device protocol and input modules: encode key events, session identity, acknowledgements, and bounded SysEx messages.
- Device display receiver: stages and validates host-authored colour/mapping updates before applying them.
- Live Remote Script: reads Live state, reuses the V1 action implementation, handles gestures/navigation, renders the grid, and sends changed data.
- Host frame sender: keeps updates bounded, tracks acknowledgements, and resynchronizes after errors.

## Protocol v11

V2 uses SysEx protocol v11 on both ends. A host-issued session identifier prevents stale input or frame messages from a prior connection from being applied. Device-originated input includes sequence and timestamp data. LED frames are acknowledged. Up to 16 changing colour slots can be carried in one bounded delta; larger changes use staged chunks and an atomic commit. Invalid or incomplete updates leave the last valid display in place.

RGB values are calculated on the computer. Mystrix stores a bounded RGB colour table and cell mapping and does not interpret Live concepts, tempo, or animation state.

## Live and timing

Live remains the authority for Tracks, Clips, Scenes, tempo, transport, and launch/stop queues. Existing V1 action and safety rules remain in the Live script. The V2 host asks Live's bundled timer for a 10 ms service callback and targets a 40 ms display cadence and initial SysEx gap. These values are targets; real scheduling and LED timing depend on Live, the computer, USB MIDI, and device firmware.

## Compatibility boundary

V1 protocol v7 and V2 protocol v11 are separate pairs. No MatrixOS firmware source is included or modified. The project has no Developer App workflow; users launch the standalone Launch application.
