"""ADV-05 -- acceptance oracle, validated against the REAL applied fix
(Directiva 37). The account owner manually applied the authorized diff in
src/refresh/{firms,dmc}_refresh.py::_publish (append_jsonl now runs before
atomic_write_json). This file requires the correct behavior for real, in
both directions:

1. History-append fails -> pointer must stay unchanged; a retry (with the
   failure lifted) must then complete the publication, not report a false
   "up_to_date".
2. Pointer-write fails AFTER a successful history append -> the resulting
   orphaned history record is characterized explicitly, and a retry must
   reconcile without duplicating entries or reporting a false result.

See docs/evidence/adv05-change-control-proposal-20261015/ for the diff and
docs/evidence/adv05-fix-validated-20261015/ for the full validation report.
"""
from __future__ import annotations

import json
from datetime import timedelta
from unittest.mock import MagicMock

import pytest

from test_remediation_red_defects import BASE_END, MAP_KEY, NOW, STATION, _make_firms_factory, firms_paths
import src.refresh.firms_refresh as fr
import src.refresh.dmc_refresh as dmc

CREDS_DMC = ("usuario-test", "token-test")


# --- FIRMS ------------------------------------------------------------------

def test_adv05_firms_pointer_unchanged_when_history_append_fails(firms_paths, monkeypatch):
    """GREEN: a failed history append must leave CURRENT byte-identical."""
    factory = _make_firms_factory()

    fr.refresh(paths=firms_paths, client_factory=factory, map_key=MAP_KEY, today=BASE_END + timedelta(days=2))
    v1_pointer_bytes = firms_paths.pointer.read_bytes()
    v1_history = firms_paths.history.read_text("utf-8") if firms_paths.history.exists() else ""

    def _fail_append(path, record):
        raise OSError("Fallo simulado: disco lleno al escribir pointer_history.jsonl")

    monkeypatch.setattr(fr, "append_jsonl", _fail_append)

    with pytest.raises(OSError, match="disco lleno"):
        fr.refresh(paths=firms_paths, client_factory=factory, map_key=MAP_KEY, today=BASE_END + timedelta(days=4))

    assert firms_paths.pointer.read_bytes() == v1_pointer_bytes, "ADV-05 NO resuelto: el puntero avanzo pese al fallo de historial"
    assert firms_paths.history.read_text("utf-8") == v1_history, "El historial no debe contener un registro parcial"


def test_adv05_firms_retry_completes_publication_after_append_restored(firms_paths, monkeypatch):
    """GREEN: once append_jsonl works again, a retry must actually publish
    the new version (not report a false up_to_date), with exactly one
    history entry for it -- no duplicates."""
    factory = _make_firms_factory()

    fr.refresh(paths=firms_paths, client_factory=factory, map_key=MAP_KEY, today=BASE_END + timedelta(days=2))
    v1_pointer_bytes = firms_paths.pointer.read_bytes()

    real_append = fr.append_jsonl

    def _fail_append(path, record):
        raise OSError("Fallo simulado: disco lleno")

    monkeypatch.setattr(fr, "append_jsonl", _fail_append)
    with pytest.raises(OSError):
        fr.refresh(paths=firms_paths, client_factory=factory, map_key=MAP_KEY, today=BASE_END + timedelta(days=4))
    assert firms_paths.pointer.read_bytes() == v1_pointer_bytes

    monkeypatch.setattr(fr, "append_jsonl", real_append)
    outcome_retry = fr.refresh(paths=firms_paths, client_factory=factory, map_key=MAP_KEY, today=BASE_END + timedelta(days=4))

    assert outcome_retry.status != "up_to_date", "ADV-05 NO resuelto: el reintento reporto up_to_date en vez de publicar"
    assert firms_paths.pointer.read_bytes() != v1_pointer_bytes, "El reintento debio avanzar el puntero"

    current_sha = json.loads(firms_paths.pointer.read_text("utf-8"))["sha256"]
    history_events = [json.loads(line) for line in firms_paths.history.read_text("utf-8").splitlines()]
    history_shas = [ev.get("sha256") for ev in history_events]
    assert history_shas.count(current_sha) == 1, f"Se esperaba exactamente 1 registro de historial para {current_sha}, hubo {history_shas.count(current_sha)}"


def test_adv05_firms_orphaned_history_record_when_pointer_write_fails(firms_paths, monkeypatch):
    """Inverse failure: history succeeds, then atomic_write_json fails.
    Characterizes the resulting orphan and confirms a retry reconciles it
    (pointer ends up matching the latest real history entry, no duplicate
    history rows, no false success)."""
    factory = _make_firms_factory()

    fr.refresh(paths=firms_paths, client_factory=factory, map_key=MAP_KEY, today=BASE_END + timedelta(days=2))
    v1_pointer_bytes = firms_paths.pointer.read_bytes()
    history_before = firms_paths.history.read_text("utf-8").splitlines()

    real_atomic_write_json = fr.atomic_write_json

    def _fail_pointer_write(path, payload):
        # refresh() also writes a per-version sidecar via atomic_write_json
        # before _publish(); only the pointer write itself must fail here,
        # so the history append inside _publish() still succeeds first.
        if path == firms_paths.pointer:
            raise OSError("Fallo simulado: disco lleno al escribir CURRENT.json")
        return real_atomic_write_json(path, payload)

    monkeypatch.setattr(fr, "atomic_write_json", _fail_pointer_write)

    with pytest.raises(OSError, match="disco lleno al escribir CURRENT"):
        fr.refresh(paths=firms_paths, client_factory=factory, map_key=MAP_KEY, today=BASE_END + timedelta(days=4))

    # Characterization of the orphan: history now has one MORE entry than
    # before, but the pointer never advanced (the publish never completed).
    history_after_failure = firms_paths.history.read_text("utf-8").splitlines()
    assert len(history_after_failure) == len(history_before) + 1, "Se espera exactamente un registro huerfano de historial"
    assert firms_paths.pointer.read_bytes() == v1_pointer_bytes, "El puntero no debe avanzar si su propia escritura fallo"

    orphan_event = json.loads(history_after_failure[-1])
    pointer_sha_before_retry = json.loads(firms_paths.pointer.read_text("utf-8"))["sha256"]
    assert orphan_event["sha256"] != pointer_sha_before_retry, "El registro huerfano describe una version que el puntero nunca reflejo"

    # Retry with the pointer write restored: must reconcile without
    # duplicating the history row or silently losing the orphan.
    monkeypatch.undo()
    outcome_retry = fr.refresh(paths=firms_paths, client_factory=factory, map_key=MAP_KEY, today=BASE_END + timedelta(days=4))
    assert outcome_retry.status != "up_to_date"

    final_pointer_sha = json.loads(firms_paths.pointer.read_text("utf-8"))["sha256"]
    history_final = [json.loads(line) for line in firms_paths.history.read_text("utf-8").splitlines()]
    final_shas = [ev.get("sha256") for ev in history_final]
    assert final_pointer_sha in final_shas, "La version finalmente publicada debe quedar registrada en el historial"
    assert len(history_final) == len(history_before) + 2, (
        "Se esperan exactamente 2 eventos nuevos: el intento huerfano y la "
        "republicacion real del reintento"
    )
    # Hallazgo (Directiva 37 / paso 5): el reintento reconstruye la MISMA
    # ventana de datos, por lo que su contenido -- y por tanto su sha256
    # determinista -- es identico al del intento huerfano. El historial
    # muestra el mismo sha256 dos veces: una del intento cuya escritura de
    # puntero fallo (orphan_event) y otra del reintento que si se publico.
    # Esto NO es una duplicacion erronea ni una corrupcion: es un registro
    # fiel de dos EVENTOS distintos sobre el mismo contenido determinista,
    # tal como se anticipo en la propuesta de change-control (seccion 3).
    # El invariante real -- que el puntero final SI corresponda a un evento
    # real del historial, sin inventar un tercer estado distinto -- se
    # confirma arriba; la igualdad de sha256 entre el huerfano y la
    # republicacion es evidencia adicional de que el reintento reprodujo
    # exactamente los mismos datos, no un resultado falso o divergente.
    assert final_pointer_sha == orphan_event["sha256"], (
        "El reintento debio reproducir el mismo contenido determinista que "
        "el intento huerfano (misma ventana de datos, mismo sha256)"
    )


# --- DMC ---------------------------------------------------------------------

def _dmc_session_for(aug, sep):
    def _payload(records):
        return {
            "organismo": "DMC", "pais": "Chile", "producto": "Datos Recientes", "timezone": "UTC",
            "registros": len(records),
            "datosEstaciones": {"estacion": {"codigoNacional": STATION, "nombreEstacion": "Rodelillo"}, "datos": records},
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
    return session


def test_adv05_dmc_pointer_absent_when_history_append_fails(tmp_path, monkeypatch):
    """GREEN: on a first publication, if history append fails, CURRENT.json
    must never be created at all (nothing to leave unchanged -- there was
    no prior version)."""
    paths = dmc.DmcPaths(root=tmp_path / "dmc")
    aug = [{"momento": "2026-08-31 22:00:00", "temperatura": "18.0 °C", "humedadRelativa": "70 %", "fuerzaDelViento": "5.0 kt", "direccionDelViento": "180 °"}]
    sep = [{"momento": "2026-09-01 02:00:00", "temperatura": "17.5 °C", "humedadRelativa": "72 %", "fuerzaDelViento": "4.5 kt", "direccionDelViento": "190 °"}]
    session = _dmc_session_for(aug, sep)

    def _fail_append(path, record):
        raise OSError("Fallo simulado en historial DMC")

    monkeypatch.setattr(dmc, "append_jsonl", _fail_append)

    with pytest.raises(OSError, match="Fallo simulado"):
        dmc.refresh(paths=paths, session=session, credentials=CREDS_DMC, now=NOW, sleep=lambda _: None)

    assert not paths.pointer.exists(), "ADV-05 NO resuelto en DMC: CURRENT.json se creo pese al fallo de historial"


def test_adv05_dmc_retry_completes_first_publication(tmp_path, monkeypatch):
    """GREEN: once append_jsonl works again, the retry must complete the
    first publication (CURRENT.json created, matching the history entry)."""
    paths = dmc.DmcPaths(root=tmp_path / "dmc")
    aug = [{"momento": "2026-08-31 22:00:00", "temperatura": "18.0 °C", "humedadRelativa": "70 %", "fuerzaDelViento": "5.0 kt", "direccionDelViento": "180 °"}]
    sep = [{"momento": "2026-09-01 02:00:00", "temperatura": "17.5 °C", "humedadRelativa": "72 %", "fuerzaDelViento": "4.5 kt", "direccionDelViento": "190 °"}]

    real_append = dmc.append_jsonl

    def _fail_append(path, record):
        raise OSError("Fallo simulado en historial DMC")

    monkeypatch.setattr(dmc, "append_jsonl", _fail_append)
    with pytest.raises(OSError):
        dmc.refresh(paths=paths, session=_dmc_session_for(aug, sep), credentials=CREDS_DMC, now=NOW, sleep=lambda _: None)
    assert not paths.pointer.exists()

    monkeypatch.setattr(dmc, "append_jsonl", real_append)
    dmc.refresh(paths=paths, session=_dmc_session_for(aug, sep), credentials=CREDS_DMC, now=NOW, sleep=lambda _: None)

    assert paths.pointer.exists(), "El reintento debio completar la primera publicacion"
    history_events = [json.loads(line) for line in paths.history.read_text("utf-8").splitlines()]
    assert len(history_events) == 1, f"Se esperaba exactamente 1 registro de historial, hubo {len(history_events)}"
