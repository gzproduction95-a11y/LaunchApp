# Installation Guide

## Requirements

- 203 Systems Mystrix Pro running MatrixOS 4.0 or newer.
- Ableton Live 12.4.6.
- USB MIDI connection between Mystrix and the computer.
- LaunchApp V2.2.2 package downloaded from GitHub Releases.

Install the Mystrix App and Live Remote Script from the same ZIP. V1 uses protocol v7; V2.2.2 uses protocol v11. Mixed pairs will not connect.

## 1. Prepare

1. Quit Ableton Live.
2. Download and extract the V2.2.2 ZIP.
3. Keep the V1 App and Remote Script available if you may need to roll back.
4. Find the Ableton User Library configured in Live. Its Remote Scripts directory is User Library/Remote Scripts.

The package has two install roots:
- Mystrix-SD/MatrixOS/Applications/Launch/
- Ableton-User-Library/Remote Scripts/Launch/

## 2. Install the Mystrix App

The known working route uses the built-in MatrixOS Python App and its USB serial file-write interface. MSC mounting is not the supported route for this device setup.

1. Connect Mystrix over USB and open the built-in Python App.
2. Use the validated serial file-write interface to place the files from the package's Mystrix-SD folder under rootfs:/MatrixOS/Applications/Launch/.
3. The files in that folder are AppInfo.json, main.py, main_v2.py, protocol_v2.py, input_events.py, and display_receiver.py.
4. Read the files back from the device and compare them with the package. Confirm all six names and contents before launching.
5. Exit Python and open Launch from the MatrixOS app menu.

Installing replaces files in the existing Launch application folder. Keep the V1 files separately if you need rollback. Stop if the serial interface is unavailable or read-back does not match.

## 3. Install the Live Remote Script

1. Copy the package's Launch folder from Ableton-User-Library/Remote Scripts/ into the configured User Library's Remote Scripts directory.
2. If a Launch folder already exists, replace it with the folder from this same package; do not merge files from different releases.
3. Start Live.
4. Open Settings/Preferences → Link, Tempo & MIDI.
5. In a Control Surface row, select Launch. Set both Input and Output to Mystrix Pro (port 1).

## 4. First connection check

1. Open a disposable or backed-up Live Set.
2. Open Launch on Mystrix.
3. Check that the Live log reports the Launch v11 connection and the initial display frame is acknowledged.
4. Confirm the 8×8 pad positions visually before testing controls.
5. Press one known empty or stopped clip slot and verify that only its matching Live slot responds.
6. Test Fn page switching and check that the device remains stable.

Stop if the app exits or restarts, the device disconnects, the wrong clip responds, or Live reports repeated NACKs or timeouts.

## Rollback

Quit Live. Restore both the V1 Mystrix Launch folder and V1 Live Remote Scripts/Launch folder from the same V1 release. Restart Live and select the V1 Launch control surface. Never pair one V1 half with one V2 half.

## Uninstall

Quit Live, remove the Launch control surface selection, and remove the Launch folders from the Live User Library and Mystrix Applications directory using the validated device file-management route. Do not delete unrelated MatrixOS applications.
