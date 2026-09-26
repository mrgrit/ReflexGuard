"""Persistence and restart boundaries of the operator's local calibration."""
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest
from reflexguard.control.config import Calibration
from reflexguard.control.settings_store import CalibrationStore, StaleSettings


@pytest.fixture
def store(tmp_path):
    (tmp_path / "config").mkdir()
    source = Path(__file__).resolve().parents[1] / "config/control.json"
    (tmp_path / "config/control.json").write_bytes(source.read_bytes())
    return CalibrationStore(tmp_path)


def test_restart_loads_saved_values_without_mutating_running_configuration(store, monkeypatch):
    monkeypatch.setattr("reflexguard.control.settings_store.CalibrationStore", lambda: store)
    running = Calibration.load()
    before = store.snapshot()
    changed = Calibration.model_validate(dict(running.model_dump(), stop_on=.4))
    store.save(before.revision, changed, "operator")
    assert Calibration.load().stop_on == .4
    assert running.stop_on == .25
    assert store.defaults().stop_on == .25
    assert store.path.stat().st_mode & 0o777 == 0o600


def test_concurrent_edit_only_one_writer_succeeds(store):
    before = store.snapshot()
    def save(_):
        try:
            store.save(before.revision, before.calibration, "operator")
            return True
        except StaleSettings:
            return False
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert sum(pool.map(save, range(4))) == 1


@pytest.mark.parametrize("bad", [b"{}", b"x" * 16385, b'{"calibration": {"stop_on": NaN}}'])
def test_corrupt_settings_fail_closed(store, bad):
    store.directory.mkdir()
    store.path.write_bytes(bad)
    with pytest.raises(ValueError):
        store.snapshot()


def test_symlinks_and_special_files_rejected(store, tmp_path):
    store.directory.mkdir()
    store.path.symlink_to(tmp_path / "missing")
    with pytest.raises(OSError):
        store.snapshot()
    store.path.unlink()
    os.mkfifo(store.path)
    with pytest.raises(ValueError):
        store.snapshot()


def test_atomic_save_failure_keeps_last_valid_snapshot(store, monkeypatch):
    before = store.snapshot()
    store.save(before.revision, before.calibration, "operator")
    before = store.snapshot()
    def fail(*args):
        raise OSError("write failure")
    monkeypatch.setattr("reflexguard.control.settings_store.os.replace", fail)
    with pytest.raises(OSError):
        store.save(before.revision, before.calibration, "admin")
    assert store.snapshot() == before
    assert not list(store.directory.glob("pending-*"))


def test_symlink_directory_rejected(store, tmp_path):
    destination = tmp_path / "outside"
    destination.mkdir()
    store.directory.symlink_to(destination, target_is_directory=True)
    with pytest.raises(ValueError):
        store.snapshot()
    with pytest.raises(ValueError):
        store.save("0" * 64, store.defaults(), "operator")
