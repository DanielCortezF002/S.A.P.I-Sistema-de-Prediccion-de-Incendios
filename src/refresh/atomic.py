"""Escritura atómica y publicación de punteros `CURRENT.json`.

Un lector nunca ve un archivo a medio escribir: todo se escribe en un
temporal del MISMO directorio, se hace `fsync` y se publica con
`os.replace` (atómico dentro de un mismo filesystem, también en Windows).
Las versiones son inmutables: si el destino ya existe, solo se acepta si
sus bytes son idénticos.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any


class ImmutableVersionError(RuntimeError):
    """El destino de una versión ya existe con contenido distinto."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _fsync_dir(directory: Path) -> None:
    # En Windows no se puede abrir un directorio para fsync; NTFS ya
    # registra el rename en su journal.
    if os.name == "nt":
        return
    fd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _replace_with_retry(src: str, dst: Path, attempts: int = 5) -> None:
    """En Windows `os.replace` falla con PermissionError si otro proceso
    tiene el destino abierto; se reintenta brevemente antes de rendirse."""
    for attempt in range(attempts):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(0.2 * (attempt + 1))


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """Escribe `data` en `path` de forma atómica (temp + fsync + replace)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        _replace_with_retry(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise
    _fsync_dir(path.parent)


def write_immutable(path: Path, data: bytes) -> bool:
    """Publica una versión inmutable. Devuelve False si ya existía con los
    mismos bytes (idempotente); lanza `ImmutableVersionError` si existía
    con otros."""
    if path.exists():
        if sha256_bytes(path.read_bytes()) == sha256_bytes(data):
            return False
        raise ImmutableVersionError(
            f"{path.name} ya existe con contenido distinto: las versiones son inmutables."
        )
    atomic_write_bytes(path, data)
    if sha256_bytes(path.read_bytes()) != sha256_bytes(data):
        raise ImmutableVersionError(
            f"{path.name} no coincide con lo escrito tras publicarlo."
        )
    return True


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    atomic_write_bytes(path, text.encode("utf-8"))


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    """Historial append-only (auditoría); una línea por evento."""
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(line)
        handle.flush()
        os.fsync(handle.fileno())
