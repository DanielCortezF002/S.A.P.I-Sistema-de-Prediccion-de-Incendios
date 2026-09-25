# Attempt 2 Operator

Coordinates the controlled Attempt 2 path. **Does not** auto-run FIRMS/DMC writers, Telegram, schedule, Jira, or git merge.

## Entry points

```powershell
python -m src.ops.attempt2_operator --help
python scripts/attempt2_operator.py --help
```

## Initialize

```powershell
python -m src.ops.attempt2_operator --dry-run init --expected-code-sha <sha> --evidence-root "D:\portafolio y seminario\SAPI-71-evidence\attempt2"
```

Creates `SAPI-ATTEMPT2-YYYYMMDD-HHMMSS/` with `state.json`, `events.jsonl`, `authorizations.json`, `manifest.json`.

## See next action

```powershell
python -m src.ops.attempt2_operator next --run <run_dir>
python -m src.ops.attempt2_operator next --run <run_dir> --advance
```

## Authorize a gate

Explicit only — never inferred from env/files/old evidence:

```powershell
python -m src.ops.attempt2_operator authorize --run <run_dir> --gate ATTEMPT2_AUTHORIZATION
python -m src.ops.attempt2_operator authorize --run <run_dir> --gate FIRMS_WRITER_AUTHORIZATION
```

Gates: `ATTEMPT2_AUTHORIZATION`, `FIRMS_WRITER_AUTHORIZATION`, `DMC_WRITER_AUTHORIZATION`, `TELEGRAM_AUTHORIZATION`, `SCHEDULE_AUTHORIZATION`.

Telegram/schedule gates exist but Attempt 2 stops before using them for send/enable.

## Import manual results

After you run the protected command yourself:

```powershell
python -m src.ops.attempt2_operator import-result --run <run_dir> --phase firms --from firms_payload.json
```

Phases: `firms`, `dmc`, `scoring`, `bridge`, `n8n`.

## Failure

Invalid transitions → exit 3. Unauthorized writer → exit 4. Validation fail → state `*_FAILED` / `STOPPED`; no auto continue.

## Resume after crash

```powershell
python -m src.ops.attempt2_operator status --run <run_dir>
python -m src.ops.attempt2_operator next --run <run_dir>
```

State is fully on disk (`state.json` + `events.jsonl`).

## What it never automates

- `firms_refresh` / `dmc_refresh`
- Telegram send
- Schedule enable
- Jira writes
- Git merge
- Production model / Hito1 changes
- Real CURRENT store writes (operator only records imported evidence)

## Existing tooling reused

Wrappers integrate concepts from Cursor evidence packs under `SAPI-71-evidence/planning/`:

- attempt2-preflight-tools (snapshot/validate semantics)
- attempt2-evidence-tools (FIRMS/DMC phase validation, import, custody)
- tooling-integration-rehearsal/adapter (`UNKNOWN≠ABSENT`, auth never false→true)

Operator embeds the decision logic needed for the state machine; optional live tool roots can be pointed via env in later integration without changing the CLI.
