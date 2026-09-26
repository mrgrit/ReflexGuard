"""Generate machine-local Webots interpreter paths without shell expansion."""
from pathlib import Path


def configure(root: Path) -> None:
    python = root / ".venv/bin/python"
    if not python.is_file():
        raise ValueError("Create the project virtual environment first")
    # Do not resolve the Python symlink: that would select system site-packages.
    for name in ("wheelchair", "scenario"):
        directory = root / "webots/controllers" / name
        template = (directory / "runtime.ini.in").read_text(encoding="utf-8")
        (directory / "runtime.ini").write_text(template.replace("@PYTHON@", str(python)), encoding="utf-8")
    layout = root / "webots/worlds/.corridor_demo.wbproj"
    template = root / "webots/worlds/corridor_demo.wbproj.in"
    if template.is_file():
        overlays = [line for line in layout.read_text().splitlines() if line.startswith("renderingDevicePerspectives:")] if layout.is_file() else []
        # Initialize absent/default overlapping overlays; preserve user-arranged layouts.
        if not layout.exists() or overlays and all(line.endswith(";0;0") for line in overlays):
            layout.write_text(template.read_text(), encoding="utf-8")


if __name__ == "__main__":
    configure(Path(__file__).resolve().parents[1])
