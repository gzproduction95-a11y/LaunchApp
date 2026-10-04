# LaunchApp

**An Ableton Live Session View controller for 203 Systems Mystrix Pro.** LaunchApp keeps its own app entry on Mystrix while Ableton Live handles control logic, display state, and RGB rendering on the computer.

[简体中文](README.zh-CN.md) · [Releases](https://github.com/gzproduction95-a11y/LaunchApp/releases) · [Report a problem](https://github.com/gzproduction95-a11y/LaunchApp/issues)

## Project overview

LaunchApp connects a standalone MatrixOS Python App on Mystrix Pro to an Ableton Live Remote Script over USB MIDI. The controller forwards pad and Fn key events. The computer reads Live's Session state, decides what each control does, renders the 8×8 RGB display, and sends the resulting colours back to Mystrix.

The goal is to retain the familiar V1 playing experience while moving gesture handling, Live decisions, and lighting calculations to the computer.

**Current release:** V2.2.2 · **Device:** 203 Systems Mystrix Pro · **Firmware:** MatrixOS 4.0 or newer · **DAW:** Ableton Live 12.4.6

V2.2.2 has passed the project’s 187 automated tests and a user-run Mystrix Pro / Live acceptance round. The initial armed-slot count-in indication and Fn page response were reported improved, with no obvious issue observed in that round. Hardware results depend on the computer, Live set, USB MIDI path, firmware build, and device.

## Features

- 8×8 Session grid with Track and Scene navigation.
- Clip launch, queued stop, recording, and state feedback synchronized to Live.
- Track page controls for recording length, Arm, Mute, Solo, navigation, and immediate Track Stop.
- Scene launch and current-bar Scene Stop. Scene Stop targets the chosen Scene row, including tracks outside the visible window, and leaves recorded material in Live.
- Fn gestures for page switching: single press for Track/Session navigation; a double press within 450 ms for the Scene page when no pad intervenes.
- Track-colour and state-based RGB feedback for empty, armed, playing, queued, recording, and Scene controls.
- Host-rendered display with protocol v11 acknowledgements and bounded frame updates.

## How it works

    Mystrix LaunchApp  -- raw key events over USB MIDI -->  Ableton Live Remote Script
    Mystrix LEDs       <-- RGB frame updates over USB MIDI -- Live state and host renderer

The device does not choose pages, interpret clips, or calculate animations. Live remains the state authority. The two halves must come from the same release archive; V1 uses protocol v7 and V2.2.2 uses protocol v11. Do not mix versions.

## Download and install

1. Download the paired V2.2.2 ZIP from the [GitHub Releases page](https://github.com/gzproduction95-a11y/LaunchApp/releases).
2. Follow the [installation guide](docs/INSTALLATION.md) before copying either half.
3. Install both the Mystrix App and the Ableton Remote Script from that same ZIP.
4. Select Launch as a Control Surface in Live and choose the Mystrix Pro MIDI ports.
5. Start with an isolated Live Set and follow the first-check steps in the guide.

The device App is installed through the MatrixOS Python App USB serial route. MSC mounting is not the supported installation path. Installation replaces the existing Launch folder; retain a known-good copy if you need rollback.

## Documentation

- [Installation](docs/INSTALLATION.md) · [User guide](docs/USER_GUIDE.md)
- [Architecture](docs/ARCHITECTURE.md) · [Development](docs/DEVELOPMENT.md)
- [Validation and hardware acceptance](docs/VALIDATION.md)
- [Changelog](CHANGELOG.md) · [Contributing](CONTRIBUTING.md) · [Notices](NOTICE.md) · [License](LICENSE)

简体中文用户请从 [中文 README](README.zh-CN.md) 开始。

## Compatibility

| Part | Supported baseline |
| --- | --- |
| Controller | 203 Systems Mystrix Pro |
| Firmware | MatrixOS 4.0 or newer |
| DAW | Ableton Live 12.4.6 |
| V2 protocol | v11, on both device and Remote Script |

Other MatrixOS and Live versions may work, but have not been claimed as tested here. MatrixOS firmware is not included or modified by this project.

## Contributing and support

Bug reports and feature requests are welcome through [GitHub Issues](https://github.com/gzproduction95-a11y/LaunchApp/issues). Include the app version, firmware version, Live version, reproduction steps, and relevant logs with private data removed. See [CONTRIBUTING.md](CONTRIBUTING.md) before submitting a change.

## License and trademarks

The source is distributed under the MIT License; see [LICENSE](LICENSE). Mystrix, MatrixOS, Ableton, and Live are the property of their respective owners. LaunchApp is an independent project and is not affiliated with or endorsed by 203 Systems or Ableton AG.
