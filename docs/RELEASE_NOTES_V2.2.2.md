# LaunchApp V2.2.2

V2.2.2 is the first public release of the host-rendered V2 architecture for Mystrix Pro and Ableton Live 12.4.6.

## Highlights

- Keep LaunchApp as a standalone MatrixOS app on Mystrix.
- Move Fn/page gestures, Live actions, state interpretation, and RGB animation rendering to the Live Remote Script on the computer.
- Use SysEx protocol v11 for raw inputs, sessions, bounded color-table updates, and acknowledged display frames.
- Improve the first armed-empty-slot count-in feedback while Live transport is stopped.
- Send incremental page changes against the acknowledged device color table.
- Preserve V1 musical actions and the user-facing control layout.

## Verification

The release worktree passes 187 automated tests. The user installed and tested the matched device/Live package on Mystrix Pro and Live 12.4.6. The latest reported round showed improved count-in indication and Fn page response with no obvious issue observed.

These observations describe that test setup only. They do not guarantee identical timing on every computer, firmware build, Live Set, or USB MIDI setup.

## Installation

Download LaunchApp-V2.2.2-responsive-40ms.zip and follow docs/INSTALLATION.md. Install both halves from this archive. Do not mix protocol-v7 V1 files with protocol-v11 V2.2.2 files.
