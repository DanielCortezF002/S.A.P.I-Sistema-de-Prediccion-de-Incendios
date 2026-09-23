"""Lock de escritor único por fuente, portable (Windows, Linux y bind mounts).

`fcntl.flock` no existe en Windows y no cruza el límite host <-> VM de
Docker Desktop; `os.open(O_CREAT | O_EXCL)` sí es atómico en ambos. El lock
no espera: si otro refresco está corriendo, falla de inmediato. Un lock
huérfano (proceso muerto) solo se rompe con `break_stale=True` explícito.
"""

from __future__ import annotations

import json
import os
import socket
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

STALE_AFTER = timedelta(hours=2)


class RefreshLockedError(RuntimeError):
    """Otro refresco de la misma fuente tiene el lock."""


def _read_lock(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _lock_age(info: dict, now: datetime) -> timedelta | None:
    try:
        return now - datetime.fromisoformat(info["started_at"])
    except (KeyError, TypeError, ValueError):
        return None


@contextmanager
def refresh_lock(
    path: Path, *, break_stale: bool = False, now: datetime | None = None
) -> Iterator[dict]:
    now = now or datetime.now(timezone.utc)
    info = {
        "pid": os.getpid(),
        "host": socket.gethostname(),
        "started_at": now.isoformat(),
        "command": " ".join(sys.argv[:3]),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    for _ in range(2):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            holder = _read_lock(path)
            age = _lock_age(holder, now)
            stale = age is None or age > STALE_AFTER
            if not (break_stale and stale):
                detail = "huérfano, use --break-stale-lock" if stale else "en curso"
                raise RefreshLockedError(
                    f"Refresco bloqueado por {path.name} ({detail}): "
                    f"host={holder.get('host')} pid={holder.get('pid')} "
                    f"desde={holder.get('started_at')}"
                ) from None
            path.unlink(missing_ok=True)
    else:  # pragma: no cover - otro proceso ganó la carrera tras romperlo
        raise RefreshLockedError(
            f"No se pudo tomar {path.name} tras romper el lock huérfano."
        )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(info, handle)
        yield info
    finally:
        path.unlink(missing_ok=True)
