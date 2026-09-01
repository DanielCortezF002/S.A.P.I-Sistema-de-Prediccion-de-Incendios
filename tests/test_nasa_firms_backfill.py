"""Pruebas del backfill histórico NASA FIRMS."""

from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

import pandas as pd

from scripts.backfill_nasa_firms import main
from src.ingesta.nasa_firms_backfill import (
    NRT_SOURCE,
    SP_SOURCE,
    Availability,
    DateWindow,
    NasaFirmsBackfill,
    build_windows,
    deduplicate_detections,
    split_windows,
)


class NasaFirmsBackfillTests(unittest.TestCase):
    def test_split_windows_uses_at_most_five_days(self) -> None:
        windows = split_windows(
            SP_SOURCE,
            date(2021, 8, 30),
            date(2021, 9, 10),
        )

        self.assertEqual([window.day_range for window in windows], [5, 5, 2])
        self.assertEqual(windows[0].start_date, date(2021, 8, 30))
        self.assertEqual(windows[-1].end_date, date(2021, 9, 10))

    def test_build_windows_preserves_sp_nrt_overlap(self) -> None:
        availability = {
            SP_SOURCE: Availability(
                SP_SOURCE,
                date(2012, 1, 20),
                date(2026, 6, 5),
            ),
            NRT_SOURCE: Availability(
                NRT_SOURCE,
                date(2026, 6, 1),
                date(2026, 8, 30),
            ),
        }

        windows = build_windows(
            date(2026, 5, 30),
            date(2026, 6, 10),
            availability,
        )

        sources_for_overlap = {
            window.source
            for window in windows
            if window.start_date <= date(2026, 6, 3) <= window.end_date
        }
        self.assertEqual(sources_for_overlap, {SP_SOURCE, NRT_SOURCE})

    def test_deduplication_prefers_standard_processing(self) -> None:
        common = {
            "latitude": -33.1,
            "longitude": -71.2,
            "acq_date": "2026-06-03",
            "acq_time": 945,
            "satellite": "N",
            "instrument": "VIIRS",
        }
        data = pd.DataFrame(
            [
                {**common, "firms_source": NRT_SOURCE, "version": "2.0NRT"},
                {**common, "firms_source": SP_SOURCE, "version": "2.0SP"},
                {
                    **common,
                    "longitude": -71.3,
                    "firms_source": NRT_SOURCE,
                    "version": "2.0NRT",
                },
            ]
        )

        result, removed = deduplicate_detections(data)

        self.assertEqual(removed, 1)
        self.assertEqual(len(result), 2)
        overlapping = result[result["longitude"] == -71.2].iloc[0]
        self.assertEqual(overlapping["firms_source"], SP_SOURCE)

    def test_url_contains_source_five_day_range_and_start_date(self) -> None:
        client = NasaFirmsBackfill(map_key="test-key")
        window = DateWindow(
            SP_SOURCE,
            date(2021, 8, 30),
            date(2021, 9, 3),
        )

        url = client.window_url(window)

        self.assertIn("/VIIRS_SNPP_SP/", url)
        self.assertTrue(url.endswith("/5/2021-08-30"))
        self.assertNotIn("test-key", url.replace("/test-key/", "/"))

    def test_full_run_requires_explicit_cli_confirmation(self) -> None:
        with patch("sys.argv", ["backfill_nasa_firms.py"]):
            with patch(
                "scripts.backfill_nasa_firms.NasaFirmsBackfill"
            ) as client_class:
                with self.assertRaisesRegex(SystemExit, "Ejecución completa bloqueada"):
                    main()
                client_class.assert_not_called()


if __name__ == "__main__":
    unittest.main()
