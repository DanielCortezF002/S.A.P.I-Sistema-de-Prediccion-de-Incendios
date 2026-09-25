# FIRMS final cross-product reconciliation

This child of b6813ee restores explicit SP precedence over NRT for the established
legacy detection key: latitude/longitude rounded to five decimals, acquisition
date, zero-padded acquisition time, satellite and instrument. The legacy key
normalization is shared without changing historical backfill deduplication policy.

All source rows validate before reconciliation. An SP key removes every matching
NRT row independently of input order. Exact complete source-record repeats are
consolidated, while distinct same-source observations remain, including SP rows
differing only in `type`. That distinction remains in raw evidence; operational
projection preserves multiplicity even when projected rows are identical.

The writer and offline publication validator share this policy through candidate
construction. Canonical total ordering remains unchanged. Tests exercise reversed
source order, shuffled unrelated rows, normalized coordinates/time, duplicate
consolidation, raw type preservation, identical bytes/SHA/resolver content, TR-K
rejection before publication and NM-02 same-source tied observations.

This corrects the earlier remediation's overbroad claim that all distinct
cross-product rows should survive. Different FRP values do not override the
authoritative SP>NRT policy for the same normalized detection identity.

Passing tests is not independent approval. The exact child commit requires Claude
re-review before merge. No real writer, main merge, push or Attempt 2 is authorized.
