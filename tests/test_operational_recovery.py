"""Recovery rehearsal: synthetic DMC, temporary stores, network forbidden."""

import hashlib
import json

import pytest

from src.refresh.lock import RefreshLockedError, refresh_lock
from test_dmc_refresh import AUG, SEP, FakeDmc, _payload, _records, _run
from src.refresh import dmc_refresh as dmc
from tools.ops.dmc_recovery import return_to_absence


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    import socket

    def refuse(*args, **kwargs):
        raise AssertionError("Real network forbidden in recovery rehearsal")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def recover(paths, **kwargs):
    return return_to_absence(
        paths,
        expected_sha256=kwargs.get("expected_sha256", digest(paths.pointer)),
        initial_current_absent=kwargs.get("initial_current_absent", True),
        consumers_stopped=kwargs.get("consumers_stopped", True),
    )


def publish(paths):
    _run(paths, FakeDmc({"2026-08": _payload(AUG), "2026-09": _payload(SEP)}))


def test_recovery_rehearsal_from_absence_through_corruption_and_rollback(tmp_path):
    paths = dmc.DmcPaths(root=tmp_path / "dmc")
    assert dmc.status(paths=paths)["origin"] == "none"
    publish(paths)
    first = dmc.read_current(paths)
    assert first is not None
    later = _records("2026-09-01T03:15", "2026-09-01T06:00")
    _run(paths, FakeDmc({"2026-09": _payload(later)}))
    assert dmc.status(paths=paths)["origin"] == "current"
    paths.pointer.write_text("{invalid", encoding="utf-8")
    assert dmc.status(paths=paths)["origin"] == "invalid_pointer"
    dmc.rollback(first["manifest_sha256"][:12], paths=paths)
    assert dmc.read_current(paths) == first
    preserved = {
        p: digest(p)
        for folder in (paths.versions_dir, paths.pointers_dir)
        for p in folder.iterdir()
    }
    history = paths.history.read_bytes()
    pointer_hash = digest(paths.pointer)
    event = recover(paths)
    assert dmc.status(paths=paths)["origin"] == "none"
    assert not paths.lock.exists()
    assert digest(paths.station_dir / event["quarantine"]) == pointer_hash
    assert all(digest(p) == sha for p, sha in preserved.items())
    assert paths.history.read_bytes().startswith(history)
    events = [
        json.loads(line)["event"] for line in paths.history.read_text().splitlines()
    ]
    assert events[-2:] == ["return_to_absence_intent", "return_to_absence_complete"]


@pytest.mark.parametrize("corrupt", [False, True])
def test_first_publication_can_return_to_absence_without_deleting_bytes(
    tmp_path, corrupt
):
    paths = dmc.DmcPaths(root=tmp_path / "dmc")
    publish(paths)
    if corrupt:
        paths.pointer.write_text("broken", encoding="utf-8")
    before = paths.pointer.read_bytes()
    event = recover(paths)
    assert (paths.station_dir / event["quarantine"]).read_bytes() == before
    assert not paths.pointer.exists()


@pytest.mark.parametrize(
    "overrides",
    [
        {"initial_current_absent": False},
        {"consumers_stopped": False},
        {"expected_sha256": "0" * 64},
    ],
)
def test_recovery_refuses_missing_attestations_or_changed_pointer(tmp_path, overrides):
    paths = dmc.DmcPaths(root=tmp_path / "dmc")
    publish(paths)
    before, history = paths.pointer.read_bytes(), paths.history.read_bytes()
    with pytest.raises(ValueError):
        recover(paths, **overrides)
    assert paths.pointer.read_bytes() == before
    assert paths.history.read_bytes() == history


def test_recovery_never_breaks_an_existing_lock(tmp_path):
    paths = dmc.DmcPaths(root=tmp_path / "dmc")
    publish(paths)
    before = paths.pointer.read_bytes()
    with refresh_lock(paths.lock):
        with pytest.raises(RefreshLockedError):
            recover(paths)
        assert paths.lock.exists()
    assert paths.pointer.read_bytes() == before
