"""Regression tests for the E2E verifier, without Docker or HTTP services."""
import json
from argparse import Namespace
import pytest
from scripts import e2e_slice as e2e


def fixture_ranking():
    ranking = dict(forecast_time='2026-09-01T00:00:00Z', model_version='test',
        inputs_fingerprint='a'*64, schema_version='sapi-ranking-v0',
        score_semantics='relative_rank', scientific_model_validation=False, horizon_hours=6)
    ranking['cells'] = [dict(cell_id=f'VP-{i:03}', score=0.1, rank=i,
                            display_rank=1, tie_group_size=50) for i in range(1, 51)]
    rows = [['37', '2026-09-01 00:00:00+00', 'test', 'a'*64, 'sapi-ranking-v0',
             'relative_rank', 'f', '6', 'unused', c['cell_id'], '0.1', str(c['rank']),
             '1', '50'] for c in ranking['cells']]
    return ranking, rows


def test_http_sql_all_fields_match():
    ranking, rows = fixture_ranking()
    assert e2e.compare_rows(rows, ranking)


@pytest.mark.parametrize('index,value', [(0,'99'), (1,'2026-09-02T00:00:00Z'),
    (2,'wrong'), (3,'b'*64), (4,'bad-schema'), (5,'probability'), (6,'t'),
    (7,'12'), (9,'VP-051'), (10,'0.2'), (11,'2'), (12,'2'), (13,'1')])
def test_reject_divergent_sql(index, value):
    ranking, rows = fixture_ranking()
    rows[0][index] = value
    assert not e2e.compare_rows(rows, ranking)


def test_reject_partial_ranking():
    ranking, rows = fixture_ranking()
    assert not e2e.compare_rows(rows[:-1], ranking)


def test_elapsed_includes_body(monkeypatch):
    clock = [0]
    class Response:
        code = 200
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self):
            clock[0] = 3
            return b'ok'
    class Opener:
        def open(self, *args, **kwargs): return Response()
    monkeypatch.setattr(e2e.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(e2e.urllib.request, 'build_opener', lambda *args: Opener())
    assert e2e.http('GET', 'http://localhost')[2] == 3


def test_failed_start_never_reports_pass_or_removes_unowned_resources(tmp_path, monkeypatch):
    runner = e2e.Runner(Namespace(project_name='test', out_dir=tmp_path/'run',
        backend_port=1, ml_port=2, db_port=3, web_port=4, keep=False, node='node'))
    def fail(): raise RuntimeError('existing resources')
    monkeypatch.setattr(runner, 'start', fail)
    monkeypatch.setattr(runner, 'compose', lambda *a, **k: pytest.fail('Unowned cleanup'))
    assert runner.run() == 1
    report = json.loads((runner.out/'e2e_report.json').read_text())
    assert report['verdict'] == 'FAIL'
    assert report['completed'] is False
    assert (runner.out/'execution-error.txt').exists()
