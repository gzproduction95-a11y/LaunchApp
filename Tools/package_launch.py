"""Build the matched LaunchApp V2.2.2 release App and Live Remote Script."""

from pathlib import Path
import argparse
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "dist"
DEVICE = [
    ("AppInfo.json", "AppInfo.json"),
    ("bootstrap_v2.py", "main.py"),
    ("main_v2.py", "main_v2.py"),
    ("protocol_v2.py", "protocol_v2.py"),
    ("input_events.py", "input_events.py"),
    ("display_receiver.py", "display_receiver.py"),
]
REMOTE = [
    ("__init___v2.py", "__init__.py"),
    ("legacy.py", "legacy.py"),
    ("model.py", "model.py"),
    ("protocol.py", "protocol.py"),
    ("timing.py", "timing.py"),
    ("protocol_v2.py", "protocol_v2.py"),
    ("input_events.py", "input_events.py"),
    ("controller.py", "controller.py"),
    ("gestures.py", "gestures.py"),
    ("navigation.py", "navigation.py"),
    ("phase.py", "phase.py"),
    ("rendering.py", "rendering.py"),
    ("state.py", "state.py"),
    ("display_stream.py", "display_stream.py"),
    ("frame_sender.py", "frame_sender.py"),
    ("slot_stream.py", "slot_stream.py"),
    ("slot_sender.py", "slot_sender.py"),
]


def main(packet_gap_ms=40):
    if not 10 <= int(packet_gap_ms) <= 100:
        raise ValueError("packet gap must be between 10 and 100 ms")
    packet_gap_ms = int(packet_gap_ms)
    output = OUT_DIR / "LaunchApp-V2.2.2-responsive-{}ms.zip".format(packet_gap_ms)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "w", ZIP_DEFLATED) as bundle:
        for source, target in DEVICE:
            bundle.write(ROOT / "PythonApps/Launch" / source,
                         "Mystrix-SD/MatrixOS/Applications/Launch/" + target)
        for source, target in REMOTE:
            source_path = ROOT / "RemoteScripts/Launch" / source
            target_path = "Ableton-User-Library/Remote Scripts/Launch/" + target
            if source == "__init___v2.py":
                host_source = source_path.read_text(encoding="utf-8")
                host_source = host_source.replace(
                    "FRAME_PACKET_GAP_MS = 40",
                    "FRAME_PACKET_GAP_MS = {}".format(packet_gap_ms), 1)
                bundle.writestr(target_path, host_source)
            else:
                bundle.write(source_path, target_path)
        documentation = (
            "INSTALLATION.md", "INSTALLATION.zh-CN.md",
            "USER_GUIDE.md", "USER_GUIDE.zh-CN.md",
            "ARCHITECTURE.md", "ARCHITECTURE.zh-CN.md",
            "DEVELOPMENT.md", "DEVELOPMENT.zh-CN.md",
            "VALIDATION.md", "VALIDATION.zh-CN.md",
            "RELEASE_NOTES_V2.2.2.md",
        )
        for name in documentation:
            bundle.write(ROOT / "docs" / name, "docs/" + name)
        for name in ("README.md", "README.zh-CN.md", "CHANGELOG.md",
                     "CONTRIBUTING.md", "SUPPORT.md", "LICENSE",
                     "LICENSE.zh-CN.md", "NOTICE.md"):
            bundle.write(ROOT / name, name)
    print("Wrote {} ({} bytes)".format(output.relative_to(ROOT), output.stat().st_size))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet-gap-ms", type=int, default=40,
                        help="minimum gap between SysEx frame packets (default: 40)")
    main(parser.parse_args().packet_gap_ms)
