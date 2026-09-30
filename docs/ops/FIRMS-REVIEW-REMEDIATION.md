# SAPI-71 — TR-K / NM-02 remediation

Reviewed parent: `3b8f5a14b6e3a99ae9ae83c1b76d4a933360e6b3`.
Scope: missing mixed-window regression and deterministic v3 serialization only.

TR-K now exercises a valid SP window followed by NRT missing each required
detection field, or carrying an unexpected `type`. Every case must fail with
exit 65, with no partial version, sidecar or history and CURRENT absent/unchanged.
Both absent and already-published synthetic CURRENT states are covered.

NM-02 had two causes: a stable but incomplete sort key and legacy backfill's
keep-first deduplication by sensor/time/position. Three input permutations gave
three publication hashes and retained only one of three distinct observations.

The v3 publication and its offline rebuilding validator now retain **every distinct**
validated source record, including SP/NRT overlaps. Only exact full-record
repetitions are consolidated, preserving the existing duplicate-response contract;
SP type and provenance participate in that equality check before projection.
Raw bytes retain all repetitions. Neither path calls the legacy keep-first
deduplicator. The historical backfill helper and
its existing SP preference are unchanged. This deliberately corrects loss of
observations in new v3 deltas; it does not rewrite existing baseline/version
bytes or change feature/scoring algorithms. Counts of previously discarded
observations can therefore differ from the defective publication path.

The order is `(acq_date, numeric acq_time, numeric latitude, numeric longitude,
full persisted token tuple in OPERATIONAL_COLUMNS order)`. The final tuple
includes original textual tokens and provenance. No input index, arrival order,
clock or scientific preference chooses a winner. Exact identical tuples have
identical bytes regardless of their positions. Distinct SP records that differ
only in type remain distinct before projection, with classification kept in raw.
SP classification stays in original raw/baseline; NRT never gains `type`.

Regression tests compare original, reversed and third-permuted input: version
bytes/SHA, resolved content, row multiset and content identity. Complete pointer
and sidecar bytes are also compared with raw bytes/path/clock frozen. When raw
responses themselves are permuted, their byte hashes and per-store paths must
differ: these provenance fields are verified, not falsely claimed identical.

All new tests use temporary synthetic stores and blocked sockets. No real
refresh, CURRENT, Attempt 1 evidence, model, Hito1, bridge or operational store
is written. This change requires independent re-review and does not authorize
Attempt 2, merge or deployment.
