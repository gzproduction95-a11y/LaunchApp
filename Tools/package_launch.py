"""Build a local LaunchApp release bundle under ignored dist/."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist" / "LaunchApp-V1.zip"
FILES = [
    ("PythonApps/Launch", ["AppInfo.json", "main.py", "controller.py", "gestures.py", "protocol.py", "state.py", "rendering.py", "navigation.py", "phase.py"]),
    ("RemoteScripts/Launch", ["__init__.py", "model.py", "protocol.py", "timing.py"]),
]

def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(OUT, "w", ZIP_DEFLATED) as bundle:
        for folder, filenames in FILES:
            root_folder = "Mystrix-SD/MatrixOS/Applications/Launch" if folder.startswith("PythonApps") else "Ableton-User-Library/Remote Scripts/Launch"
            for filename in filenames:
                source = ROOT / folder / filename
                bundle.write(source, root_folder + "/" + filename)
        bundle.write(ROOT / "docs/INSTALLATION.md", "INSTALLATION.md")
        bundle.write(ROOT / "docs/USER_GUIDE.md", "USER_GUIDE.md")
        bundle.write(ROOT / "docs/VALIDATION.md", "VALIDATION.md")
    print("Wrote {} ({} bytes)".format(OUT.relative_to(ROOT), OUT.stat().st_size))

if __name__ == "__main__":
    main()
