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
- ``3``: el ranking no está disponible (red, tiempo agotado, HTTP distinto
  de 200 y de 500, o cuerpo que no cumple el contrato).
- ``4``: el backend respondió HTTP 500. Spring usa ese código cuando la
  persistencia write-through falla y también cuando el servicio de ranking
  responde 500; el cuerpo HTTP no los separa.
- ``1``: fallo interno de este proceso, sin traza hacia el operador.

``scientific_model_validation`` debe permanecer en false. El score es un
ranking relativo.
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

from app.utils.backend_client import BackendError, BackendRankingClient  # noqa: E402

EXIT_OK = 0
EXIT_INTERNAL = 1
EXIT_CURRENT_MISSING = 2
EXIT_RANKING_UNAVAILABLE = 3
EXIT_PERSISTENCE_UNAVAILABLE = 4

# Única estación regional ya usada por el Modelo D.
DMC_STATION_ID = "330007"

_RANKING_UNAVAILABLE = "El ranking no está disponible. Este proceso no escribió en la base."
_PERSISTENCE_UNAVAILABLE = (
    "El backend respondió HTTP 500. Puede ser la persistencia o un fallo "
    "interno del ranking. Este proceso no escribió en la base."
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
    """
    if exc.http_status == 500:
        return DailyRunOutcome(EXIT_PERSISTENCE_UNAVAILABLE, _PERSISTENCE_UNAVAILABLE)
    return DailyRunOutcome(EXIT_RANKING_UNAVAILABLE, _RANKING_UNAVAILABLE)


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

    if view.scientific_model_validation is not False:
        return DailyRunOutcome(EXIT_RANKING_UNAVAILABLE, _RANKING_UNAVAILABLE)

    forecast_time = view.forecast_time.isoformat()
    natural_key = (forecast_time, view.model_version, view.inputs_fingerprint)
    message = (
        "Ranking relativo aceptado. "
        f"forecast_time={forecast_time} "
        f"model_version={view.model_version} "
        f"inputs_fingerprint={view.inputs_fingerprint} "
        "scientific_model_validation=false "
        f"celdas={len(view.cells)}. "
        "La persistencia queda en el backend."
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
