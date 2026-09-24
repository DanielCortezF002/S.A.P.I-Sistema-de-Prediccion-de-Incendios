"""Primitivas del refresco (SAPI-71 Fase B): escritura atómica, lock y redacción."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone

import pytest

import src.refresh.atomic as atomic
from src.refresh.lock import STALE_AFTER, RefreshLockedError, refresh_lock
from src.refresh.redact import REDACTED, redact


def test_atomic_write_replaces_whole_file(tmp_path):
    target = tmp_path / "CURRENT.json"
    atomic.atomic_write_json(target, {"v": 1})
    atomic.atomic_write_json(target, {"v": 2})
    assert json.loads(target.read_text(encoding="utf-8")) == {"v": 2}
    assert [p.name for p in tmp_path.iterdir()] == ["CURRENT.json"]  # sin temporales


def test_failed_replace_keeps_previous_content_and_no_temp(tmp_path, monkeypatch):
    target = tmp_path / "CURRENT.json"
    atomic.atomic_write_json(target, {"v": 1})

    def _boom(*_args, **_kwargs):
        raise OSError("fallo simulado en os.replace")

    monkeypatch.setattr(atomic.os, "replace", _boom)
    with pytest.raises(OSError):
        atomic.atomic_write_json(target, {"v": 2})

    assert json.loads(target.read_text(encoding="utf-8")) == {"v": 1}
    assert [p.name for p in tmp_path.iterdir()] == ["CURRENT.json"]


def test_replace_retries_transient_permission_error(tmp_path, monkeypatch):
    real_replace = os.replace
    calls = {"n": 0}

    def _flaky(src, dst):
        calls["n"] += 1
        if calls["n"] == 1:
            raise PermissionError("destino abierto por otro proceso (Windows)")
        real_replace(src, dst)

    monkeypatch.setattr(atomic.os, "replace", _flaky)
    monkeypatch.setattr(atomic.time, "sleep", lambda _: None)
    atomic.atomic_write_bytes(tmp_path / "a.csv", b"ok\n")
    assert (tmp_path / "a.csv").read_bytes() == b"ok\n" and calls["n"] == 2


def test_write_immutable_is_idempotent_and_refuses_changes(tmp_path):
    version = tmp_path / "v.csv"
    assert atomic.write_immutable(version, b"a\n") is True
    assert atomic.write_immutable(version, b"a\n") is False
    with pytest.raises(atomic.ImmutableVersionError):
        atomic.write_immutable(version, b"b\n")
    assert version.read_bytes() == b"a\n"


def test_append_jsonl_keeps_history(tmp_path):
    history = tmp_path / "h.jsonl"
    atomic.append_jsonl(history, {"event": "publish"})
    atomic.append_jsonl(history, {"event": "rollback"})
    lines = history.read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["event"] for line in lines] == ["publish", "rollback"]


def test_lock_is_exclusive_and_released(tmp_path):
    lock = tmp_path / ".refresh.lock"
    with refresh_lock(lock) as info:
        assert lock.exists() and info["pid"] == os.getpid()
        with pytest.raises(RefreshLockedError, match="en curso"):
            with refresh_lock(lock):
                pass
    assert not lock.exists()


def test_lock_released_on_error(tmp_path):
    lock = tmp_path / ".refresh.lock"
    with pytest.raises(ValueError):
        with refresh_lock(lock):
            raise ValueError("fallo dentro del refresco")
    assert not lock.exists()


def _stale_lock(path, age):
    started = datetime.now(timezone.utc) - age
    path.write_text(
        json.dumps({"pid": 1, "host": "h", "started_at": started.isoformat()})
    )


def test_stale_lock_requires_explicit_break(tmp_path):
    lock = tmp_path / ".refresh.lock"
    _stale_lock(lock, STALE_AFTER + timedelta(minutes=1))
    with pytest.raises(RefreshLockedError, match="huérfano"):
        with refresh_lock(lock):
            pass
    assert lock.exists()
    with refresh_lock(lock, break_stale=True):
        assert json.loads(lock.read_text())["pid"] == os.getpid()
    assert not lock.exists()


def test_break_stale_never_breaks_a_fresh_lock(tmp_path):
    lock = tmp_path / ".refresh.lock"
    _stale_lock(lock, timedelta(minutes=5))
    with pytest.raises(RefreshLockedError, match="en curso"):
        with refresh_lock(lock, break_stale=True):
            pass
    assert json.loads(lock.read_text())["pid"] == 1


def test_redact_removes_every_secret():
    text = "GET /api/area/csv/KEY123/x?usuario=u&token=TOK456 fallo"
    out = redact(text, ["KEY123", "TOK456", ""])
    assert "KEY123" not in out and "TOK456" not in out and out.count(REDACTED) == 2


@pytest.mark.parametrize(
    "secret",
    ["sapi@dmc.cl", "tok+en/42=", "a%2Fb", "con espacio", "ñandú=1"],
)
def test_redact_removes_url_encoded_variants(secret):
    from urllib.parse import quote, quote_plus

    forms = [
        secret,
        quote_plus(secret),
        quote(secret, safe=""),
        quote(secret),
        # escapes en minúscula (%2f): los aceptan los servidores y algunas libs
        re.sub(r"%[0-9A-F]{2}", lambda m: m.group().lower(), quote_plus(secret)),
    ]
    text = " | ".join(f"url?token={form}" for form in forms)

    out = redact(text, [secret])

    for form in forms:
        assert form not in out
    assert out.count(REDACTED) == len(forms)


def test_redact_keeps_non_secret_text():
    out = redact("ConnectionError para 2026-09", ["sapi@dmc.cl", ""])
    assert out == "ConnectionError para 2026-09"
