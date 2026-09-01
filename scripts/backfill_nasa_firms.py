"""CLI seguro para el backfill histórico NASA FIRMS."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.ingesta.nasa_firms_backfill import (  # noqa: E402
    NasaFirmsBackfill,
    build_windows,
    five_year_start,
    select_boundary_sample,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill VIIRS S-NPP SP/NRT en ventanas FIRMS de hasta 5 días."
    )
    parser.add_argument("--start-date", type=date.fromisoformat)
    parser.add_argument("--end-date", type=date.fromisoformat, default=date.today())
    parser.add_argument(
        "--sample-boundary-windows",
        type=int,
        metavar="N",
        help="Ejecuta solo N ventanas alrededor del límite SP/NRT.",
    )
    parser.add_argument(
        "--confirm-full-run",
        action="store_true",
        help="Confirmación obligatoria para ejecutar todas las ventanas.",
    )
    parser.add_argument(
        "--delay-seconds",
        type=float,
        default=0.25,
        help="Pausa entre solicitudes (default: 0.25).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    end_date = args.end_date
    start_date = args.start_date or five_year_start(end_date)
    if end_date < start_date:
        raise SystemExit("--end-date no puede ser anterior a --start-date")

    if args.sample_boundary_windows is None and not args.confirm_full_run:
        raise SystemExit(
            "Ejecución completa bloqueada: use --sample-boundary-windows 4 para "
            "probar o --confirm-full-run después de validar."
        )

    client = NasaFirmsBackfill(request_delay_seconds=args.delay_seconds)
    availability = client.fetch_availability()
    windows = build_windows(start_date, end_date, availability)

    if args.sample_boundary_windows is not None:
        windows = select_boundary_sample(windows, args.sample_boundary_windows)

    print(
        json.dumps(
            {
                "period": [start_date.isoformat(), end_date.isoformat()],
                "availability": {
                    source: [
                        available.min_date.isoformat(),
                        available.max_date.isoformat(),
                    ]
                    for source, available in availability.items()
                },
                "selected_windows": [
                    {
                        "source": window.source,
                        "start": window.start_date.isoformat(),
                        "end": window.end_date.isoformat(),
                        "day_range": window.day_range,
                    }
                    for window in windows
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    result = client.run(windows)
    print(
        json.dumps(
            {
                "requested_windows": result.requested_windows,
                "raw_records": result.raw_records,
                "unique_records": result.unique_records,
                "duplicates_removed": result.duplicates_removed,
                "consolidated_path": str(result.consolidated_path),
                "manifest_path": str(result.manifest_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
