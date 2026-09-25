# DMC live contract probe

Run `python -m src.ops.dmc_live_probe --month 2026-09` with existing
`DMC_USUARIO` and `DMC_TOKEN` configuration. This makes one monthly request for
station 330007 through the same `getDatosRecientesEma` interface as the writer.
There are no retries or redirects. The response stays in memory; only a sanitized
JSON summary is printed. No publication paths are accepted. Do not run this command
repeatedly as a monitoring job without separate authorization.

The probe uses `prepare_month_payload`, also used by the production writer:
structure and timestamps, required numeric fields, exact monthly null threshold,
merge, canonical bytes, and the scoring parser's row-count invariant. The parser
now consumes bytes directly through its existing shared core, avoiding temporary
files. Explicit null rows up to and including 1% are allowed; more than 1%, missing
fields and invalid numbers are rejected. Values are never fabricated.

This is a **monthly candidate validation dry run against empty prior state**.
It does not inspect CURRENT, existing versions, permissions, locks, freshness or
other months. COMPATIBLE means the writer's payload preparation accepts this
candidate, not that a full refresh or Attempt 2 is approved. The writer can skip an
empty current month during its existing first-six-hours grace period; the probe
reports empty data as unusable rather than claiming compatibility.

Statuses and exit codes: COMPATIBLE/0, INCOMPATIBLE/65,
NETWORK_UNAVAILABLE/69, CONFIG_MISSING/78, INCOMPLETE/2. Unknown is never success.
The report distinguishes received coverage from accepted candidate coverage.
HTTP diagnostics contain status, media type, byte count and observation time;
request URLs, headers, credentials and response values are never dumped. All
reported strings pass through project redaction. Non-200 responses are not parsed.
The response limit is 16 MiB; connection/read timeouts are 5/20 seconds, with a
30-second elapsed guard checked between chunks (not a hard wall-clock deadline).

For equivalent unique timestamps, canonical identity is independent of input
ordering. Conflicting duplicates retain the writer's existing first-incoming
semantics and receive an explicit order-sensitive finding. There is no additional
physical-range or station-metadata validation beyond the production contract.

Synthetic tests prohibit socket access, file mutations and writer/publication
entrypoints, exercise threshold boundaries and redaction, and pass an accepted
candidate through real ScoringInputs without invoking Model D. Live evidence may
be captured only under `D:\portafolio y seminario\SAPI-71-evidence\`.
This command never authorizes or executes DMC/FIRMS publication, Model D on new
live data, Telegram, n8n changes, schedules, or Attempt 2.
