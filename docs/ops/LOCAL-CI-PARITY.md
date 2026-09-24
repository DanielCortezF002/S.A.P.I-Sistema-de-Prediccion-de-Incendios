# Local CI parity — fallback evidence

Base: `7ef8d3c9f7ecb4758718255b8e48d6468f8613ea`. This lane is independent of
the FIRMS fix, bridge and scientific validation. No workflow changes.

## Run

Use a separate clean checkout, Python 3.14 and an isolated virtual environment:

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest tests/test_ci_local.py -o addopts= -q
python scripts/ci_local.py --host --output D:\evidence\new-host-run
python scripts/ci_local.py --fast --output D:\evidence\new-fast-run
python scripts/ci_local.py --docker --output D:\evidence\new-docker-run
python scripts/ci_local.py --all --output D:\evidence\new-all-run
```

Each output directory must be new and outside the checkout. The harness writes
sanitized logs, `run-result.json`, `run-summary.md`, `commands.txt` and a SHA-256
`evidence-manifest.json`. It never installs dependencies into the host environment.
Record any reuse of an existing environment separately; installed direct pins and
Python version are checked and recorded. Dependency resolution is not a lockfile.

## Existing workflow contract

`.github/workflows/ci.yml` runs on push and pull requests targeting `main` or
`develop`, with `ubuntu-latest`, Python `3.14` and PostGIS `postgis/postgis:15-3.4`.
All commands use the repository root. Its seven steps are mapped in
`ci-parity-map.json`; the parser checks YAML, supported workflow/config digests,
referenced directories, requirement files and SQL files. A changed contract
requires review/update of the map and fails with `CI_PARITY_GAP` meanwhile.

| CI step | Command or action |
| --- | --- |
| Checkout | `actions/checkout@v4` |
| Python | `actions/setup-python@v5`, Python 3.14 |
| Dependencies | `python -m pip install --upgrade pip`; `pip install -r requirements-dev.txt` |
| Schema | apt installs `postgresql-client`; ordered loop over `docker/initdb/*.sql` invoking psql |
| Format | `black --check src app tests` |
| Lint | `flake8 src app tests --max-line-length=100 --extend-ignore=E203,W503` |
| Tests | `pytest`, inheriting `pytest.ini` |

Environment names: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`,
`DATABASE_URL`, `DATABASE_URL_DIRECT`, `PGPASSWORD`. Values are not evidence.
`pytest.ini` collects `tests`, covers `app` and `src`, reports missing lines and
requires **80%**. There is no dedicated CI secret scan, artifact verification or
application Docker build. CI does use a Docker PostGIS service.

YAML/path validation is not GitHub's hosted workflow validation. No concrete
workflow defect explaining zero runs was confirmed. The SQL loop has no
`ON_ERROR_STOP` or explicit fail-fast shell option; this is a review limitation,
not an observed execution failure or an explanation for zero runs.

The initial local static check on this base found 86 files that Black would
reformat and 231 flake8 findings. The CI gate must report those failures even
when pytest passes. This lane leaves those pre-existing files unchanged.

## Gate semantics

Exit 0 = `LOCAL_GATE_PASS`; 1 = `LOCAL_GATE_FAIL`; 2 = `LOCAL_GATE_INCOMPLETE`.
A failed command/hash/secret check is FAIL. An unknown state, dirty checkout,
missing required capability or missing report prevents PASS. Dirty results record
HEAD and its committed tree, explicitly **not** the complete executed dirty bytes.
`merge_authorization` is always false; result validation rejects inconsistent states.

Fast runs static checks, frozen fingerprint and focused harness tests; the full
suite remains NOT_RUN, so fast cannot grant canonical PASS. Host runs the complete
suite even when format/lint fails, preserving all evidence. Host PostGIS setup is
BLOCKED and required for full parity, so otherwise successful host evidence remains
INCOMPLETE. Missing optional ignored operational datasets are separately BLOCKED
but non-gating under `verify_reproducibility.py`'s existing contract. A missing
tracked frozen artifact fails, as the existing contract requires it to exist.

The frozen FIRMS snapshot is checked against the baseline reference hash; this
does not prove the identity of an absent operational baseline. Model and ranking
fingerprints are pinned independently. Hito1 is compared with this lane's base:
only “changed by this lane?” is assessed, with no claim about earlier history.
Scoring uses frozen inputs and never refreshes. The secret scan is heuristic,
read-only and redacted: text files tracked/unignored plus ignored dotenv files,
no binary scan or full Git-history scan. Exact reviewed fixture values and
environment-variable placeholders are excluded; changed values are rescanned.

## Docker and safety

`--docker` requires Docker; unavailable means BLOCKED/INCOMPLETE. In `--all`,
unavailable Docker stays visibly BLOCKED but optional; an executed Docker failure
still fails the gate. No silent host fallback. The harness does not start or repair
Docker Desktop. It builds from a clean commit's `git archive`, rejects archive
links, and never mounts a real store or launches Compose/n8n/bridge/web.

The image extends `Dockerfile.analytics` with git for isolated identity tests and
overrides the daily-loop entrypoint. Dependency builds may download packages;
runtime uses a unique internal Docker network with no published ports. PostGIS
has ephemeral storage and fixture trust authentication only on that internal
network. Its schema is initialized in CI order. Unique test containers/network
are removed in a finally block; cleanup failure remains visible. Image/build
cache and archived evidence are retained. There is no operational volume access.

Host children receive a minimal environment with dotenv disabled, isolated home,
and a Python socket guard denying connections (except stdlib's own Windows
socketpair). This is a safety constraint, not a hostile-code security sandbox.
Docker uses internal networking instead. Linux image/system packages, host network
guard, extra machine report flags and unavailable real datasets are explicit
parity gaps; tests are not edited or skipped merely to make this gate green.

## GitHub relationship and remaining human action

**LOCAL CI PASS != GITHUB ACTIONS PASS. LOCAL FALLBACK EVIDENCE only.**
The historical observation was zero Actions runs; this lane neither rechecks nor
resolves its cause. Daniel must inspect Actions availability/permissions and
eligible event/ref history, then obtain an actual hosted run. No settings,
permissions, branch protection, remote comments, push or merge are performed here.
Historical test counts on other revisions are not results for this checkout.
