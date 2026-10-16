"""ADV-05 -- real acceptance tests (Directiva 37: fix applied and validated).

These were historical defect characterizations (passing while confirming
the defect's presence). The account owner applied the authorized
change-control fix in src/refresh/{firms,dmc}_refresh.py::_publish
(append_jsonl now runs before atomic_write_json). Every assertion below has
been inverted to require the CORRECT post-fix behavior; none of them
tolerate the old defective behavior anymore. See
docs/evidence/adv05-fix-validated-20261015/ for the full validation report
and docs/evidence/adv05-change-control-proposal-20261015/ for the diff.
"""
from __future__ import annotations

import io
import json
import socket
from datetime import timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest

from test_remediation_red_defects import (
    BASE_END, CREDS, MAP_KEY, NOW, STATION, _make_firms_factory,
    _block_all_network, firms_paths,
)
import src.refresh.firms_refresh as fr
import src.refresh.dmc_refresh as dmc
from test_refresh_adversarial import (
    FakeFirmsClient, FakeDmcSession, _dmc_records_range, _dmc_payload,
    dmc_paths, API_COLUMNS,
)

def test_adv05_firms_history_failure_leaves_pointer_unchanged(firms_paths, monkeypatch):
    """Fixed: a history-append failure on a second publication must leave
    CURRENT byte-identical to the previously published version."""
    factory = _make_firms_factory()

    # Publicación 1 exitosa
    fr.refresh(paths=firms_paths, client_factory=factory, map_key=MAP_KEY, today=BASE_END + timedelta(days=2))
    v1_pointer_bytes = firms_paths.pointer.read_bytes()

    # Publicación 2: simulamos fallo de disco durante el append del historial
    def _fail_append(path, record):
        raise OSError("Fallo simulado: disco lleno al escribir pointer_history.jsonl")

    monkeypatch.setattr(fr, "append_jsonl", _fail_append)

    with pytest.raises(OSError, match="disco lleno"):
        fr.refresh(paths=firms_paths, client_factory=factory, map_key=MAP_KEY, today=BASE_END + timedelta(days=4))

    assert firms_paths.pointer.read_bytes() == v1_pointer_bytes, (
        "ADV-05 regresion: el puntero avanzo pese al fallo de historial"
    )


def test_adv05_firms_retry_reconciles_history_after_failed_append(firms_paths, monkeypatch):
    """Fixed: once append_jsonl works again, a retry must actually publish
    the new version (not report a false up_to_date), and the final pointer
    must be reflected in history."""
    factory = _make_firms_factory()

    # Publicación 1
    fr.refresh(paths=firms_paths, client_factory=factory, map_key=MAP_KEY, today=BASE_END + timedelta(days=2))

    # Publicación 2 con fallo de append
    def _fail_append(path, record):
        raise OSError("Fallo simulado de disco")

    original_append = fr.append_jsonl
    monkeypatch.setattr(fr, "append_jsonl", _fail_append)

    with pytest.raises(OSError):
        fr.refresh(paths=firms_paths, client_factory=factory, map_key=MAP_KEY, today=BASE_END + timedelta(days=4))

    # Restaurar append normal para la corrida de reintento
    monkeypatch.setattr(fr, "append_jsonl", original_append)
    with pytest.raises(AssertionError, match="red"):
        socket.create_connection(("127.0.0.1", 9))

    # Reintento (replay): debe publicar de verdad, no reportar up_to_date
    outcome_retry = fr.refresh(paths=firms_paths, client_factory=factory, map_key=MAP_KEY, today=BASE_END + timedelta(days=4))
    assert outcome_retry.status != "up_to_date", (
        "ADV-05 regresion: el reintento reporto up_to_date en vez de publicar"
    )

    # El historial debe contener la Versión 2 finalmente publicada
    current_sha = json.loads(firms_paths.pointer.read_text("utf-8"))["sha256"]
    history_events = [
        json.loads(line) for line in firms_paths.history.read_text("utf-8").splitlines()
    ]
    history_shas = [ev.get("sha256") for ev in history_events]

    assert current_sha in history_shas, (
        "ADV-05 regresion: la version publicada no quedo registrada en el historial"
    )


def test_adv05_dmc_history_failure_prevents_first_publication(tmp_path, monkeypatch):
    """Fixed: on a first publication, a history-append failure must leave
    CURRENT.json absent -- nothing partially committed."""
    paths = dmc.DmcPaths(root=tmp_path / "dmc")
    aug = [
        {
            "momento": "2026-08-31 22:00:00",
            "temperatura": "18.0 °C",
            "humedadRelativa": "70 %",
            "fuerzaDelViento": "5.0 kt",
            "direccionDelViento": "180 °",
        }
    ]
    sep = [
        {
            "momento": "2026-09-01 02:00:00",
            "temperatura": "17.5 °C",
            "humedadRelativa": "72 %",
            "fuerzaDelViento": "4.5 kt",
            "direccionDelViento": "190 °",
        }
    ]

    def _payload(records):
        return {
            "organismo": "DMC",
            "pais": "Chile",
            "producto": "Datos Recientes",
            "timezone": "UTC",
            "registros": len(records),
            "datosEstaciones": {
                "estacion": {"codigoNacional": STATION, "nombreEstacion": "Rodelillo"},
                "datos": records,
            },
        }

    session = MagicMock()

    def _mock_get(url, *args, **kwargs):
        year, month = url.rstrip("/").split("/")[-2:]
        m_key = f"{year}-{int(month):02d}"
        resp = MagicMock(status_code=200)
        if m_key == "2026-08":
            resp.json.return_value = _payload(aug)
        elif m_key == "2026-09":
            resp.json.return_value = _payload(sep)
        else:
            resp.status_code = 404
            resp.json.side_effect = ValueError("Not found")
        return resp

    session.get.side_effect = _mock_get

    def _fail_append(path, record):
        raise OSError("Fallo simulado en historial DMC")

    monkeypatch.setattr(dmc, "append_jsonl", _fail_append)

    with pytest.raises(OSError, match="Fallo simulado"):
        dmc.refresh(paths=paths, session=session, credentials=CREDS, now=NOW, sleep=lambda _: None)

    assert not paths.pointer.exists(), (
        "ADV-05 regresion en DMC: CURRENT.json se creo pese al fallo de historial"
    )


def test_adv05a_firms_history_append_failure_prevents_pointer_write(firms_paths, monkeypatch):
    """Fixed (ex ADV-05a): si el append al historial falla por error de I/O,
    la excepcion debe propagarse, el lock debe liberarse limpiamente, y
    CURRENT.json NUNCA debe escribirse (el historial se intenta primero)."""
    def factory(raw_dir: Path):
        client = MagicMock()
        client.fetch_availability.return_value = FakeFirmsClient().fetch_availability()
        from src.ingesta.nasa_firms_backfill import NRT_SOURCE
        raw_csv = raw_dir / "test.csv"
        raw_csv.parent.mkdir(parents=True, exist_ok=True)
        row_str = "-33.05,-71.4,331.0,0.5,0.4,2026-08-31,1745,N,VIIRS,n,2.0NRT,291.0,4.1,D\n"
        raw_csv.write_text(API_COLUMNS + "\n" + row_str, encoding="utf-8")
        df = pd.read_csv(io.StringIO(API_COLUMNS + "\n" + row_str))
        df["firms_source"] = NRT_SOURCE
        df["request_start_date"] = "2026-08-31"
        client.download_window.return_value = (raw_csv, df)
        return client

    def _boom_append(path, record):
        raise OSError("Fallo simulado: disco lleno al escribir historial")

    monkeypatch.setattr(fr, "append_jsonl", _boom_append)

    with pytest.raises(OSError, match="disco lleno"):
        fr.refresh(paths=firms_paths, client_factory=factory, map_key=MAP_KEY, today=BASE_END + timedelta(days=2))

    # El lock se liberó mediante el bloque finally
    assert not firms_paths.lock.exists()

    # Comprobación de estado (post-fix): nada se publicó -- ni CURRENT ni historial
    assert not firms_paths.pointer.exists(), (
        "ADV-05 regresion: CURRENT.json se escribio pese a que el historial fallo primero"
    )
    assert not firms_paths.history.exists() or len(firms_paths.history.read_text("utf-8").strip()) == 0


def test_adv05b_dmc_history_append_failure_prevents_pointer_write(dmc_paths, monkeypatch):
    """Fixed (ex ADV-05b): verificación homóloga en DMC: un fallo de I/O al
    escribir el historial propaga el error, libera el lock, y evita que
    CURRENT.json se escriba -- nunca deja el puntero desincronizado del
    historial."""
    aug = _dmc_records_range("2026-08-31T22:00", "2026-08-31T23:45")
    sep = _dmc_records_range("2026-09-01T00:00", "2026-09-01T02:00")
    session = FakeDmcSession({"2026-08": _dmc_payload(aug), "2026-09": _dmc_payload(sep)})

    def _boom_append(path, record):
        raise OSError("Fallo simulado: disco lleno en DMC audit history")

    monkeypatch.setattr(dmc, "append_jsonl", _boom_append)

    with pytest.raises(OSError, match="disco lleno"):
        dmc.refresh(paths=dmc_paths, session=session, credentials=CREDS, now=NOW, sleep=lambda _: None)

    # El lock fue liberado
    assert not dmc_paths.lock.exists()

    # Comprobación de estado (post-fix): CURRENT.json nunca se escribio
    assert not dmc_paths.pointer.exists(), (
        "ADV-05 regresion en DMC: CURRENT.json se escribio pese a que el historial fallo primero"
    )
    assert not dmc_paths.history.exists() or len(dmc_paths.history.read_text("utf-8").strip()) == 0
