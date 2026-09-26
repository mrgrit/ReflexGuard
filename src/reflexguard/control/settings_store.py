"""Local restart-only calibration with atomic writes and optimistic concurrency."""
import fcntl
import hashlib
import os
import secrets
import stat
import tempfile
import time
from pathlib import Path
from pydantic import BaseModel, ConfigDict, Field
from reflexguard.control.config import Calibration

ROOT = Path(__file__).resolve().parents[3]


class Snapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    calibration: Calibration
    revision: str = Field(pattern=r"^[a-f0-9]{64}$")
    actor: str = Field(max_length=80)
    changed_ms: int = Field(ge=0)


class RevisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    expected_revision: str = Field(pattern=r"^[a-f0-9]{64}$")


class SaveRequest(RevisionRequest):
    calibration: Calibration


class StaleSettings(ValueError):
    """Another editor saved since this page was read."""


def read_bounded(path: Path) -> bytes:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError("Expected regular settings file")
        data = stream.read(16385)
    if len(data) > 16384:
        raise ValueError("Settings file too large")
    return data


class CalibrationStore:
    def __init__(self, root: Path = ROOT):
        # root is selected by application code, never by an HTTP request.
        self.root = root
        self.directory = root / ".local-control"
        self.path = self.directory / "calibration.json"

    def defaults(self) -> Calibration:
        return Calibration.model_validate_json(read_bounded(self.root / "config/control.json"))

    def snapshot(self) -> Snapshot:
        if self.directory.is_symlink():
            raise ValueError("Settings directory must not be a symlink")
        try:
            return Snapshot.model_validate_json(read_bounded(self.path))
        except FileNotFoundError:
            default = self.defaults()
            revision = hashlib.sha256(default.model_dump_json().encode()).hexdigest()
            return Snapshot(calibration=default, revision=revision, actor="default", changed_ms=0)

    def save(self, expected_revision: str, calibration: Calibration, actor: str) -> Snapshot:
        self.directory.mkdir(mode=0o700, exist_ok=True)
        if self.directory.is_symlink():
            raise ValueError("Settings directory must not be a symlink")
        fd = os.open(self.directory / "lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        with os.fdopen(fd, "rb") as lock:
            if not stat.S_ISREG(os.fstat(lock.fileno()).st_mode):
                raise ValueError("Expected regular lock file")
            fcntl.flock(lock, fcntl.LOCK_EX)
            if self.snapshot().revision != expected_revision:
                raise StaleSettings("Settings changed")
            snapshot = Snapshot(calibration=calibration, revision=secrets.token_hex(32),
                                actor=actor, changed_ms=int(time.time() * 1000))
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.directory,
                                                 prefix="pending-", delete=False) as stream:
                    temporary = Path(stream.name)
                    stream.write(snapshot.model_dump_json() + "\n")
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, self.path)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
            return snapshot
