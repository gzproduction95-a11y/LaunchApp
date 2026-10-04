"""Build the standalone V2 link-only diagnostic for a controlled A/B test."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist" / "LaunchApp-link-only-check.zip"
SOURCE = ROOT / "RemoteScripts" / "LaunchLinkOnly"
DESTINATION = "Ableton-User-Library/Remote Scripts/LaunchLinkOnly"


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(OUT, "w", ZIP_DEFLATED) as bundle:
        for filename in ("__init__.py", "protocol.py"):
            bundle.write(SOURCE / filename, DESTINATION + "/" + filename)
        bundle.write(ROOT / "docs/LINK_ONLY_DIAGNOSTIC.md", "READ_ME_FIRST.md")
    print("Wrote {} ({} bytes)".format(OUT.relative_to(ROOT), OUT.stat().st_size))


if __name__ == "__main__":
    main()
