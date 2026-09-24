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


if __name__ == "__main__":
    configure(Path(__file__).resolve().parents[1])
