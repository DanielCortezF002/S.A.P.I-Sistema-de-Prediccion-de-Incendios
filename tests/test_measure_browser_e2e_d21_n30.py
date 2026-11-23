"""SAPI-137 (HU-90.T2): pruebas del arnés ampliado a n muestras por escenario.

Ninguna prueba abre un navegador, contacta la app ni ejecuta Docker: los
escenarios se sustituyen por funciones o drivers simulados y
``get_container_identities`` se reemplaza por un doble.
"""

from __future__ import annotations

import csv
import json
import math
import random
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import measure_browser_e2e_d21 as h

REPO_ROOT = Path(__file__).resolve().parents[1]

try:
    import numpy as np
except ImportError:  # pragma: no cover - numpy está en requirements.txt
    np = None


def _args(*extra):
    return h.parse_args(list(extra))


def _outcome(ms, verified=True):
    return h.SampleOutcome(latency_ms=ms, content_verified=verified)


class _ListLog:
    def __init__(self):
        self.lines = []

    def __call__(self, msg):
        self.lines.append(msg)


# --------------------------------------------------------------------- 1) n
class RepetitionsTests(unittest.TestCase):
    def test_schedule_has_n_measured_samples_per_scenario(self):
        plan = h.build_schedule(h.SCENARIOS, repetitions=30, warmup=0, order="blocks")
        self.assertEqual(len(plan), 120)
        for s in h.SCENARIOS:
            its = [p.iteration for p in plan if p.scenario == s]
            self.assertEqual(its, list(range(1, 31)))
        self.assertTrue(all(p.role == h.ROLE_MEASURE for p in plan))

    def test_default_repetitions_is_one_and_documented_as_provisional(self):
        args = _args()
        self.assertEqual(args.repetitions, 1)
        self.assertIn("PROVISIONAL", h.build_parser().description)

    def test_repetitions_below_one_rejected(self):
        for bad in (0, -3):
            with self.assertRaises(ValueError):
                h.build_schedule(["cold"], repetitions=bad, warmup=0, order="blocks")
            self.assertIn("--repetitions debe ser >= 1",
                          h.validate_args(_args("--repetitions", str(bad))))

    def test_cli_exits_with_error_on_invalid_repetitions(self):
        with mock.patch("sys.stderr"), self.assertRaises(SystemExit) as cm:
            h.main(["--repetitions", "0"])
        self.assertEqual(cm.exception.code, 2)

    def test_unknown_empty_or_duplicate_scenarios_rejected(self):
        for scen in ("cold,foo", ",", "cold,cold"):
            self.assertTrue(h.validate_args(_args("--scenarios", scen)), scen)
        with self.assertRaises(ValueError):
            h.build_schedule(["cold", "cold"], 1, 0, "blocks")
        with self.assertRaises(ValueError):
            h.build_schedule([], 1, 0, "blocks")
        with self.assertRaises(ValueError):
            h.build_schedule(["nope"], 1, 0, "blocks")

    def test_n_above_one_requires_explicit_method_and_failure_policy(self):
        errs = h.validate_args(_args("--repetitions", "30"))
        self.assertTrue(any("--percentile-method es obligatorio" in e for e in errs))
        self.assertTrue(any("--failure-policy es obligatorio" in e for e in errs))
        ok = h.validate_args(_args("--repetitions", "30", "--percentile-method", "linear",
                                   "--failure-policy", "ok_only"))
        self.assertEqual(ok, [])

    def test_cli_n30_without_method_exits_before_measuring(self):
        with mock.patch.object(h, "run_measurement") as run, \
                mock.patch("sys.stderr"), self.assertRaises(SystemExit) as cm:
            h.main(["--repetitions", "30"])
        self.assertEqual(cm.exception.code, 2)
        run.assert_not_called()

    def test_percentile_out_of_range_rejected(self):
        for bad in ("0", "-1", "100.5"):
            self.assertTrue(h.validate_args(_args("--percentile", bad)), bad)


# --------------------------------------------------------------- 2) percentil
class PercentileTests(unittest.TestCase):
    def test_nearest_rank_n30_is_29th_value(self):
        vals = list(range(1, 31))
        random.Random(1).shuffle(vals)
        self.assertEqual(h.percentile_nearest_rank(vals, 95), 29)

    def test_nearest_rank_n31_is_30th_value(self):
        self.assertEqual(h.percentile_nearest_rank(list(range(1, 32)), 95), 30)

    def test_nearest_rank_exact_rank_uses_exact_arithmetic(self):
        # 0.95 * 20 = 19 exactamente: debe ser la 19.ª, no la 20.ª
        self.assertEqual(h.percentile_nearest_rank(list(range(1, 21)), 95), 19)
        # En coma flotante 7/100*100 = 7.000000000000001 y ceil daría la 8.ª.
        self.assertEqual(h.percentile_nearest_rank(list(range(1, 101)), 7), 7)

    def test_linear_matches_numpy_default_formula(self):
        vals = list(range(1, 31))
        # h = 29 * 0.95 = 27.55 -> 28 + 0.55 * (29 - 28)
        self.assertAlmostEqual(h.percentile_linear(vals, 95), 28.55)
        self.assertEqual(h.percentile_linear([5.0], 95), 5.0)

    @unittest.skipIf(np is None, "numpy no disponible")
    def test_both_methods_match_numpy_on_random_samples(self):
        rng = random.Random(137)
        for n in (1, 2, 7, 30, 31, 40, 100):
            vals = [rng.uniform(100, 3000) for _ in range(n)]
            for p in (50, 90, 95, 99):
                self.assertAlmostEqual(
                    h.percentile_nearest_rank(vals, p),
                    float(np.percentile(vals, p, method="inverted_cdf")), places=9)
                self.assertAlmostEqual(
                    h.percentile_linear(vals, p),
                    float(np.percentile(vals, p, method="linear")), places=9)

    def test_infinite_failures_propagate(self):
        vals = [100.0] * 28 + [math.inf, math.inf]
        self.assertEqual(h.percentile_nearest_rank(vals, 95), math.inf)
        self.assertEqual(h.percentile_linear(vals, 95), math.inf)
        one_fail = [100.0] * 29 + [math.inf]
        self.assertEqual(h.percentile_nearest_rank(one_fail, 95), 100.0)
        self.assertEqual(h.percentile_linear(one_fail, 95), 100.0)

    def test_invalid_inputs_rejected(self):
        for fn in (h.percentile_nearest_rank, h.percentile_linear):
            with self.assertRaises(ValueError):
                fn([], 95)
            with self.assertRaises(ValueError):
                fn([1.0, math.nan], 95)
            with self.assertRaises(ValueError):
                fn([1.0], 0)
            with self.assertRaises(ValueError):
                fn([1.0], 101)
        with self.assertRaises(ValueError):
            h.compute_percentile([1.0], 95, "numpy_default")

    def test_cli_rejects_unknown_percentile_method(self):
        with mock.patch("sys.stderr"), self.assertRaises(SystemExit):
            _args("--percentile-method", "midpoint")

    def test_summary_reports_both_methods_and_selected_primary(self):
        rows = [self._row("cold", i, float(i)) for i in range(1, 31)]
        summ = h.summarize_rows(rows, 95, "nearest_rank", "as_infinite")
        cold = summ["scenarios"]["cold"]
        self.assertEqual(cold["as_infinite"]["nearest_rank"]["p95"], 29.0)
        self.assertAlmostEqual(cold["as_infinite"]["linear"]["p95"], 28.55)
        self.assertEqual(cold["primary"]["p95"], 29.0)
        self.assertEqual(cold["primary"]["method"], "nearest_rank")
        lin = h.summarize_rows(rows, 95, "linear", "as_infinite")["scenarios"]["cold"]
        self.assertAlmostEqual(lin["primary"]["p95"], 28.55)

    def test_summary_without_primary_when_not_chosen(self):
        rows = [self._row("cold", 1, 10.0)]
        cold = h.summarize_rows(rows, 95, None, None)["scenarios"]["cold"]
        self.assertNotIn("primary", cold)
        with self.assertRaises(ValueError):
            h.summarize_rows(rows, 95, "bogus", "ok_only")
        with self.assertRaises(ValueError):
            h.summarize_rows(rows, 95, "linear", "bogus")

    @staticmethod
    def _row(scenario, it, ms, status="ok", role="measure"):
        return {"scenario": scenario, "role": role, "iteration": it, "status": status,
                "ui_visible_latency_ms": "" if ms is None else repr(ms)}


# ----------------------------------------------------- 3) CSV incremental
class IncrementalCsvTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _read(self, path):
        with open(path, newline="", encoding="utf-8") as fh:
            return list(csv.DictReader(fh))

    def test_each_row_is_on_disk_before_the_next_sample(self):
        path = self.dir / "samples.csv"
        writer = h.IncrementalSampleWriter(path)
        seen = []

        def sample(planned):
            seen.append(len(self._read(path)))  # filas ya en disco al iniciar la muestra
            return _outcome(100.0)

        plan = h.build_schedule(["cold"], 3, 0, "blocks")
        h.execute_schedule(plan, sample, writer, log=_ListLog())
        writer.close()
        self.assertEqual(seen, [0, 1, 2])
        self.assertEqual(len(self._read(path)), 3)

    def test_existing_file_is_never_overwritten(self):
        path = self.dir / "samples.csv"
        path.write_text("previo", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            h.IncrementalSampleWriter(path)
        self.assertEqual(path.read_text(encoding="utf-8"), "previo")

    def test_undeclared_field_rejected(self):
        writer = h.IncrementalSampleWriter(self.dir / "samples.csv")
        with self.assertRaises(ValueError):
            writer.write({"seq": 1, "inventado": "x"})
        writer.close()

    def test_latency_is_stored_unrounded(self):
        writer = h.IncrementalSampleWriter(self.dir / "samples.csv")
        plan = h.build_schedule(["cold"], 1, 0, "blocks")
        h.execute_schedule(plan, lambda p: _outcome(1234.56789), writer, log=_ListLog())
        writer.close()
        self.assertEqual(self._read(self.dir / "samples.csv")[0]["ui_visible_latency_ms"],
                         "1234.56789")

    def test_interruption_keeps_written_rows_and_summary(self):
        calls = {"n": 0}

        def sample(planned):
            calls["n"] += 1
            if calls["n"] == 4:
                raise KeyboardInterrupt("corte simulado")
            return _outcome(100.0 + calls["n"])

        args = _args("--repetitions", "3", "--scenarios", "cold,update",
                     "--percentile-method", "nearest_rank", "--failure-policy", "as_infinite")
        out = self.dir / "run"
        with mock.patch.object(h, "get_container_identities", return_value={}), \
                mock.patch.object(h, "run_negative_test_stale_dom", return_value=True), \
                self.assertRaises(KeyboardInterrupt):
            h.run_measurement(args, out, sample_fn=sample, log=_ListLog())
        rows = self._read(out / "samples.csv")
        self.assertEqual(len(rows), 3)
        summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
        self.assertIn("KeyboardInterrupt", summary["interrupted"])
        self.assertEqual(summary["recorded_samples"], 3)
        self.assertEqual(summary["planned_samples"], 6)
        self.assertEqual(summary["exit_code"], 1)
        self.assertEqual(summary["samples_csv_sha256"], h.sha256_file(out / "samples.csv"))

    def test_full_run_writes_manifest_samples_and_summary(self):
        args = _args("--repetitions", "2", "--scenarios", "cold", "--candidate-sha", "abc",
                     "--percentile-method", "linear", "--failure-policy", "ok_only")
        out = self.dir / "run"
        with mock.patch.object(h, "get_container_identities", return_value={"web-v2": "img"}), \
                mock.patch.object(h, "run_negative_test_stale_dom", return_value=True):
            code = h.run_measurement(args, out, sample_fn=lambda p: _outcome(10.0),
                                     log=_ListLog())
        self.assertEqual(code, 0)
        manifest = json.loads((out / "run_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["config"]["repetitions"], 2)
        self.assertEqual(manifest["config"]["percentile_method"], "linear")
        self.assertFalse(manifest["candidate_matches_head"])
        self.assertEqual(manifest["containers"], {"web-v2": "img"})
        self.assertIn("provisional", manifest["provisional_defaults_note"])
        self.assertEqual(len(self._read(out / "samples.csv")), 2)

    def test_run_refuses_invalid_config_before_touching_disk(self):
        out = self.dir / "run"
        with self.assertRaises(ValueError):
            h.run_measurement(_args("--repetitions", "30"), out, sample_fn=lambda p: None)
        self.assertFalse(out.exists())

    def test_failing_negative_selftest_aborts_before_sampling(self):
        out = self.dir / "run"
        sample = mock.Mock()
        with mock.patch.object(h, "run_negative_test_stale_dom", return_value=False), \
                self.assertRaises(RuntimeError):
            h.run_measurement(_args(), out, sample_fn=sample)
        sample.assert_not_called()


# ------------------------------------------------ 4) fallos y timeouts
class FailureRowsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "samples.csv"

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self, outcomes, scenarios=("cold",), on_failure=None):
        it = iter(outcomes)

        def sample(planned):
            item = next(it)
            if isinstance(item, BaseException):
                raise item
            return item

        reps = len(outcomes) // len(scenarios)
        plan = h.build_schedule(scenarios, reps, 0, "blocks")
        writer = h.IncrementalSampleWriter(self.path)
        rows = h.execute_schedule(plan, sample, writer, on_failure=on_failure, log=_ListLog())
        writer.close()
        return rows

    def test_timeout_error_and_unverified_are_rows_not_drops(self):
        failures = []
        rows = self._run(
            [_outcome(100.0), TimeoutError("sin ranking"), RuntimeError("sin botón"),
             _outcome(150.0, verified=False), _outcome(120.0)],
            on_failure=lambda p, ex: failures.append((p.iteration, type(ex).__name__)),
        )
        self.assertEqual([r["status"] for r in rows],
                         ["ok", "timeout", "error", "content_unverified", "ok"])
        self.assertEqual(rows[1]["error_type"], "TimeoutError")
        self.assertIn("sin botón", rows[2]["error_message"])
        self.assertEqual(rows[1]["ui_visible_latency_ms"], "")
        self.assertEqual(rows[3]["ui_visible_latency_ms"], "150.0")
        self.assertEqual(failures, [(2, "TimeoutError"), (3, "RuntimeError")])
        with open(self.path, newline="", encoding="utf-8") as fh:
            self.assertEqual(len(list(csv.DictReader(fh))), 5)

    def test_a_failing_scenario_does_not_stop_the_others(self):
        outcomes = [TimeoutError("x")] * 2 + [_outcome(50.0)] * 2
        rows = self._run(outcomes, scenarios=("cold", "expand"))
        self.assertEqual([(r["scenario"], r["status"]) for r in rows],
                         [("cold", "timeout"), ("cold", "timeout"),
                          ("expand", "ok"), ("expand", "ok")])

    def test_summary_counts_failures_and_both_policies(self):
        outs = [_outcome(float(i)) for i in range(1, 29)]
        outs += [TimeoutError("t"), _outcome(5000.0, verified=False)]
        rows = self._run(outs)
        cold = h.summarize_rows(rows, 95, "nearest_rank", "as_infinite")["scenarios"]["cold"]
        self.assertEqual(cold["n_attempted"], 30)
        self.assertEqual((cold["n_ok"], cold["n_timeout"], cold["n_content_unverified"]),
                         (28, 1, 1))
        self.assertEqual(cold["as_infinite"]["nearest_rank"]["p95"], math.inf)
        self.assertEqual(cold["ok_only"]["nearest_rank"]["p95"], 27.0)  # ceil(.95*28)=27
        self.assertEqual(cold["max_ok_ms"], 28.0)  # la no verificada no entra en ok

    def test_all_failed_scenario_has_no_ok_percentile(self):
        rows = self._run([TimeoutError("t"), TimeoutError("t")])
        cold = h.summarize_rows(rows, 95, "linear", "ok_only")["scenarios"]["cold"]
        self.assertIsNone(cold["ok_only"]["linear"]["p95"])
        self.assertIsNone(cold["primary"]["p95"])
        self.assertEqual(cold["as_infinite"]["linear"]["p95"], math.inf)

    def test_exit_code_nonzero_if_any_row_not_ok(self):
        self.assertEqual(h.exit_code_for([{"status": "ok"}]), 0)
        self.assertEqual(h.exit_code_for([{"status": "ok"}, {"status": "timeout"}]), 1)
        self.assertEqual(h.exit_code_for([{"status": "content_unverified"}]), 1)
        self.assertEqual(h.exit_code_for([]), 1)

    def test_infinity_is_serialised_explicitly_in_json(self):
        self.assertEqual(h._json_safe({"a": [math.inf, 1.0]}), {"a": ["Infinity", 1.0]})


# ------------------------------------------------------- 5) calentamiento
class WarmupTests(unittest.TestCase):
    def test_warmup_rows_recorded_and_excluded_from_percentile(self):
        with tempfile.TemporaryDirectory() as tmp:
            writer = h.IncrementalSampleWriter(Path(tmp) / "samples.csv")
            plan = h.build_schedule(["cold"], repetitions=30, warmup=1, order="blocks")
            lat = iter([99999.0] + [float(i) for i in range(1, 31)])
            rows = h.execute_schedule(plan, lambda p: _outcome(next(lat)), writer,
                                      log=_ListLog())
            writer.close()
        self.assertEqual(rows[0]["role"], "warmup")
        self.assertEqual(rows[0]["ui_visible_latency_ms"], "99999.0")
        cold = h.summarize_rows(rows, 95, "nearest_rank", "as_infinite")["scenarios"]["cold"]
        self.assertEqual(cold["n_attempted"], 30)
        self.assertEqual(cold["n_warmup"], 1)
        self.assertEqual(cold["warmup_latencies_ms"], [99999.0])
        self.assertEqual(cold["as_infinite"]["nearest_rank"]["p95"], 29.0)
        self.assertEqual(cold["max_ok_ms"], 30.0)

    def test_failed_warmup_is_reported_and_fails_exit_code(self):
        rows = [{"scenario": "cold", "role": "warmup", "status": "timeout",
                 "ui_visible_latency_ms": ""},
                {"scenario": "cold", "role": "measure", "status": "ok",
                 "ui_visible_latency_ms": "10.0"}]
        cold = h.summarize_rows(rows, 95, None, None)["scenarios"]["cold"]
        self.assertEqual(cold["warmup_statuses"], ["timeout"])
        self.assertEqual(cold["n_timeout"], 0)
        self.assertEqual(h.exit_code_for(rows), 1)

    def test_default_warmup_zero_and_negative_rejected(self):
        self.assertEqual(_args().warmup, 0)
        self.assertIn("--warmup debe ser >= 0", h.validate_args(_args("--warmup", "-1")))
        with self.assertRaises(ValueError):
            h.build_schedule(["cold"], 1, -1, "blocks")


# ----------------------------------------------------------------- 6) orden
class OrderTests(unittest.TestCase):
    def test_blocks_order(self):
        plan = h.build_schedule(["cold", "update"], 2, 1, "blocks")
        self.assertEqual([(p.scenario, p.role, p.iteration) for p in plan], [
            ("cold", "warmup", 1), ("cold", "measure", 1), ("cold", "measure", 2),
            ("update", "warmup", 1), ("update", "measure", 1), ("update", "measure", 2),
        ])

    def test_interleaved_order(self):
        plan = h.build_schedule(["cold", "update"], 2, 1, "interleaved")
        self.assertEqual([(p.scenario, p.role, p.iteration) for p in plan], [
            ("cold", "warmup", 1), ("update", "warmup", 1),
            ("cold", "measure", 1), ("update", "measure", 1),
            ("cold", "measure", 2), ("update", "measure", 2),
        ])

    def test_same_samples_regardless_of_order(self):
        a = h.build_schedule(h.SCENARIOS, 5, 2, "blocks")
        b = h.build_schedule(h.SCENARIOS, 5, 2, "interleaved")
        self.assertEqual(sorted(a, key=repr), sorted(b, key=repr))

    def test_unknown_order_rejected(self):
        with self.assertRaises(ValueError):
            h.build_schedule(["cold"], 1, 0, "random")
        with mock.patch("sys.stderr"), self.assertRaises(SystemExit):
            _args("--order", "random")


# ----------------------------------------------- 7) intervalo de expandir
class _FakeClock:
    def __init__(self, step=0.01):
        self.t = 0.0
        self.step = step
        self.sleeps = []

    def clock(self):
        self.t += self.step
        return self.t

    def sleep(self, s):
        self.sleeps.append(s)
        self.t += s


class _Summary:
    def __init__(self, driver):
        self.driver = driver

    def click(self):
        self.driver.calls.append("click")
        self.driver.clicked_at = self.driver.fake_clock.t


_DEFAULT = object()


class _EventExpandDriver:
    """Driver simulado para el modo current (medida por evento en el navegador)."""

    def __init__(self, fake_clock, result=_DEFAULT, armed=None, pre_open=False, pre_grid=False,
                 has_expander=True, python_delay_s=0.0):
        self.fake_clock = fake_clock
        self.result = result if result is not _DEFAULT else {
            "t_click": 1000.0, "t_visible": 1123.5, "via": "mutation", "timed_out": False}
        self.armed = armed if armed is not None else {"armed": True}
        self.pre_open = pre_open
        self.pre_grid = pre_grid
        self.has_expander = has_expander
        self.python_delay_s = python_delay_s
        self.calls = []
        self.script_timeout = None
        self.clicked_at = None

    def find_elements(self, by, selector):
        if by == "xpath":
            return [_Summary(self)] if self.has_expander else []
        return []

    def execute_script(self, script, *args):
        if "__sapiExpand" in script:
            self.calls.append("arm")
            self.arm_args = args
            return self.armed
        if "sapiGridVisible" in script:
            return self.pre_grid
        if "d.open" in script:
            return self.pre_open
        if "stStatusWidget" in script:
            return False
        return self.pre_grid

    def set_script_timeout(self, seconds):
        self.script_timeout = seconds

    def execute_async_script(self, script, *args):
        self.calls.append("wait")
        self.wait_args = args
        self.fake_clock.t += self.python_delay_s  # ida y vuelta de WebDriver
        return self.result


class CurrentExpandEventTests(unittest.TestCase):
    """Ajuste 1 (Auditor, Orden 09): current sin ningún sleep dentro del intervalo."""

    def _measure(self, drv, fc, timeout=5.0):
        return h.measure_expand(drv, "current", timeout=timeout, clock=fc.clock, sleep=fc.sleep)

    def test_delayed_grid_measured_by_browser_clock_without_any_sleep(self):
        fc = _FakeClock()
        drv = _EventExpandDriver(fc, result={"t_click": 500.0, "t_visible": 2500.0,
                                             "via": "mutation", "timed_out": False},
                                 python_delay_s=2.3)
        ms, detail = self._measure(drv, fc)
        self.assertEqual(ms, 2000.0)  # performance.now: 2500 - 500
        self.assertEqual(fc.sleeps, [])  # ningún sleep de Python, ni de 50 ms ni de 500 ms
        self.assertIn("via=mutation", detail)
        self.assertIn("wall_python_ms=", detail)

    def test_no_real_sleep_called_during_current_measurement(self):
        fc = _FakeClock()
        with mock.patch.object(h.time, "sleep", side_effect=AssertionError("sleep")) as sl:
            self._measure(_EventExpandDriver(fc), fc)
        sl.assert_not_called()

    def test_latency_comes_from_browser_not_from_python_round_trip(self):
        fc = _FakeClock()
        drv = _EventExpandDriver(fc, python_delay_s=9.0)
        ms, _ = self._measure(drv, fc)
        self.assertAlmostEqual(ms, 123.5)

    def test_arm_before_click_and_wait_after_click(self):
        fc = _FakeClock()
        drv = _EventExpandDriver(fc)
        self._measure(drv, fc, timeout=5.0)
        self.assertEqual(drv.calls, ["arm", "click", "wait"])
        self.assertEqual(drv.arm_args[1], h._GRID_SELECTOR)
        self.assertEqual(drv.arm_args[2], 5000.0)  # el plazo se fija al armar
        self.assertEqual(drv.wait_args, (5000.0,))
        self.assertGreater(drv.script_timeout, 5.0)

    def test_timeout_result_is_timeout_error(self):
        fc = _FakeClock()
        drv = _EventExpandDriver(fc, result={"t_click": 1.0, "t_visible": None,
                                             "via": None, "timed_out": True})
        with self.assertRaises(TimeoutError):
            self._measure(drv, fc)
        self.assertEqual(fc.sleeps, [])

    def test_late_event_with_js_flag_false_is_still_timeout(self):
        # Defensa en Python, independiente del JS: 5000,001 ms con plazo de 5 s.
        fc = _FakeClock()
        drv = _EventExpandDriver(fc, result={"t_click": 1000.0, "t_visible": 6000.001,
                                             "via": "mutation", "timed_out": False})
        with self.assertRaises(TimeoutError) as cm:
            self._measure(drv, fc, timeout=5.0)
        self.assertIn("fuera del plazo", str(cm.exception))

    def test_duration_equal_to_timeout_is_success(self):
        fc = _FakeClock()
        drv = _EventExpandDriver(fc, result={"t_click": 1000.0, "t_visible": 6000.0,
                                             "via": "raf", "timed_out": False})
        ms, _ = self._measure(drv, fc, timeout=5.0)
        self.assertEqual(ms, 5000.0)

    def test_js_timed_out_flag_wins_even_with_both_marks(self):
        fc = _FakeClock()
        drv = _EventExpandDriver(fc, result={"t_click": 1000.0, "t_visible": 1100.0,
                                             "via": "mutation", "timed_out": True})
        with self.assertRaises(TimeoutError):
            self._measure(drv, fc, timeout=5.0)

    def test_late_sample_is_a_timeout_row_and_infinite_in_percentile(self):
        fc = _FakeClock()
        late = {"t_click": 0.0, "t_visible": 5000.5, "via": "mutation", "timed_out": False}
        ok = {"t_click": 0.0, "t_visible": 100.0, "via": "mutation", "timed_out": False}
        results = iter([ok, late])

        def sample(planned):
            drv = _EventExpandDriver(fc, result=next(results))
            ms, detail = self._measure(drv, fc, timeout=5.0)
            return h.SampleOutcome(latency_ms=ms, content_verified=True, method_detail=detail)

        with tempfile.TemporaryDirectory() as tmp:
            writer = h.IncrementalSampleWriter(Path(tmp) / "samples.csv")
            rows = h.execute_schedule(h.build_schedule(["expand"], 2, 0, "blocks"), sample,
                                      writer, log=_ListLog())
            writer.close()
        self.assertEqual([r["status"] for r in rows], ["ok", "timeout"])
        self.assertEqual(rows[1]["ui_visible_latency_ms"], "")
        self.assertIn("5000.500 ms", rows[1]["error_message"])
        summ = h.summarize_rows(rows, 95, "nearest_rank", "as_infinite")["scenarios"]["expand"]
        self.assertEqual(summ["as_infinite"]["nearest_rank"]["p95"], math.inf)
        self.assertEqual(summ["n_timeout"], 1)

    def test_click_not_registered_is_an_error(self):
        fc = _FakeClock()
        drv = _EventExpandDriver(fc, result={"t_click": None, "t_visible": None,
                                             "via": None, "timed_out": True})
        with self.assertRaises(RuntimeError) as cm:
            self._measure(drv, fc)
        self.assertIn("no registró el clic", str(cm.exception))

    def test_invalid_or_incoherent_results_are_errors(self):
        for res in ({"error": "medición no armada"}, None, "texto",
                    {"t_click": 10.0, "t_visible": 5.0, "via": "raf", "timed_out": False}):
            fc = _FakeClock()
            with self.assertRaises(RuntimeError):
                self._measure(_EventExpandDriver(fc, result=res), fc)

    def test_arming_failure_aborts_before_click(self):
        fc = _FakeClock()
        drv = _EventExpandDriver(fc, armed={"armed": False, "reason": "sin <details>"})
        with self.assertRaises(RuntimeError) as cm:
            self._measure(drv, fc)
        self.assertIn("sin <details>", str(cm.exception))
        self.assertNotIn("click", drv.calls)

    def test_invalid_pre_state_rejected_before_arming(self):
        fc = _FakeClock()
        for kw in ({"pre_open": True}, {"pre_grid": True}, {"pre_open": None}):
            drv = _EventExpandDriver(fc, **kw)
            with self.assertRaises(RuntimeError) as cm:
                self._measure(drv, fc)
            self.assertIn("Estado previo inválido", str(cm.exception))
            self.assertEqual(drv.calls, [])

    def test_missing_expander_and_unknown_method(self):
        fc = _FakeClock()
        with self.assertRaises(RuntimeError):
            self._measure(_EventExpandDriver(fc, has_expander=False), fc)
        with self.assertRaises(ValueError):
            h.measure_expand(_EventExpandDriver(fc), "old", clock=fc.clock, sleep=fc.sleep)

    def test_event_scripts_do_not_poll(self):
        self.assertIn("MutationObserver", h._EXPAND_ARM_JS)
        self.assertIn("requestAnimationFrame", h._EXPAND_ARM_JS)
        self.assertIn("capture: true", h._EXPAND_ARM_JS)
        for js in (h._EXPAND_ARM_JS, h._EXPAND_WAIT_JS):
            self.assertNotIn("setInterval", js)
        self.assertNotIn("setTimeout", h._EXPAND_ARM_JS)
        self.assertEqual(h._EXPAND_WAIT_JS.count("setTimeout"), 1)  # solo el plazo


_NODE = shutil.which("node")

_NODE_HARNESS = r"""
const fs = require('fs');
const [armSrc, waitSrc, gridSrc, scenario] = [fs.readFileSync(process.argv[2], 'utf8'),
  fs.readFileSync(process.argv[3], 'utf8'), fs.readFileSync(process.argv[4], 'utf8'),
  process.argv[5]];
globalThis.window = globalThis;
let fakeNow = null;  // reloj controlado para los casos de borde
const realNow = performance.now.bind(performance);
Object.defineProperty(globalThis, 'performance', { configurable: true,
  value: { now: () => (fakeNow === null ? realNow() : fakeNow) } });
globalThis.requestAnimationFrame = (cb) => setTimeout(() => cb(performance.now()), 16);
const observers = [];
globalThis.MutationObserver = class {
  constructor(cb) { this.cb = cb; this.active = false; observers.push(this); }
  observe() { this.active = true; }
  disconnect() { this.active = false; }
};
const mutate = () => observers.forEach(o => o.active && o.cb([]));
// DOM mínimo con el comportamiento observado en Edge 158 (Instrumentación B):
// la grilla dentro de un <details> cerrado conserva su caja de layout, pero
// checkVisibility() es false; abierto, el <details> recorta (overflow) mientras
// su altura crece durante la animación.
const details = { open: false, clipH: 1000, querySelectorAll: () => [grid],
  parentElement: null,
  getBoundingClientRect() { return { top: 0, bottom: this.clipH, left: 0, right: 800 }; } };
const grid = { shown: false, parentElement: details,
  getClientRects() { return this.shown ? [1] : []; },
  get offsetHeight() { return this.shown ? 280 : 0; },
  checkVisibility() { return this.shown && details.open; },
  getBoundingClientRect() { return { top: 300, bottom: 580, left: 0, right: 700 }; } };
globalThis.getComputedStyle = (e) => (e === details
  ? { overflowX: 'hidden', overflowY: 'hidden' } : { overflowX: 'visible', overflowY: 'visible' });
const listeners = [];
const summary = {
  closest: (s) => (scenario === 'no_details' ? null : details),
  addEventListener: (t, fn, opts) => listeners.push({ t, fn, opts }),
};
const click = () => {  // listener en captura y luego la acción por omisión: abrir
  listeners.filter(l => l.t === 'click').forEach(l => l.fn());
  details.open = true; mutate();
};
const gridVisible = () => new Function(gridSrc).apply(null, [summary, 'GRID']);
const arm = new Function(armSrc);
const wait = new Function(waitSrc);
const out = (o) => { process.stdout.write(JSON.stringify(o)); process.exit(0); };

if (scenario === 'wait_unarmed') { wait.apply(null, [500, out]); }
else if (scenario === 'grid_states') {
  const st = {};
  grid.shown = true;                       // caja de layout presente
  st.closed_with_layout_box = gridVisible();
  details.open = true; details.clipH = 200;  // abierto, pero recortado (grilla en 300)
  st.open_clipped = gridVisible();
  details.clipH = 350;                     // empieza a asomar
  st.open_partly_revealed = gridVisible();
  details.open = false;
  st.closed_again = gridVisible();
  delete grid.checkVisibility; details.open = true;
  st.fallback_open = gridVisible();
  details.open = false;
  st.fallback_closed = gridVisible();
  out(st);
}
else {
  const ARM_TIMEOUT = { never: 300, visible_before_click: 1000, late_query: 50,
    border_equal: 50, border_over: 50, bad_timeout: 0 };
  const T = scenario in ARM_TIMEOUT ? ARM_TIMEOUT[scenario] : 3000;
  const armed = arm.apply(null, [summary, 'GRID', T]);
  if (!armed.armed) { out({ armed }); }
  else {
    const opts = listeners[0] && listeners[0].opts;
    if (scenario === 'mutation_delayed') {
      click();
      setTimeout(() => { grid.shown = true; mutate(); }, 200);
      wait.apply(null, [3000, (r) => out({ r, opts })]);
    } else if (scenario === 'layout_only') {
      click();
      setTimeout(() => { grid.shown = true; }, 120);  // sin mutación: lo ve rAF
      wait.apply(null, [3000, (r) => out({ r, opts })]);
    } else if (scenario === 'never') {
      click();
      wait.apply(null, [300, (r) => out({ r, opts })]);
    } else if (scenario === 'late_query') {
      // Reproducción del Auditor: plazo 50 ms, mutación a los 75 ms, consulta a los 125 ms.
      click();
      setTimeout(() => { grid.shown = true; mutate(); }, 75);
      setTimeout(() => wait.apply(null, [T, (r) => out({ r, opts })]), 125);
    } else if (scenario === 'border_equal' || scenario === 'border_over') {
      fakeNow = 100; click();
      fakeNow = scenario === 'border_equal' ? 150 : 150.001;
      grid.shown = true; mutate();
      wait.apply(null, [T, (r) => out({ r, opts })]);
    } else if (scenario === 'clip_reveal') {
      // Como en Edge: la grilla ya está renderizada, el <details> se abre a 48 px y
      // crece sin mutaciones; la grilla asoma cuando la altura supera 300 px.
      grid.shown = true; details.clipH = 48;
      click();
      setTimeout(() => { details.clipH = 400; }, 120);
      wait.apply(null, [3000, (r) => out({ r, opts })]);
    } else if (scenario === 'visible_before_click') {
      grid.shown = true; mutate();
      setTimeout(() => {
        const clickAt = performance.now(); click();
        wait.apply(null, [1000, (r) => out({ r, opts, clickAt })]);
      }, 100);
    }
  }
}
"""


@unittest.skipIf(_NODE is None, "node no disponible")
class EventScriptInNodeTests(unittest.TestCase):
    """Ejecuta los scripts JS reales con un DOM mínimo simulado en Node."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        d = Path(cls._tmp.name)
        (d / "arm.js").write_text(h._EXPAND_ARM_JS, encoding="utf-8")
        (d / "wait.js").write_text(h._EXPAND_WAIT_JS, encoding="utf-8")
        (d / "grid.js").write_text(h._GRID_IN_DETAILS_JS, encoding="utf-8")
        (d / "harness.js").write_text(_NODE_HARNESS, encoding="utf-8")
        cls.dir = d

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def _run(self, scenario):
        res = subprocess.run(
            [_NODE, str(self.dir / "harness.js"), str(self.dir / "arm.js"),
             str(self.dir / "wait.js"), str(self.dir / "grid.js"), scenario],
            capture_output=True, text=True, encoding="utf-8", timeout=30)
        self.assertEqual(res.returncode, 0, res.stderr)
        return json.loads(res.stdout)

    def test_delayed_grid_detected_by_mutation_with_browser_timestamps(self):
        out = self._run("mutation_delayed")
        r = out["r"]
        self.assertFalse(r["timed_out"])
        self.assertEqual(r["via"], "mutation")  # el cambio de DOM se detecta en el acto
        self.assertGreaterEqual(r["t_visible"] - r["t_click"], 190.0)
        self.assertLess(r["t_visible"] - r["t_click"], 400.0)
        self.assertEqual(out["opts"], {"capture": True, "once": True})

    def test_visibility_without_mutation_detected_by_animation_frame(self):
        r = self._run("layout_only")["r"]
        self.assertEqual(r["via"], "raf")
        self.assertGreaterEqual(r["t_visible"] - r["t_click"], 110.0)
        self.assertLess(r["t_visible"] - r["t_click"], 400.0)

    def test_never_visible_times_out(self):
        r = self._run("never")["r"]
        self.assertTrue(r["timed_out"])
        self.assertIsNone(r["t_visible"])
        self.assertIsNotNone(r["t_click"])

    def test_nothing_is_recorded_before_the_click(self):
        out = self._run("visible_before_click")
        r = out["r"]
        # La grilla ya era visible 100 ms antes: ni t_click ni t_visible pueden ser
        # anteriores al clic real (el arnés Python rechaza además ese estado previo).
        self.assertGreaterEqual(r["t_click"], out["clickAt"])
        self.assertGreaterEqual(r["t_visible"], out["clickAt"])

    def test_late_query_after_deadline_is_timeout_not_success(self):
        # Negativo (Auditor, delta 07f814a): el evento llega a los ~75 ms con plazo de
        # 50 ms y la consulta a los 125 ms; antes salía timed_out=false.
        r = self._run("late_query")["r"]
        self.assertGreater(r["t_visible"] - r["t_click"], 50.0)
        self.assertTrue(r["timed_out"])  # en 07f814a: False
        self.assertTrue(r["late"])
        self.assertEqual(r["timeout_ms"], 50)

    def test_duration_equal_to_deadline_is_accepted(self):
        r = self._run("border_equal")["r"]
        self.assertEqual(r["t_visible"] - r["t_click"], 50.0)
        self.assertFalse(r["late"])
        self.assertFalse(r["timed_out"])

    def test_duration_just_over_deadline_is_timeout(self):
        r = self._run("border_over")["r"]
        self.assertGreater(r["t_visible"] - r["t_click"], 50.0)
        self.assertTrue(r["timed_out"])

    def test_invalid_deadline_is_not_armed(self):
        out = self._run("bad_timeout")
        self.assertFalse(out["armed"]["armed"])
        self.assertIn("plazo inválido", out["armed"]["reason"])

    def test_closed_details_layout_box_is_not_visible(self):
        # Defecto B-1 (Edge 158): con el expander cerrado la grilla tiene caja de
        # layout; el criterio anterior (rects + offsetHeight) la daba por visible.
        st = self._run("grid_states")
        self.assertFalse(st["closed_with_layout_box"])
        self.assertFalse(st["closed_again"])
        self.assertFalse(st["fallback_closed"])

    def test_open_but_clipped_grid_is_not_visible_until_revealed(self):
        # Defecto B-2 (Edge 158): durante la animación el <details> recorta la grilla.
        st = self._run("grid_states")
        self.assertFalse(st["open_clipped"])
        self.assertTrue(st["open_partly_revealed"])
        self.assertTrue(st["fallback_open"])

    def test_clip_reveal_is_detected_by_frame_not_at_click(self):
        r = self._run("clip_reveal")["r"]
        self.assertFalse(r["timed_out"])
        self.assertEqual(r["via"], "raf")
        self.assertGreaterEqual(r["t_visible"] - r["t_click"], 110.0)  # no ~0 ms al abrir
        self.assertLess(r["t_visible"] - r["t_click"], 400.0)

    def test_no_details_is_not_armed(self):
        out = self._run("no_details")
        self.assertFalse(out["armed"]["armed"])

    def test_wait_without_arm_reports_error(self):
        self.assertIn("error", self._run("wait_unarmed"))


class _ReadyDriver:
    """Página que tarda en mostrar el expander y en salir de «Running»."""

    def __init__(self, fc, expander_after_s=0.3, running_until_s=0.5):
        self.fc = fc
        self.expander_after_s = expander_after_s
        self.running_until_s = running_until_s

    def find_elements(self, by, selector):
        if by == "xpath" and self.fc.t >= self.expander_after_s:
            return [object()]
        return []

    def execute_script(self, script, *args):
        return self.fc.t < self.running_until_s


class ExpanderReadyTests(unittest.TestCase):
    """Defecto B-3 (Edge 158): tras recargar, el expander llega después del primer
    chip VP-; la preparación (fuera del intervalo) debe esperarlo."""

    def test_waits_for_expander_and_streamlit_idle(self):
        fc = _FakeClock()
        h.wait_for_expander_ready(_ReadyDriver(fc), timeout=5.0, clock=fc.clock, sleep=fc.sleep)
        self.assertGreaterEqual(fc.t, 0.5)

    def test_returns_immediately_when_ready(self):
        fc = _FakeClock()
        h.wait_for_expander_ready(_ReadyDriver(fc, 0.0, 0.0), timeout=5.0,
                                  clock=fc.clock, sleep=fc.sleep)
        self.assertEqual(fc.sleeps, [])

    def test_times_out_if_expander_never_appears(self):
        fc = _FakeClock()
        with self.assertRaises(TimeoutError) as cm:
            h.wait_for_expander_ready(_ReadyDriver(fc, 99.0, 0.0), timeout=1.0,
                                      clock=fc.clock, sleep=fc.sleep)
        self.assertIn("encontrado=False", str(cm.exception))

    def test_times_out_if_streamlit_stays_running(self):
        fc = _FakeClock()
        with self.assertRaises(TimeoutError) as cm:
            h.wait_for_expander_ready(_ReadyDriver(fc, 0.0, 99.0), timeout=1.0,
                                      clock=fc.clock, sleep=fc.sleep)
        self.assertIn("running=True", str(cm.exception))

    def test_expand_scenario_prepares_before_measuring(self):
        calls = []
        orig_ready, orig_measure = h.wait_for_expander_ready, h.measure_expand
        with mock.patch.object(h, "wait_for_expander_ready",
                               side_effect=lambda *a, **k: calls.append("ready")), \
                mock.patch.object(h, "measure_expand",
                                  side_effect=lambda *a, **k: (calls.append("measure"),
                                                               (5.0, "d"))[1]):
            fc = _FakeClock()
            runner = h.BrowserScenarioRunner("http://x", None, Path("."), "current", "none",
                                             driver_factory=_PanelDriver, clock=fc.clock,
                                             sleep=fc.sleep)
            try:
                runner(h.PlannedSample("expand", "measure", 1))
            except Exception:
                pass
            runner.close()
        self.assertEqual(calls[:2], ["ready", "measure"])
        self.assertIs(h.wait_for_expander_ready, orig_ready)
        self.assertIs(h.measure_expand, orig_measure)

    def test_grid_js_requires_open_details(self):
        self.assertIn("!d.open", h._GRID_IN_DETAILS_JS)
        self.assertIn("checkVisibility", h._GRID_IN_DETAILS_JS)
        self.assertIn("overflowY", h._GRID_IN_DETAILS_JS)
        self.assertIn("sapiGridVisible", h._EXPAND_ARM_JS)


class _FakeTimeoutException(Exception):
    pass


_FakeTimeoutException.__name__ = "TimeoutException"


class _LegacyDriver:
    def __init__(self, fake_clock, pre_open=False):
        self.fake_clock = fake_clock
        self.pre_open = pre_open
        self.calls = []
        self.clicked_at = None

    def find_elements(self, by, selector):
        return [_Summary(self)] if by == "xpath" else []

    def execute_script(self, script, *args):
        if "sapiGridVisible" in script:
            return False
        if "d.open" in script:
            return self.pre_open
        return False


def _legacy_factory(log, fake_clock, until_raises=None, until_after_s=0.0):
    class _Wait:
        def __init__(self, driver, timeout, *args, **kwargs):
            log.append(("WebDriverWait", timeout, args, kwargs, fake_clock.t))

        def until(self, condition):
            log.append(("until", condition))
            fake_clock.t += until_after_s
            if until_raises is not None:
                raise until_raises
            return True

    class _EC:
        @staticmethod
        def visibility_of_element_located(locator):
            log.append(("visibility_of_element_located", locator))
            return ("cond", locator)

    return lambda: (_Wait, _EC)


PARENT_LEGACY_SELECTOR = "div[data-testid='stDataFrame'], [data-testid='stTable']"


class LegacyExpandParityTests(unittest.TestCase):
    """Ajuste 2 (Auditor, Orden 09): legacy = intervalo idéntico a f8c5218:617-623."""

    def _measure(self, drv, fc, log, **kw):
        return h.measure_expand(drv, "legacy", clock=fc.clock, sleep=fc.sleep,
                                wait_factory=_legacy_factory(log, fc, **kw))

    def test_same_sequence_and_arguments_as_parent(self):
        fc, log = _FakeClock(), []
        drv = _LegacyDriver(fc)
        orig_sleep = fc.sleep

        def sleep(s):
            log.append(("sleep", s))
            orig_sleep(s)

        fc.sleep = sleep
        self._measure(drv, fc, log, until_after_s=0.08)
        names = [e[0] for e in log]
        self.assertEqual(names[0], "sleep")
        self.assertEqual(log[0], ("sleep", 0.5))
        self.assertEqual(names[1:], ["WebDriverWait", "visibility_of_element_located", "until"])
        _, timeout, args, kwargs, t_at = log[1]
        self.assertEqual(timeout, 5)  # mismo plazo que el padre
        self.assertEqual((args, kwargs), ((), {}))  # sondeo por omisión (0,5 s), sin cambios
        self.assertEqual(log[2][1], ("css selector", PARENT_LEGACY_SELECTOR))
        self.assertEqual(drv.calls, ["click"])
        self.assertGreaterEqual(t_at - drv.clicked_at, 0.5)  # el plazo arranca tras la pausa

    def test_latency_includes_fixed_pause_and_wait(self):
        fc, log = _FakeClock(), []
        ms, detail = self._measure(_LegacyDriver(fc), fc, log, until_after_s=0.08)
        self.assertGreaterEqual(ms, 580.0)
        self.assertIn("intervalo de f8c5218", detail)

    def test_parent_constants(self):
        self.assertEqual(h.LEGACY_EXPAND_SLEEP_S, 0.5)
        self.assertEqual(h.LEGACY_WAIT_TIMEOUT_S, 5)
        self.assertEqual(h._GRID_SELECTOR, PARENT_LEGACY_SELECTOR)
        self.assertEqual(h._EXPANDER_XPATH, "//summary[contains(., 'Ver ranking completo')]")

    def test_selenium_timeout_becomes_timeout_error(self):
        fc, log = _FakeClock(), []
        with self.assertRaises(TimeoutError) as cm:
            self._measure(_LegacyDriver(fc), fc, log, until_raises=_FakeTimeoutException("t"))
        self.assertIsInstance(cm.exception.__cause__, _FakeTimeoutException)

    def test_other_wait_errors_propagate_unchanged(self):
        fc, log = _FakeClock(), []
        with self.assertRaises(KeyError):
            self._measure(_LegacyDriver(fc), fc, log, until_raises=KeyError("x"))

    def test_open_pre_state_is_reported_not_rejected(self):
        fc, log = _FakeClock(), []
        ms, detail = self._measure(_LegacyDriver(fc, pre_open=True), fc, log)
        self.assertIn("details.open=True", detail)

    @unittest.skipIf(h.WebDriverWait is not None, "selenium instalado")
    def test_legacy_without_selenium_fails_closed(self):
        fc = _FakeClock()
        with self.assertRaises(RuntimeError) as cm:
            h.measure_expand(_LegacyDriver(fc), "legacy", clock=fc.clock, sleep=fc.sleep)
        self.assertIn("requiere Selenium", str(cm.exception))

    def test_default_expand_method_is_current_and_cli_validates(self):
        self.assertEqual(_args().expand_method, "current")
        self.assertEqual(_args("--expand-method", "legacy").expand_method, "legacy")
        with mock.patch("sys.stderr"), self.assertRaises(SystemExit):
            _args("--expand-method", "sleepy")


class TimingColumnsTests(unittest.TestCase):
    def test_every_row_declares_source_and_resolution_including_failures(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "samples.csv"
            writer = h.IncrementalSampleWriter(path)
            plan = h.build_schedule(h.SCENARIOS, 1, 0, "blocks")
            outs = iter([_outcome(1.0), TimeoutError("t"), _outcome(2.0), RuntimeError("e")])

            def sample(p):
                o = next(outs)
                if isinstance(o, BaseException):
                    raise o
                return o

            h.execute_schedule(plan, sample, writer, log=_ListLog(),
                               timing_fn=lambda p: h.timing_info(p.scenario, "current"))
            writer.close()
            with open(path, newline="", encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))
        self.assertIn("timing_source", rows[0])
        by = {r["scenario"]: r for r in rows}
        self.assertEqual(by["cold"]["timing_source"], "python_perf_counter")
        self.assertIn("±50 ms", by["cold"]["timing_resolution"])
        self.assertEqual(by["update"]["status"], "timeout")
        self.assertIn("±50 ms", by["update"]["timing_resolution"])
        self.assertEqual(by["expand"]["status"], "error")
        self.assertEqual(by["expand"]["timing_source"], "browser_performance_now")
        self.assertIn("sin sleep en Python", by["expand"]["timing_resolution"])

    def test_legacy_resolution_declared(self):
        src, res = h.timing_info("expand", "legacy")
        self.assertEqual(src, "python_perf_counter")
        self.assertIn("0,5 s", res)

    def test_unknown_scenario_or_method_rejected(self):
        with self.assertRaises(ValueError):
            h.timing_info("nope")
        with self.assertRaises(ValueError):
            h.timing_info("expand", "sleepy")

    def test_selenium_timeout_exception_classified_as_timeout(self):
        self.assertEqual(h.classify_exception(_FakeTimeoutException("x")), "timeout")
        self.assertEqual(h.classify_exception(TimeoutError("x")), "timeout")
        self.assertEqual(h.classify_exception(RuntimeError("x")), "error")


# -------------------------------------------------------- 8) KPI .sapi-card-kpi
class _KpiDriver:
    def __init__(self, cards):
        self.cards = cards

    def execute_script(self, script, *args):
        if "sapi-card-kpi" in script:
            return self.cards
        return ""


class KpiCardTests(unittest.TestCase):
    def test_card_with_label_then_value_passes(self):
        drv = _KpiDriver([["Celdas evaluadas", "50"], ["Prioridad alta", "5"]])
        ok, msg = h.verify_50_cells_integrity(drv, backend_url=None)
        self.assertTrue(ok)
        self.assertIn(".sapi-card-kpi", msg)

    def test_wrong_value_or_label_fails(self):
        for cards in ([["Celdas evaluadas", "49"]], [["Celdas", "50"]],
                      [["Celdas evaluadas", "500"]], [[None, "50"]], [["Celdas evaluadas", None]]):
            ok, _ = h.verify_50_cells_integrity(_KpiDriver(cards), backend_url=None)
            self.assertFalse(ok, cards)

    def test_old_layout_without_cards_fails(self):
        # El DOM antiguo (div.sapi-v2-kpi / texto "50 Celdas evaluadas") ya no se acepta.
        ok, _ = h.verify_50_cells_integrity(_KpiDriver([]), backend_url=None)
        self.assertFalse(ok)

    def test_whitespace_is_trimmed_and_malformed_items_ignored(self):
        cards = h.read_kpi_cards(_KpiDriver([["  Celdas evaluadas ", " 50 "], "basura", [1]]))
        self.assertEqual(cards, [("  Celdas evaluadas ", " 50 ")])
        self.assertTrue(h.kpi_cells_ok(cards))

    def test_dom_error_is_a_failure_not_a_pass(self):
        class _Broken:
            def execute_script(self, script, *args):
                raise RuntimeError("sin DOM")

        ok, msg = h.verify_50_cells_integrity(_Broken(), backend_url=None)
        self.assertFalse(ok)
        self.assertIn("Error comprobando KPI", msg)

    def test_selectors_match_the_panel_source(self):
        src = (REPO_ROOT / "app" / "components" / "ranking_backend_view.py").read_text(
            encoding="utf-8")
        self.assertIn('class="sapi-card-kpi sapi-card-kpi--', src)
        self.assertIn('<span class="sapi-card-kpi__label">Celdas evaluadas</span>', src)
        self.assertIn('<div class="sapi-card-kpi__val">{len(view.cells)}</div>', src)
        self.assertNotIn("sapi-v2-kpi", src)


# ---------------------------------------- escenarios con driver simulado
class _El:
    def __init__(self, text="", displayed=True):
        self.text = text
        self._d = displayed

    def is_displayed(self):
        return self._d

    def click(self):
        pass


class _PanelDriver:
    """Panel simulado que siempre muestra el ranking y la tarjeta KPI."""

    instances: list = []

    def __init__(self, fail_get=False):
        self.fail_get = fail_get
        self.quit_called = False
        self.gets = 0
        _PanelDriver.instances.append(self)

    def get(self, url):
        self.gets += 1
        if self.fail_get:
            raise RuntimeError("conexión rechazada")

    def refresh(self):
        pass

    def quit(self):
        self.quit_called = True

    def find_elements(self, by, selector):
        if "sapi-v2-chip" in selector:
            return [_El("VP-001 grupo prioritario")]
        return []

    def find_element(self, by, selector):
        return _El("vp-001 grupo prioritario")

    def execute_script(self, script, *args):
        if "sapi-card-kpi" in script:
            return [["Celdas evaluadas", "50"]]
        if "navigation" in script:
            return "navigate"
        if "textContent" in script:
            return "obtenido 2026-11-23 10:00:00 UTC"
        return None


class BrowserRunnerTests(unittest.TestCase):
    def setUp(self):
        _PanelDriver.instances = []
        self.fc = _FakeClock()

    def _runner(self, factory):
        return h.BrowserScenarioRunner("http://x", None, Path("."), "current", "none",
                                       driver_factory=factory, clock=self.fc.clock,
                                       sleep=self.fc.sleep)

    def test_cold_uses_a_new_browser_per_sample_and_quits_it(self):
        runner = self._runner(_PanelDriver)
        for i in (1, 2):
            out = runner(h.PlannedSample("cold", "measure", i))
            self.assertTrue(out.content_verified)
        self.assertEqual(len(_PanelDriver.instances), 2)
        self.assertTrue(all(d.quit_called for d in _PanelDriver.instances))

    def test_session_failure_is_recorded_and_session_recreated(self):
        made = {"n": 0}

        def factory():
            made["n"] += 1
            return _PanelDriver(fail_get=(made["n"] == 1))

        runner = self._runner(factory)
        with tempfile.TemporaryDirectory() as tmp:
            writer = h.IncrementalSampleWriter(Path(tmp) / "samples.csv")
            plan = h.build_schedule(["reload"], 2, 0, "blocks")
            rows = h.execute_schedule(plan, runner, writer, on_failure=runner.reset_session,
                                      log=_ListLog())
            writer.close()
        self.assertEqual(rows[0]["status"], "error")
        self.assertIn("conexión rechazada", rows[0]["error_message"])
        # navigation.type simulado = 'navigate' -> recarga sin verificar, pero registrada
        self.assertEqual(rows[1]["status"], "content_unverified")
        self.assertTrue(_PanelDriver.instances[0].quit_called)
        runner.close()
        self.assertTrue(_PanelDriver.instances[1].quit_called)


class _UpdateExpandDriver(_PanelDriver):
    """Panel simulado con botón Actualizar y expander cerrado que se abre al clic."""

    def __init__(self, ts_after_click="obtenido 2026-11-23 10:00:05 UTC", has_button=True,
                 pre_ts=True):
        super().__init__()
        self.ts = "obtenido 2026-11-23 10:00:00 UTC" if pre_ts else "sin marca"
        self.ts_after_click = ts_after_click
        self.has_button = has_button
        self.opened = False
        self.shots = []

    def save_screenshot(self, path):
        Path(path).write_bytes(b"png")
        self.shots.append(path)

    def find_elements(self, by, selector):
        if "Actualizar ranking" in selector:
            return [_ClickEl(self, "update")] if self.has_button else []
        if "Ver ranking completo" in selector:
            return [_ClickEl(self, "expand")]
        if "stDataFrame" in selector:
            return [_El("grid", displayed=self.opened)]
        return super().find_elements(by, selector)

    def set_script_timeout(self, seconds):
        self.script_timeout = seconds

    def execute_async_script(self, script, *args):
        return {"t_click": 10.0, "t_visible": 42.5, "via": "mutation", "timed_out": False}

    def execute_script(self, script, *args):
        if "__sapiExpand" in script:
            return {"armed": True}
        if "arguments[0].click()" in script:
            args[0].click()
            return None
        if "sapiGridVisible" in script:
            return self.opened
        if "d.open" in script:
            return self.opened
        if "scrollIntoView" in script:
            return None
        if "getBoundingClientRect" in script:
            return True
        if "stStatusWidget" in script:
            return False
        if "textContent" in script and "sapi-card-kpi" not in script:
            return self.ts
        return super().execute_script(script, *args)


class _ClickEl(_El):
    def __init__(self, driver, kind):
        super().__init__(kind)
        self.driver = driver
        self.kind = kind

    def click(self):
        if self.kind == "update":
            self.driver.clicks = getattr(self.driver, "clicks", 0) + 1
            self.driver.ts = self.driver.ts_after_click.replace(
                ":05 UTC", f":{4 + self.driver.clicks:02d} UTC")
        else:
            self.driver.opened = True


class UpdateAndExpandScenarioTests(unittest.TestCase):
    def setUp(self):
        _PanelDriver.instances = []
        self.fc = _FakeClock()
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _runner(self, factory, screenshots="none"):
        return h.BrowserScenarioRunner("http://x", None, self.dir, "current", screenshots,
                                       driver_factory=factory, clock=self.fc.clock,
                                       sleep=self.fc.sleep)

    def test_update_confirms_new_timestamp_and_sleeps_outside_interval(self):
        runner = self._runner(_UpdateExpandDriver, screenshots="first")
        out = runner(h.PlannedSample("update", "measure", 1))
        self.assertTrue(out.content_verified)
        self.assertEqual(out.pre_timestamp, "obtenido 2026-11-23 10:00:00 UTC")
        self.assertEqual(out.post_timestamp, "obtenido 2026-11-23 10:00:05 UTC")
        self.assertIn(h.UPDATE_CLOCK_GAP_S, self.fc.sleeps)  # sleep simulado, fuera del reloj real
        self.assertTrue(out.screenshot.startswith("update_measure_001"))
        self.assertEqual(out.screenshot_sha256, h.sha256_file(self.dir / out.screenshot))
        second = runner(h.PlannedSample("update", "measure", 2))
        self.assertEqual(second.screenshot, "")  # screenshots=first: solo la primera
        runner.close()

    def test_update_without_button_or_timestamp_is_an_error(self):
        runner = self._runner(lambda: _UpdateExpandDriver(has_button=False))
        with self.assertRaises(RuntimeError):
            runner(h.PlannedSample("update", "measure", 1))
        runner = self._runner(lambda: _UpdateExpandDriver(pre_ts=False))
        with self.assertRaises(RuntimeError):
            runner(h.PlannedSample("update", "measure", 1))

    def test_expand_scenario_opens_closed_expander_and_verifies_grid(self):
        runner = self._runner(_UpdateExpandDriver, screenshots="all")
        out = runner(h.PlannedSample("expand", "warmup", 1))
        self.assertTrue(out.content_verified, out.element_verified)
        self.assertIn("details.open=False", out.method_detail)
        self.assertEqual(out.latency_ms, 32.5)  # 42.5 - 10.0, reloj del navegador
        self.assertTrue(out.screenshot.startswith("expand_warmup_001"))

    def test_screenshot_first_skips_warmup(self):
        runner = self._runner(_UpdateExpandDriver, screenshots="first")
        out = runner(h.PlannedSample("reload", "warmup", 1))
        self.assertEqual(out.screenshot, "")


class IdentityAndCliTests(unittest.TestCase):
    def test_container_identities_from_json_array_and_lines(self):
        arr = json.dumps([{"Service": "web-v2", "Image": "sapi-web"}])
        lines = "\n".join(json.dumps({"service": s, "image": f"img-{s}"})
                          for s in ("db-v2", "backend")) + "\n"
        for out, expected in ((arr, {"web-v2": "sapi-web"}),
                              (lines, {"db-v2": "img-db-v2", "backend": "img-backend"})):
            res = mock.Mock(returncode=0, stdout=out)
            with mock.patch.object(h.subprocess, "run", return_value=res) as run:
                self.assertEqual(h.get_container_identities("p"), expected)
            self.assertEqual(run.call_args[0][0][:4], ["docker", "compose", "-p", "p"])

    def test_container_identities_empty_on_failure(self):
        with mock.patch.object(h.subprocess, "run",
                               return_value=mock.Mock(returncode=1, stdout="")):
            self.assertEqual(h.get_container_identities("p"), {})
        with mock.patch.object(h.subprocess, "run", side_effect=FileNotFoundError("docker")):
            self.assertEqual(h.get_container_identities("p"), {})

    def test_git_identities_unknown_on_failure(self):
        with mock.patch.object(h.subprocess, "run", side_effect=OSError("git")):
            self.assertEqual(h.get_git_identities(REPO_ROOT),
                             ("UNKNOWN_COMMIT", "UNKNOWN_TREE"))

    def test_main_negative_only_and_measurement_paths(self):
        with mock.patch.object(h, "run_negative_test_stale_dom", return_value=True), \
                self.assertRaises(SystemExit) as cm:
            h.main(["--negative-only"])
        self.assertEqual(cm.exception.code, 0)
        with mock.patch.object(h, "run_measurement", return_value=1) as run, \
                self.assertRaises(SystemExit) as cm:
            h.main(["--artifacts-dir", "rel\\dir"])
        self.assertEqual(cm.exception.code, 1)
        self.assertTrue(run.call_args[0][1].is_absolute())

    @unittest.skipIf(h.webdriver is not None, "selenium instalado")
    def test_create_driver_requires_selenium(self):
        with self.assertRaises(RuntimeError):
            h.create_driver()


# ------------------------------------------------- protocolo KPI-03 (kpi03-h3)
_PROTO = ["--protocol", "kpi03-h3", "--candidate-sha", "abc1234", "--expand-method", "current"]


def _rows_for(scenario, values, statuses=None, role="measure"):
    statuses = statuses or ["ok"] * len(values)
    return [{"scenario": scenario, "role": role, "iteration": i + 1, "status": st,
             "ui_visible_latency_ms": "" if v is None else repr(float(v))}
            for i, (v, st) in enumerate(zip(values, statuses))]


class ProtocolPresetTests(unittest.TestCase):
    def test_preset_fixes_every_protocol_value(self):
        a = _args(*_PROTO)
        self.assertEqual(a.scenarios, "cold,update,reload,expand")
        self.assertEqual((a.repetitions, a.warmup, a.order), (30, 1, "interleaved"))
        self.assertEqual((a.percentile, a.percentile_method, a.failure_policy),
                         (95.0, "nearest_rank", "as_infinite"))
        self.assertEqual((a.target_ms, a.min_n), (2000.0, 30))
        self.assertEqual(h.validate_args(a), [])

    def test_preset_schedule_is_one_warmup_cycle_plus_30_interleaved_rounds(self):
        a = _args(*_PROTO)
        plan = h.build_schedule(a.scenarios.split(","), a.repetitions, a.warmup, a.order)
        self.assertEqual(len(plan), 124)
        self.assertEqual([(p.scenario, p.role) for p in plan[:4]],
                         [(s, "warmup") for s in ("cold", "update", "reload", "expand")])
        measured = plan[4:]
        self.assertEqual(len(measured), 120)
        for r in range(30):
            block = measured[4 * r:4 * r + 4]
            self.assertEqual([p.scenario for p in block], ["cold", "update", "reload", "expand"])
            self.assertTrue(all(p.iteration == r + 1 and p.role == "measure" for p in block))

    def test_explicit_flags_equal_to_preset_are_accepted(self):
        a = _args(*_PROTO, "--repetitions", "30", "--order", "interleaved",
                  "--scenarios", "cold, update, reload, expand", "--target-ms", "2000")
        self.assertEqual(a.repetitions, 30)

    def test_conflicting_flags_are_rejected(self):
        for extra in (["--repetitions", "20"], ["--warmup", "0"], ["--order", "blocks"],
                      ["--percentile", "90"], ["--percentile-method", "linear"],
                      ["--failure-policy", "ok_only"], ["--target-ms", "2500"],
                      ["--min-n", "10"], ["--scenarios", "update,cold,reload,expand"],
                      ["--scenarios", "cold,update,reload"]):
            with mock.patch("sys.stderr"), self.assertRaises(SystemExit) as cm:
                _args(*_PROTO, *extra)
            self.assertEqual(cm.exception.code, 2, extra)

    def test_protocol_requires_candidate_sha_and_expand_method(self):
        for argv in (["--protocol", "kpi03-h3", "--expand-method", "current"],
                     ["--protocol", "kpi03-h3", "--candidate-sha", "xyz",
                      "--expand-method", "current"],
                     ["--protocol", "kpi03-h3", "--candidate-sha", "abc1234"]):
            with mock.patch("sys.stderr"), self.assertRaises(SystemExit):
                _args(*argv)
        errs = h.resolve_args(h.build_parser().parse_args(["--protocol", "kpi03-h3"]))
        self.assertTrue(any("--candidate-sha" in e for e in errs))
        self.assertTrue(any("--expand-method" in e for e in errs))

    def test_unknown_protocol_rejected_and_defaults_stay_provisional(self):
        with mock.patch("sys.stderr"), self.assertRaises(SystemExit):
            _args("--protocol", "kpi99")
        a = _args()
        self.assertIsNone(a.protocol)
        self.assertEqual((a.repetitions, a.warmup, a.order, a.expand_method),
                         (1, 0, "blocks", "current"))
        self.assertIsNone(a.target_ms)

    def test_target_and_min_n_validation(self):
        self.assertTrue(any("--target-ms exige" in e
                            for e in h.validate_args(_args("--target-ms", "2000"))))
        self.assertIn("--target-ms debe ser > 0", h.validate_args(
            _args("--target-ms", "0", "--percentile-method", "linear",
                  "--failure-policy", "ok_only")))
        self.assertIn("--min-n debe ser >= 1", h.validate_args(_args("--min-n", "0")))
        self.assertTrue(any("< --min-n" in e for e in h.validate_args(_args("--min-n", "5"))))


class VerdictTests(unittest.TestCase):
    def _summ(self, rows, target=2000.0, min_n=30):
        return h.summarize_rows(rows, 95, "nearest_rank", "as_infinite",
                                target_ms=target, min_n=min_n)

    def test_p95_is_rank_29_of_30_per_scenario(self):
        vals = list(range(1, 31))
        e = self._summ(_rows_for("cold", vals))["scenarios"]["cold"]
        self.assertEqual(e["nearest_rank_k"], 29)
        self.assertEqual(e["primary"]["p95"], 29.0)

    def test_pass_at_boundary_equal_to_target(self):
        vals = [100.0] * 28 + [2000.0, 9000.0]  # k=29 -> 2000
        e = self._summ(_rows_for("cold", vals))["scenarios"]["cold"]
        self.assertEqual(e["verdict"], "PASS")

    def test_fail_just_over_target(self):
        vals = [100.0] * 28 + [2000.001, 9000.0]
        e = self._summ(_rows_for("cold", vals))["scenarios"]["cold"]
        self.assertEqual(e["verdict"], "FAIL")
        self.assertIn("p95=2000.001 > 2000.0 ms", e["verdict_reasons"][0])

    def test_a_single_failure_fails_even_if_p95_is_under_target(self):
        for bad in ("timeout", "error", "content_unverified"):
            vals = [100.0] * 29 + [None if bad != "content_unverified" else 150.0]
            sts = ["ok"] * 29 + [bad]
            e = self._summ(_rows_for("update", vals, sts))["scenarios"]["update"]
            self.assertLessEqual(e["primary"]["p95"], 2000.0)  # 1 +inf queda en k=30
            self.assertEqual(e["verdict"], "FAIL", bad)
            self.assertIn("1 fallo(s)", e["verdict_reasons"][0])

    def test_two_failures_make_p95_infinite(self):
        sts = ["ok"] * 28 + ["timeout", "error"]
        e = self._summ(_rows_for("reload", [100.0] * 28 + [None, None], sts))
        e = e["scenarios"]["reload"]
        self.assertEqual(e["primary"]["p95"], math.inf)
        self.assertEqual(e["verdict"], "FAIL")

    def test_warmup_is_outside_the_calculation_but_a_failed_one_annuls(self):
        # Fuera del cálculo: no entra en n ni en el p95. Pero si falla, la corrida
        # queda anulada (M-1): el escenario NO puede salir PASS.
        rows = _rows_for("expand", [None], ["timeout"], role="warmup") + \
            _rows_for("expand", [100.0] * 30)
        summ = self._summ(rows)
        e = summ["scenarios"]["expand"]
        self.assertEqual(e["n_attempted"], 30)
        self.assertEqual(e["primary"]["p95"], 100.0)
        self.assertEqual(e["warmup_statuses"], ["timeout"])
        self.assertEqual(e["verdict"], "NO_EVALUABLE")
        self.assertEqual(e["verdict_without_annulment"], "PASS")
        self.assertTrue(summ["annulled"])
        self.assertIn("expand=timeout", e["verdict_reasons"][0])

    def test_ok_warmup_keeps_normal_verdict(self):
        rows = _rows_for("expand", [50.0], role="warmup") + _rows_for("expand", [100.0] * 30)
        summ = self._summ(rows)
        self.assertFalse(summ["annulled"])
        self.assertEqual(summ["warmup_failures"], [])
        self.assertEqual(summ["scenarios"]["expand"]["verdict"], "PASS")
        self.assertNotIn("verdict_without_annulment", summ["scenarios"]["expand"])

    def test_scenarios_are_not_pooled(self):
        rows = _rows_for("cold", [100.0] * 30) + _rows_for("update", [3000.0] * 30)
        s = self._summ(rows)["scenarios"]
        self.assertEqual(s["cold"]["primary"]["p95"], 100.0)
        self.assertEqual(s["cold"]["verdict"], "PASS")
        self.assertEqual(s["update"]["verdict"], "FAIL")

    def test_too_few_samples_is_not_evaluable(self):
        e = self._summ(_rows_for("cold", [100.0] * 29))["scenarios"]["cold"]
        self.assertEqual(e["verdict"], "NO_EVALUABLE")

    def test_missing_primary_is_not_evaluable(self):
        summ = h.summarize_rows(_rows_for("cold", [1.0] * 30), 95, None, None,
                                target_ms=2000.0, min_n=30)
        self.assertEqual(summ["scenarios"]["cold"]["verdict"], "NO_EVALUABLE")

    def test_no_target_no_verdict(self):
        e = h.summarize_rows(_rows_for("cold", [1.0]), 95, "linear", "ok_only")
        self.assertNotIn("verdict", e["scenarios"]["cold"])

    def test_overall_verdict(self):
        rows = [r for s in h.SCENARIOS for r in _rows_for(s, [100.0] * 30)]
        summ = self._summ(rows)
        self.assertEqual(h.overall_verdict(summ, h.SCENARIOS, 120, 120, None)[0], "PASS")
        self.assertEqual(h.overall_verdict(summ, h.SCENARIOS, 124, 120, None)[0],
                         "NO_EVALUABLE")
        self.assertEqual(h.overall_verdict(summ, h.SCENARIOS, 120, 120, "Ctrl-C")[0],
                         "NO_EVALUABLE")
        partial = self._summ([r for r in rows if r["scenario"] != "expand"])
        self.assertEqual(h.overall_verdict(partial, h.SCENARIOS, 120, 120, None)[0],
                         "NO_EVALUABLE")
        bad = self._summ(rows[:-1] + _rows_for("expand", [None], ["timeout"]))
        verdict, reasons = h.overall_verdict(bad, h.SCENARIOS, 120, 120, None)
        self.assertEqual(verdict, "FAIL")
        self.assertEqual(reasons, ["expand: FAIL"])


class WarmupAnnulmentRunTests(unittest.TestCase):
    """M-1 (Auditor, 961c879): veredicto del JSON con 120 muestras ok y un
    calentamiento no ok -> NO_EVALUABLE global y por escenario, exit code 1."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.out = Path(self._tmp.name) / "run"

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self, warm_failure):
        def sample(p):
            if p.role == "warmup" and p.scenario == "cold" and warm_failure is not None:
                if isinstance(warm_failure, BaseException):
                    raise warm_failure
                return warm_failure
            return _outcome(100.0)

        args = _args(*_PROTO)
        with mock.patch.object(h, "get_container_identities", return_value={}), \
                mock.patch.object(h, "run_negative_test_stale_dom", return_value=True):
            code = h.run_measurement(args, self.out, sample_fn=sample, log=_ListLog())
        summary = json.loads((self.out / "summary.json").read_text(encoding="utf-8"))
        return code, summary

    def _assert_annulled(self, warm_failure, status):
        code, summary = self._run(warm_failure)
        self.assertEqual(code, 1)
        self.assertEqual(summary["verdict"], "NO_EVALUABLE")
        self.assertTrue(summary["annulled"])
        self.assertEqual(summary["warmup_failures"],
                         [{"scenario": "cold", "iteration": 1, "status": status}])
        self.assertIn("cold=" + status, summary["verdict_reasons"][0])
        for s in h.SCENARIOS:
            e = summary["scenarios"][s]
            self.assertEqual(e["n_ok"], 30)  # las 120 muestras medidas, todas ok
            self.assertEqual(e["verdict"], "NO_EVALUABLE", s)
            self.assertEqual(e["verdict_without_annulment"], "PASS", s)

    def test_warmup_timeout_annuls(self):
        self._assert_annulled(TimeoutError("plazo"), "timeout")

    def test_warmup_error_annuls(self):
        self._assert_annulled(RuntimeError("botón ausente"), "error")

    def test_warmup_without_final_event_annuls(self):
        # «Sin evento final»: el arnés lo levanta como TimeoutError (p. ej. el
        # ranking nunca visible, o actualizar sin nueva marca de obtención).
        self._assert_annulled(TimeoutError("No se detectó el ranking visible tras 35 s"),
                              "timeout")

    def test_warmup_content_unverified_annuls(self):
        self._assert_annulled(_outcome(100.0, verified=False), "content_unverified")

    def test_ok_warmup_gives_normal_pass(self):
        code, summary = self._run(None)
        self.assertEqual(code, 0)
        self.assertEqual(summary["verdict"], "PASS")
        self.assertFalse(summary["annulled"])
        self.assertTrue(all(summary["scenarios"][s]["verdict"] == "PASS" for s in h.SCENARIOS))

    def test_overall_verdict_checks_annulment_first(self):
        summ = {"annulled": True, "annulment_reason": "corrida anulada: x", "scenarios": {}}
        self.assertEqual(h.overall_verdict(summ, h.SCENARIOS, 1, 1, None),
                         ("NO_EVALUABLE", ["corrida anulada: x"]))


class ProtocolRunTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.out = Path(self._tmp.name) / "run"

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self, sample):
        args = _args(*_PROTO)
        with mock.patch.object(h, "get_container_identities", return_value={}), \
                mock.patch.object(h, "run_negative_test_stale_dom", return_value=True):
            return h.run_measurement(args, self.out, sample_fn=sample, log=_ListLog())

    def _csv(self, name):
        with open(self.out / name, newline="", encoding="utf-8") as fh:
            return list(csv.DictReader(fh))

    def test_schedule_registered_before_first_sample_and_rows_follow_it(self):
        seen = {}

        def sample(p):
            if not seen:
                seen["schedule"] = self._csv("schedule.csv")
                seen["manifest"] = json.loads(
                    (self.out / "run_manifest.json").read_text(encoding="utf-8"))
            return _outcome(100.0)

        code = self._run(sample)
        self.assertEqual(code, 0)
        self.assertEqual(len(seen["schedule"]), 124)
        self.assertEqual(seen["manifest"]["schedule_sha256"],
                         h.sha256_file(self.out / "schedule.csv"))
        self.assertEqual(len(seen["manifest"]["schedule"]), 124)
        rows = self._csv("samples.csv")
        self.assertEqual([(r["seq"], r["scenario"], r["role"], r["iteration"]) for r in rows],
                         [(s["seq"], s["scenario"], s["role"], s["iteration"])
                          for s in seen["schedule"]])
        summary = json.loads((self.out / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["verdict"], "PASS")
        self.assertEqual({s: e["n_attempted"] for s, e in summary["scenarios"].items()},
                         {s: 30 for s in h.SCENARIOS})

    def test_one_timeout_in_30_fails_without_retry(self):
        calls = {"n": 0}

        def sample(p):
            calls["n"] += 1
            if p.role == "measure" and p.scenario == "update" and p.iteration == 7:
                raise TimeoutError("sin evento final")
            return _outcome(100.0)

        code = self._run(sample)
        self.assertEqual(code, 1)
        self.assertEqual(calls["n"], 124)  # sin reintentos sustitutos
        summary = json.loads((self.out / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["verdict"], "FAIL")
        upd = summary["scenarios"]["update"]
        self.assertEqual((upd["n_attempted"], upd["n_timeout"], upd["verdict"]),
                         (30, 1, "FAIL"))
        self.assertEqual(summary["scenarios"]["cold"]["verdict"], "PASS")

    def test_every_row_carries_order_date_versions_and_shas(self):
        def sample(p):
            if p.scenario == "reload" and p.iteration == 3 and p.role == "measure":
                raise RuntimeError("falla")
            return _outcome(100.0)

        self._run(sample)
        rows = self._csv("samples.csv")
        script = Path(h.__file__).resolve()
        for r in rows:
            self.assertTrue(r["seq"] and r["start_time_iso"] and r["end_time_iso"])
            self.assertEqual(r["system_sha"], "abc1234")
            self.assertEqual(r["candidate_sha"], "abc1234")
            self.assertEqual(r["harness_sha256"], h.sha256_file(script))
            self.assertTrue(r["harness_commit_sha"])
            self.assertIn(r["harness_dirty"], ("true", "false", "unknown"))
            self.assertTrue(r["python_version"] and r["platform"])
            self.assertEqual(r["protocol"], "kpi03-h3")
        self.assertIn("error", [r["status"] for r in rows])

    def test_existing_schedule_is_not_overwritten(self):
        self.out.mkdir(parents=True)
        (self.out / "schedule.csv").write_text("previo", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            self._run(lambda p: _outcome(1.0))
        self.assertEqual((self.out / "schedule.csv").read_text(encoding="utf-8"), "previo")

    def test_harness_dirty_flag(self):
        for out, expected in (("", "false"), (" M scripts/measure_browser_e2e_d21.py\n", "true")):
            with mock.patch.object(h.subprocess, "run",
                                   return_value=mock.Mock(stdout=out)):
                self.assertEqual(h.harness_is_dirty(REPO_ROOT), expected)
        with mock.patch.object(h.subprocess, "run", side_effect=OSError("git")):
            self.assertEqual(h.harness_is_dirty(REPO_ROOT), "unknown")


class _CapsDriver(_PanelDriver):
    def __init__(self, session_id=None, nav="navigate"):
        super().__init__()
        if session_id is not None:
            self.session_id = session_id
        self.nav = nav
        self.capabilities = {"browserName": "MicrosoftEdge", "browserVersion": "142.0.1",
                             "msedge": {"msedgedriverVersion": "142.0.1 (abc)"}}

    def execute_script(self, script, *args):
        if "navigation" in script:
            return self.nav
        return super().execute_script(script, *args)


class ColdInitialConditionTests(unittest.TestCase):
    def setUp(self):
        _PanelDriver.instances = []
        self.fc = _FakeClock()

    def _runner(self, factory):
        r = h.BrowserScenarioRunner("http://x", None, Path("."), "current", "none",
                                    driver_factory=factory, clock=self.fc.clock,
                                    sleep=self.fc.sleep)
        r.identity = {}
        return r

    def test_each_round_gets_a_fresh_browser_separate_from_the_session(self):
        runner = self._runner(_CapsDriver)
        for i in (1, 2, 3):
            runner(h.PlannedSample("cold", "measure", i))
            runner(h.PlannedSample("reload", "measure", i))
        colds = [d for d in _PanelDriver.instances if d.gets == 1 and d.quit_called]
        self.assertEqual(len(colds), 3)  # tres navegadores en frío, cada uno cerrado
        self.assertEqual(len(_PanelDriver.instances), 4)  # + 1 sesión compartida
        runner.close()

    def test_reused_browser_session_is_an_error(self):
        runner = self._runner(lambda: _CapsDriver(session_id="S1"))
        runner(h.PlannedSample("cold", "measure", 1))
        with self.assertRaises(RuntimeError) as cm:
            runner(h.PlannedSample("cold", "measure", 2))
        self.assertIn("reutilizada", str(cm.exception))

    def test_cold_requires_a_navigate_entry(self):
        runner = self._runner(lambda: _CapsDriver(nav="reload"))
        out = runner(h.PlannedSample("cold", "measure", 1))
        self.assertFalse(out.content_verified)
        self.assertIn("session=", out.method_detail)

    def test_browser_and_driver_versions_recorded(self):
        runner = self._runner(_CapsDriver)
        runner(h.PlannedSample("cold", "measure", 1))
        self.assertEqual(runner.identity["browser_version"], "MicrosoftEdge 142.0.1")
        self.assertEqual(runner.identity["driver_version"], "142.0.1")


if __name__ == "__main__":
    unittest.main()
