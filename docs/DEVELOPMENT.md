# Development

## Requirements

- Python 3.9 or newer for local tests and packaging.
- Ableton Live and MatrixOS are not required to run the unit tests; tests provide doubles for those APIs.
- Physical validation requires Mystrix Pro and the supported Live setup described in README.md.

## Tests

From the repository root:

    PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/launch -q
    git diff --check

The suite covers protocol codecs, v11 host/device parity, frame staging and acknowledgement, recovery paths, rendering and musical phase, fake-Live actions, and packaging-related runtime behavior.

## Build the paired package

    python3 Tools/package_launch.py --packet-gap-ms 40

The output is dist/LaunchApp-V2.2.2-responsive-40ms.zip. The packager maps source modules to the filenames expected by MatrixOS and Ableton Live. It does not install files into the device, Live, a User Library, or a Live Set. Generated ZIPs are ignored by Git.

## Change rules

- Keep V1 v7 and V2 v11 endpoints paired and independently usable.
- Preserve Live as the state authority.
- Keep device modules within the tested MicroPython memory budget.
- Do not change MatrixOS core or install into the user's environment during automated work.
- Update English and Simplified Chinese documentation together.
- Treat automated tests, Live logs, and physical-device observations as separate evidence levels.
