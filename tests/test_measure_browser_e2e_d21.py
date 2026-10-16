"""Pruebas discriminantes RED/GREEN para scripts/measure_browser_e2e_d21.py
(Directiva 28 / Defecto A: falso positivo de actualización en CA4).

Hallazgo cubierto:
El extractor original aceptaba marcas temporales de precisión distinta
(p. ej. 'Obtenido del backend: 15:53 UTC' vs 'obtenido 2026-10-15 15:53:16 UTC')
como evidencia de actualización, por comparación textual superficial, aunque
ambas pudieran representar la misma obtención real.

Metodología obligatoria por hallazgo:
1. Crear prueba que reproduzca el fallo existente (RED).
2. Implementar la corrección.
3. Demostrar que la misma prueba pasa (GREEN).
"""

from __future__ import annotations

import time
import unittest

from scripts.measure_browser_e2e_d21 import (
    is_confirmed_update,
    parse_backend_timestamp,
    wait_for_ranking_update_cycle,
)


class TestParseBackendTimestamp(unittest.TestCase):
    def test_detail_pattern_has_second_precision(self):
        content = "... info técnica (obtenido 2026-10-15 15:53:16 UTC; stack v2) ..."
        ts = parse_backend_timestamp(content)
        self.assertIsNotNone(ts)
        self.assertEqual(ts.precision, "second")
        self.assertEqual((ts.date, ts.hour, ts.minute, ts.second), ("2026-10-15", 15, 53, 16))

    def test_header_pattern_has_minute_precision_and_no_date(self):
        content = "Obtenido del backend: 15:53 UTC"
        ts = parse_backend_timestamp(content)
        self.assertIsNotNone(ts)
        self.assertEqual(ts.precision, "minute")
        self.assertIsNone(ts.date)
        self.assertIsNone(ts.second)

    def test_no_match_returns_none(self):
        self.assertIsNone(parse_backend_timestamp("no hay ninguna marca temporal aqui"))


class TestIsConfirmedUpdateCA4Directiva28(unittest.TestCase):
    """Matriz RED/GREEN obligatoria de la Directiva 28 / Defecto A."""

    def test_case1_same_event_different_timestamp_format_is_rejected(self):
        """Caso 1: mismo evento, diferente formato de timestamp -> debe rechazarse."""
        pre = parse_backend_timestamp("Obtenido del backend: 15:53 UTC")
        post = parse_backend_timestamp("obtenido 2026-10-15 15:53:16 UTC")
        self.assertFalse(is_confirmed_update(pre, post))
        # Y el caso inverso también debe rechazarse.
        self.assertFalse(is_confirmed_update(post, pre))

    def test_case2_dom_without_changes_is_rejected(self):
        """Caso 2: DOM sin cambios -> debe rechazarse."""
        pre = parse_backend_timestamp("obtenido 2026-10-15 15:53:16 UTC")
        post = parse_backend_timestamp("obtenido 2026-10-15 15:53:16 UTC")
        self.assertFalse(is_confirmed_update(pre, post))

    def test_case3_truncated_or_ambiguous_timestamp_never_passes(self):
        """Caso 3: timestamp truncado o ambiguo (no extraído) -> nunca produce PASS."""
        pre = parse_backend_timestamp("obtenido 2026-10-15 15:53:16 UTC")
        self.assertFalse(is_confirmed_update(pre, None))
        self.assertFalse(is_confirmed_update(None, pre))
        self.assertFalse(is_confirmed_update(None, None))

    def test_case4_real_update_after_click_is_accepted(self):
        """Caso 4: actualización real posterior al clic (mismo origen/precisión,
        segundo distinto) -> debe aceptarse."""
        pre = parse_backend_timestamp("obtenido 2026-10-15 15:53:16 UTC")
        post = parse_backend_timestamp("obtenido 2026-10-15 15:53:47 UTC")
        self.assertTrue(is_confirmed_update(pre, post))

    def test_minute_precision_change_of_minute_is_comparable_and_accepted(self):
        """Dos timestamps del MISMO origen (ambos minuto) con minuto distinto sí
        constituyen evidencia válida; solo el cruce de precisiones se rechaza."""
        pre = parse_backend_timestamp("Obtenido del backend: 15:53 UTC")
        post = parse_backend_timestamp("Obtenido del backend: 15:54 UTC")
        self.assertTrue(is_confirmed_update(pre, post))

    def test_different_date_with_same_hms_is_accepted(self):
        pre = parse_backend_timestamp("obtenido 2026-10-15 15:53:16 UTC")
        post = parse_backend_timestamp("obtenido 2026-10-16 15:53:16 UTC")
        self.assertTrue(is_confirmed_update(pre, post))


class _ScriptedDriver:
    """Mock mínimo de WebDriver: por cada iteración del ciclo de espera se invoca
    primero el script de 'is_running' y luego el de 'textContent' (mismo índice de
    paso); al completar ambos, el paso avanza para la siguiente iteración."""

    def __init__(self, texts: list[str], running_flags: list[bool] | None = None):
        self._texts = texts
        self._running_flags = running_flags or [False] * len(texts)
        self._step = 0

    def execute_script(self, script):
        if "textContent" in script:
            idx = min(self._step, len(self._texts) - 1)
            text = self._texts[idx]
            if self._step < len(self._texts) - 1:
                self._step += 1
            return text
        idx = min(self._step, len(self._running_flags) - 1)
        return self._running_flags[max(idx, 0)]


class TestWaitForRankingUpdateCycleCA4Directiva28(unittest.TestCase):
    def test_case5_timeout_produces_fail_on_stale_dom(self):
        """Caso 5: timeout sin ninguna señal comparable -> debe fallar (TimeoutError)."""
        driver = _ScriptedDriver(["obtenido 2026-10-15 15:53:16 UTC"])
        pre = parse_backend_timestamp("obtenido 2026-10-15 15:53:16 UTC")
        t_start = time.perf_counter()
        with self.assertRaises(TimeoutError):
            wait_for_ranking_update_cycle(driver, pre, t_start, timeout=0.3)

    def test_timeout_when_only_precision_format_changes(self):
        """RED (regresión directa del falso positivo original): el DOM pasa de
        formato minuto a formato segundos, pero jamás se confirma como
        actualización real -> debe fallar por timeout, nunca PASS."""
        driver = _ScriptedDriver(["obtenido 2026-10-15 15:53:16 UTC"])
        pre = parse_backend_timestamp("Obtenido del backend: 15:53 UTC")
        t_start = time.perf_counter()
        with self.assertRaises(TimeoutError):
            wait_for_ranking_update_cycle(driver, pre, t_start, timeout=0.3)

    def test_real_update_detected_before_timeout_demonstrates_pass(self):
        """Caso 4 (end-to-end): una actualización real y comparable se confirma
        antes de que expire el timeout."""
        texts = (
            ["obtenido 2026-10-15 15:53:16 UTC"] * 3
            + ["obtenido 2026-10-15 15:53:47 UTC"] * 5
        )
        driver = _ScriptedDriver(texts)
        pre = parse_backend_timestamp("obtenido 2026-10-15 15:53:16 UTC")
        t_start = time.perf_counter()
        latency_ms, post_raw, detail = wait_for_ranking_update_cycle(driver, pre, t_start, timeout=5.0)
        self.assertIn("15:53:47", post_raw)
        self.assertGreaterEqual(latency_ms, 0.0)
        self.assertIn("Actualización confirmada", detail)

    def test_update_withheld_while_spinner_running(self):
        """Una nueva marca comparable que aparece mientras el spinner sigue activo
        no debe confirmarse hasta que el widget deje de reportar 'Running'."""
        texts = ["obtenido 2026-10-15 15:53:16 UTC"] + ["obtenido 2026-10-15 15:53:47 UTC"] * 6
        running_flags = [True, True, True, False, False, False, False]
        driver = _ScriptedDriver(texts, running_flags=running_flags)
        pre = parse_backend_timestamp("obtenido 2026-10-15 15:53:16 UTC")
        t_start = time.perf_counter()
        latency_ms, post_raw, _ = wait_for_ranking_update_cycle(driver, pre, t_start, timeout=5.0)
        self.assertIn("15:53:47", post_raw)


if __name__ == "__main__":
    unittest.main()
