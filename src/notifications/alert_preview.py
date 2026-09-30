"""CLI local de vista previa de alertas SAPI. Lee un archivo; NUNCA envía nada.

    python -m src.notifications.alert_preview --input score.json --top 5 --format text

Entrada: el JSON de `/score` del bridge (éxito o error), o la evidencia de
`tools/ops/capture_score.py` (`{"score": {...}}`). Sin HTTP, sin Telegram, sin n8n.

Exit: 0 READY · 1 INVALID · 2 uso inválido · 3 UNAVAILABLE.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.notifications.alert_payload import (
    DEFAULT_TOP_N,
    MAX_TOP_N,
    STATUS_INVALID,
    STATUS_READY,
    STATUS_UNAVAILABLE,
    build_alert,
    render_telegram_preview,
    render_text,
)

EXIT_BY_STATUS = {STATUS_READY: 0, STATUS_INVALID: 1, STATUS_UNAVAILABLE: 3}
EXIT_USAGE = 2


def _load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None  # build_alert(None) → INVALID input_not_object


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m src.notifications.alert_preview",
        description="Vista previa local de alertas SAPI (nunca envía).",
    )
    parser.add_argument(
        "--input", required=True, help="Archivo JSON con el resultado de scoring"
    )
    parser.add_argument(
        "--top",
        type=int,
        default=DEFAULT_TOP_N,
        help=f"1..{MAX_TOP_N} (solo presentación)",
    )
    parser.add_argument(
        "--format", choices=["json", "text", "telegram-preview"], default="text"
    )
    parser.add_argument(
        "--generated-at",
        help="Marca de generación (fuera de la identidad de la alerta); "
        "por defecto, ahora en UTC",
    )
    args = parser.parse_args(argv)
    if not 1 <= args.top <= MAX_TOP_N:
        parser.error(f"--top debe estar entre 1 y {MAX_TOP_N}")

    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(encoding="utf-8", errors="replace")

    generated_at = args.generated_at or datetime.now(timezone.utc).isoformat()
    alert = build_alert(
        _load(Path(args.input)), top_n=args.top, generated_at=generated_at
    )
    if args.format == "json":
        print(json.dumps(alert, ensure_ascii=False, indent=2, sort_keys=True))
    elif args.format == "text":
        print(render_text(alert))
    else:
        print(
            json.dumps(
                render_telegram_preview(alert),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
    return EXIT_BY_STATUS[alert["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
