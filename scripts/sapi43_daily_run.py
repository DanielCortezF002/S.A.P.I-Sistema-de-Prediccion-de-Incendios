"""Entrypoint diario preparatorio de SAPI-43.

Comprueba que los punteros CURRENT ya definidos existan y se puedan leer
como objeto JSON, y después pide ``GET /api/v1/ranking`` al backend Spring.
El score y la escritura idempotente siguen en el servicio ML y en el
write-through de Spring. Este proceso no puntúa, no refresca y no abre
otra persistencia.

Punteros ya definidos (sin validar campos de SAPI-71):

- ``data/processed/firms/CURRENT.json``
- ``data/processed/dmc/330007/CURRENT.json``

Códigos de salida:

- ``0``: ranking aceptado. Una repetición con la misma clave natural también
  sale ``0``: el backend responde 200 y su clave única no inserta otra
  ejecución. Este proceso no consulta la base para distinguir el alta de
  la repetición.
- ``2``: algún puntero CURRENT falta o no se puede leer. No hay petición HTTP.
- ``3``: el ranking no está disponible, el cuerpo no cumple el contrato,
  ``firms_origin`` no es ``current``, o falta la metadata FIRMS ya definida
  en el contrato.
- ``4``: el backend respondió HTTP 500. Es una clasificación controlada:
  ese código no prueba un fallo de la base. Spring lo usa también cuando
  el servicio de ranking responde 500.
- ``1``: fallo interno de este proceso, sin traza hacia el operador.

``scientific_model_validation`` debe permanecer en false. El score es un
ranking relativo. ``firms_origin=current`` es obligatorio en este flujo.
Un origen ``reproducibility`` o ``baseline`` es un snapshot histórico y
no se acepta.

El puntero DMC legible no demuestra que el almacén versionado se haya
consumido. El contrato público no trae un origen DMC. ``station_id``, si
llega, solo nombra la estación regional. Esa evidencia queda para SAPI-71.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from app.utils.backend_client import (  # noqa: E402
    BackendError,
    BackendRankingClient,
    RankingView,
)

EXIT_OK = 0
EXIT_INTERNAL = 1
EXIT_CURRENT_MISSING = 2
EXIT_RANKING_UNAVAILABLE = 3
# HTTP 500 del backend. No afirma que PostGIS haya fallado.
EXIT_BACKEND_INTERNAL = 4

FIRMS_ORIGIN_CURRENT = "current"
HISTORICAL_FIRMS_ORIGINS = frozenset({"baseline", "reproducibility"})
# Valores ya publicados en el contrato. No se agregan campos.
FIRMS_STATUS_VALUES = frozenset({"FIRMS AL DÍA", "FIRMS DESACTUALIZADO"})
# El puntero DMC no es evidencia de que el store versionado se haya leído.
DMC_STORE_CONSUMPTION_PROVEN = False

# Única estación regional ya usada por el Modelo D.
DMC_STATION_ID = "330007"

_RANKING_UNAVAILABLE = "El ranking no está disponible. Este proceso no escribió en la base."
_HISTORICAL_ORIGIN = (
    "El ranking no trae firms_origin=current. "
    "Un snapshot histórico no cuenta como corrida diaria. "
    "Este proceso no escribió en la base."
)
_METADATA_INCOMPLETE = (
    "Falta metadata FIRMS del contrato (cobertura, desfase o estado). "
    "Este proceso no escribió en la base."
)
_BACKEND_INTERNAL = (
    "El backend respondió HTTP 500 (error interno). "
    "Ese código no identifica un fallo de la base. "
    "Este proceso no escribió en la base."
)
_INTERNAL = "Fallo interno del entrypoint diario."


@dataclass(frozen=True)
class DailyRunOutcome:
    """Resultado controlado de una corrida preparatoria.

    Attributes:
        code: Código de salida del proceso.
        message: Texto para el operador, sin traza ni cuerpo remoto.
        natural_key: ``(forecast_time, model_version, inputs_fingerprint)``
            cuando el ranking fue aceptado. ``None`` en cualquier otro caso.
    """

    code: int
    message: str
    natural_key: Optional[tuple[str, str, str]] = None


def firms_pointer_path(repo_root: Path) -> Path:
    """Ruta del puntero FIRMS ya definido.

    Args:
        repo_root: Raíz del checkout.

    Returns:
        Ruta de ``data/processed/firms/CURRENT.json``.
    """
    return repo_root / "data" / "processed" / "firms" / "CURRENT.json"


def dmc_pointer_path(repo_root: Path, station_id: str = DMC_STATION_ID) -> Path:
    """Ruta del puntero DMC ya definido para la estación del Modelo D.

    Args:
        repo_root: Raíz del checkout.
        station_id: Código de estación. Por defecto ``330007``.

    Returns:
        Ruta de ``data/processed/dmc/<estación>/CURRENT.json``.
    """
    return repo_root / "data" / "processed" / "dmc" / station_id / "CURRENT.json"


def _pointer_problem(path: Path) -> Optional[str]:
    """Dice si un puntero falta o no se puede leer como objeto JSON.

    No revisa claves, hashes, sidecars ni versiones. Eso pertenece a SAPI-71.

    Args:
        path: Ruta del ``CURRENT.json``.

    Returns:
        ``ausente``, ``ilegible``, o ``None`` si hay un objeto JSON.
    """
    if not path.is_file():
        return "ausente"
    try:
        raw = path.read_bytes()
    except OSError:
        return "ilegible"
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return "ilegible"
    if not isinstance(payload, dict):
        return "ilegible"
    return None


def _precondition_message(problems: list[str]) -> str:
    """Arma el mensaje de precondición sin pedir el ranking.

    Args:
        problems: Fragmentos ``rol estado`` de cada puntero fallido.

    Returns:
        Texto de una línea para stderr.
    """
    detail = "; ".join(problems)
    return (
        f"Puntero CURRENT ausente o ilegible ({detail}). "
        "No se consultó el ranking y este proceso no escribió en la base."
    )


def _from_backend_error(exc: BackendError) -> DailyRunOutcome:
    """Traduce un fallo del cliente de ranking a un código de salida.

    Args:
        exc: Error ya clasificado por el cliente HTTP existente.

    Returns:
        Salida 4 si el backend respondió 500; salida 3 en el resto.
        La salida 4 no afirma que la base haya fallado.
    """
    if exc.http_status == 500:
        return DailyRunOutcome(EXIT_BACKEND_INTERNAL, _BACKEND_INTERNAL)
    return DailyRunOutcome(EXIT_RANKING_UNAVAILABLE, _RANKING_UNAVAILABLE)


def _reject_provenance(view: RankingView) -> Optional[DailyRunOutcome]:
    """Rechaza un ranking que no es una corrida con FIRMS current.

    Usa solo campos que el contrato ya define. No revisa hashes ni sidecars.

    Args:
        view: Ranking ya validado por el cliente HTTP.

    Returns:
        Un rechazo, o ``None`` si ``firms_origin`` es ``current`` y la
        metadata FIRMS del contrato está presente.
    """
    if view.scientific_model_validation is not False:
        return DailyRunOutcome(EXIT_RANKING_UNAVAILABLE, _RANKING_UNAVAILABLE)
    origin = view.firms_origin
    if origin in HISTORICAL_FIRMS_ORIGINS or origin != FIRMS_ORIGIN_CURRENT:
        return DailyRunOutcome(EXIT_RANKING_UNAVAILABLE, _HISTORICAL_ORIGIN)
    metadata_ok = (
        view.firms_coverage_end is not None
        and view.firms_lag_days is not None
        and view.firms_status in FIRMS_STATUS_VALUES
    )
    if not metadata_ok:
        return DailyRunOutcome(EXIT_RANKING_UNAVAILABLE, _METADATA_INCOMPLETE)
    return None


def execute(
    repo_root: Path,
    *,
    client: Optional[BackendRankingClient] = None,
) -> DailyRunOutcome:
    """Corre las precondiciones y, si pasan, un GET del ranking.

    Args:
        repo_root: Raíz del checkout. Los punteros se leen bajo esta raíz
            y no se crean si faltan.
        client: Cliente ya construido. Si es ``None``, se usa
            ``SAPI_BACKEND_BASE_URL`` y los timeouts explícitos del entorno.

    Returns:
        Resultado con código, mensaje y, si hubo ranking, la clave natural.
    """
    checks = (
        ("FIRMS", firms_pointer_path(repo_root)),
        ("DMC", dmc_pointer_path(repo_root)),
    )
    problems = [
        f"{role} {problem}"
        for role, path in checks
        if (problem := _pointer_problem(path)) is not None
    ]
    if problems:
        return DailyRunOutcome(EXIT_CURRENT_MISSING, _precondition_message(problems))

    ranking_client = client if client is not None else BackendRankingClient.from_env()
    try:
        view = ranking_client.fetch_ranking()
    except BackendError as exc:
        return _from_backend_error(exc)

    rejected = _reject_provenance(view)
    if rejected is not None:
        return rejected

    forecast_time = view.forecast_time.isoformat()
    natural_key = (forecast_time, view.model_version, view.inputs_fingerprint)
    message = (
        "Ranking relativo aceptado. "
        f"forecast_time={forecast_time} "
        f"model_version={view.model_version} "
        f"inputs_fingerprint={view.inputs_fingerprint} "
        "scientific_model_validation=false "
        "firms_origin=current "
        f"celdas={len(view.cells)}. "
        "La persistencia queda en el backend. "
        "El puntero DMC legible no demuestra que su almacén versionado se haya usado."
    )
    return DailyRunOutcome(EXIT_OK, message, natural_key)


def main(argv: Optional[list[str]] = None) -> int:
    """Punto de entrada de consola.

    No admite modos alternativos: ``argv`` se ignora a propósito.

    Args:
        argv: Argumentos sin usar.

    Returns:
        Código de salida de :func:`execute`, o ``1`` si el proceso falla.
    """
    del argv
    try:
        outcome = execute(_REPO_ROOT)
    except Exception:
        print(_INTERNAL, file=sys.stderr)
        return EXIT_INTERNAL
    stream = sys.stdout if outcome.code == EXIT_OK else sys.stderr
    print(outcome.message, file=stream)
    return outcome.code


if __name__ == "__main__":
    sys.exit(main())
