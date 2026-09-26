"""Build a standalone, read-only LaunchApp handshake check."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist" / "LaunchApp-handshake-check.zip"
SOURCE = ROOT / "RemoteScripts" / "LaunchHandshake"
DESTINATION = "Ableton-User-Library/Remote Scripts/LaunchHandshake"


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(OUT, "w", ZIP_DEFLATED) as bundle:
        for filename in ("__init__.py", "protocol.py"):
            bundle.write(SOURCE / filename, DESTINATION + "/" + filename)
        bundle.write(
            ROOT / "docs/INSTALLATION.md",
            "INSTALLATION.md",
        )
    print("Wrote {} ({} bytes)".format(OUT.relative_to(ROOT), OUT.stat().st_size))


if __name__ == "__main__":
    main()
