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
    return h.build_parser().parse_args(list(extra))


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


# ----------------------------------------------- 7) sleep(0.5) de expandir
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
        self.driver.clicked_at = self.driver.fake_clock.t


class _ExpandDriver:
    """Expander cuyo grid aparece ``appear_after`` segundos después del clic."""

    def __init__(self, fake_clock, appear_after=0.1, pre_open=False, pre_grid=False,
                 has_expander=True, global_grid=False):
        self.fake_clock = fake_clock
        self.appear_after = appear_after
        self.pre_open = pre_open
        self.pre_grid = pre_grid
        self.has_expander = has_expander
        self.global_grid = global_grid
        self.clicked_at = None

    def _grid_visible(self):
        if self.clicked_at is None:
            return self.pre_grid
        return self.fake_clock.t - self.clicked_at >= self.appear_after

    def find_elements(self, by, selector):
        if by == "xpath":
            return [_Summary(self)] if self.has_expander else []
        visible = self._grid_visible() or self.global_grid

        class _G:
            def is_displayed(self_inner):
                return visible

        return [_G()]

    def execute_script(self, script, *args):
        if "d.open" in script:
            return self.pre_open
        return self._grid_visible()


class ExpandMethodTests(unittest.TestCase):
    def test_current_method_has_no_fixed_sleep_in_interval(self):
        fc = _FakeClock()
        drv = _ExpandDriver(fc, appear_after=0.1)
        ms, detail = h.measure_expand(drv, "current", clock=fc.clock, sleep=fc.sleep)
        self.assertNotIn(h.LEGACY_EXPAND_SLEEP_S, fc.sleeps)
        self.assertLess(ms, 500.0)
        self.assertGreaterEqual(ms, 100.0)
        self.assertIn("expand_method=current", detail)

    def test_legacy_method_reproduces_sleep_inside_interval(self):
        fc = _FakeClock()
        drv = _ExpandDriver(fc, appear_after=0.1)
        ms, detail = h.measure_expand(drv, "legacy", clock=fc.clock, sleep=fc.sleep)
        self.assertEqual(fc.sleeps[0], 0.5)
        self.assertGreaterEqual(ms, 500.0)
        self.assertIn("expand_method=legacy", detail)

    def test_current_rejects_expander_already_open(self):
        fc = _FakeClock()
        with self.assertRaises(RuntimeError) as cm:
            h.measure_expand(_ExpandDriver(fc, pre_open=True), "current",
                             clock=fc.clock, sleep=fc.sleep)
        self.assertIn("Estado previo inválido", str(cm.exception))
        with self.assertRaises(RuntimeError):
            h.measure_expand(_ExpandDriver(fc, pre_grid=True), "current",
                             clock=fc.clock, sleep=fc.sleep)

    def test_legacy_reports_open_state_without_rejecting(self):
        fc = _FakeClock()
        ms, detail = h.measure_expand(_ExpandDriver(fc, pre_open=True), "legacy",
                                      clock=fc.clock, sleep=fc.sleep)
        self.assertIn("details.open=True", detail)

    def test_current_ignores_grids_outside_the_expander(self):
        fc = _FakeClock()
        drv = _ExpandDriver(fc, appear_after=10.0, global_grid=True)
        with self.assertRaises(TimeoutError):
            h.measure_expand(drv, "current", timeout=1.0, clock=fc.clock, sleep=fc.sleep)

    def test_missing_expander_and_unknown_method(self):
        fc = _FakeClock()
        with self.assertRaises(RuntimeError):
            h.measure_expand(_ExpandDriver(fc, has_expander=False), "current",
                             clock=fc.clock, sleep=fc.sleep)
        with self.assertRaises(ValueError):
            h.measure_expand(_ExpandDriver(fc), "old", clock=fc.clock, sleep=fc.sleep)

    def test_default_expand_method_is_current_and_cli_validates(self):
        self.assertEqual(_args().expand_method, "current")
        self.assertEqual(_args("--expand-method", "legacy").expand_method, "legacy")
        with mock.patch("sys.stderr"), self.assertRaises(SystemExit):
            _args("--expand-method", "sleepy")


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

    def execute_script(self, script, *args):
        if "arguments[0].click()" in script:
            args[0].click()
            return None
        if "d.open" in script:
            return self.opened
        if "querySelectorAll(arguments[1])" in script:
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
        self.assertLess(out.latency_ms, 500.0)
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


if __name__ == "__main__":
    unittest.main()
