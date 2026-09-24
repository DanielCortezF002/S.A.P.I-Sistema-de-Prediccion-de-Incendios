# FIRMS live-schema failure — diagnosis and proposed separate correction

Attempt 1 status: FAILED — MANUAL INTERVENTION REQUIRED (closed).
Attempt 2: NOT STARTED. This branch implements the offline fix; it does not
authorize a new operation, deployment, or merge.
Base: origin/main 7ef8d3c9f7ecb4758718255b8e48d6468f8613ea.
Do not rerun FIRMS, run DMC, send Telegram, or roll back this failed attempt.

## Observed failure

Human attempt 2026-09-24, raw run 20260924T180743Z: exit 65 in 6.6 s.
`build_version_bytes()` rejects missing `type` after five raw downloads.
No CURRENT, history, version, or residual lock was found. Store inventory:
458 original files unchanged, 5 added raw CSVs, 0 removed, 0 modified.
Classification: PUBLICATION/PARTIAL MUTATION DETECTED (raw additions only).
There is no published version to roll back. Preserve raw files as evidence.

Actual source: VIIRS_SNPP_NRT (Suomi NPP, not NOAA-20).
Sanitized endpoint template:
`https://firms.modaps.eosdis.nasa.gov/api/area/csv/[REDACTED]/VIIRS_SNPP_NRT/-71.75,-33.65,-70.25,-32.0/{days}/{start}`.
Five requested windows span 2026-08-31 through 2026-09-23; 85 returned rows
span 2026-09-02 through 2026-09-22. Request coverage is not detection coverage.
Exact HTTP status and Content-Type were not retained by the client and cannot
be recovered from the CSVs. The code passed `raise_for_status()` and CSV parsing;
this does not establish an observed HTTP 200 or an observed Content-Type.

## Source contract and origin of type

Live columns, in order:
`latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,instrument,confidence,version,bright_ti5,frp,daynight`.

The baseline has these 14 plus `type,firms_source,request_start_date`.
The ingestion client adds the last two provenance fields before the failing check.
Thus missing at the failing boundary: `type`; extra: none. Comparing the raw
response directly with the baseline also lacks the two locally generated fields.

[NASA S-NPP attributes](https://firms.modaps.eosdis.nasa.gov/content/descriptions/FIRMS_VIIRS_Firehotspots.html)
restrict `type` to VNP14IMGT standard quality. It classifies inferred hotspot
type, not a value inferable from the NRT `confidence` or `version` field.
[NASA Area API](https://firms.modaps.eosdis.nasa.gov/api/area/) distinguishes
VIIRS_SNPP_SP from VIIRS_SNPP_NRT. [NASA's S-NPP example](https://firms.modaps.eosdis.nasa.gov/content/academy/data_ingest/firms_data_ingest.html)
also uses 14 columns.

Historical raw SP already contains `type`; historical raw NRT does not.
The backfill concatenated the schemas with pandas and retained the union in
the frozen baseline: 12,203 SP rows (7,130 type 0; 5,066 type 2; 7 type 3),
274 NRT rows with empty type, total 12,477. This is not a new upstream schema
change established today. It is a mismatch between two established products
and the refresh's assumption that every baseline column is a live requirement.
No evidence of an SAPI-derived hotspot classification was found.

Model D does not select, filter, or engineer features from `type`:
`prototype_service.build_feature_matrix` -> `assign_episodes` ->
`first_arrival_by_cell` -> `historial_firms_features`; model columns are
`scripts/experiment_abcd.py::FEATURES_D`, not raw FIRMS columns.
`type` is retained source information, not a Model D input. This does not
authorize retraining, filtering historical type 2 rows, or changing Hito1.

Existing `tests/test_firms_refresh.py::FakeFirms` gave NRT an artificial
`type=0`; the validator self-test imports that fixture. Those tests exercised
publication mechanics but not the real source schema.

## Implemented contract

`src/ingesta/firms_schema.py` defines `viirs-snpp-common-v1` independently
of the baseline header:

- NRT: exactly the 14 common columns. Extra fields, including `type` and
  caller-supplied provenance, are rejected. Reordered headers are accepted
  and canonicalized. RT/URT suffixes are valid documented variants of the
  NRT endpoint and remain explicit in `version`.
- SP: the 14 common columns plus the original `type` (0/1/2/3). No classification
  is inferred. Historical/raw SP retains it; the common operational view does
  not claim to include that classification.
- SAPI provenance: only `firms_source` and `request_start_date` are appended
  after source validation. They are not original scientific API attributes.

Each response is checked BEFORE raw persistence or concatenation: field set,
duplicate headers, row width, numeric finiteness/ranges, date/time, sensor,
confidence/daynight categories, product version and requested date bounds.
Empty payloads fail; a valid header-only response records a consulted window
with zero detections. A missing common field cannot be masked by an SP window.
The client preserves complete raw SP/NRT CSVs with immutable writes and hashes.

`build_version_bytes` projects verified historical or current data to the
14 common columns plus 2 provenance columns. Original field tokens and row
order of the base are preserved in the projection; original baseline bytes
are never changed. New rows sort stably by date, numeric acquisition time,
latitude and longitude, with explicit LF CSV serialization. Dates must be
strictly after previous requested coverage and within new requested coverage.
A repeated v3 projection is byte-identical. No new type field is added and no
missing classification is filled. Existing structural blanks in a mixed
historical input are recognized only to validate that input before projection.

## Pointer version and provenance

New publications use pointer **v3** and `data_contract=viirs-snpp-common-v1`.
A version change is necessary: the CSV is now a declared projection, not an
exact byte-prefix of a 17-column baseline. Silently calling it v2 would hide
that semantic change. Existing v2 pointers remain readable and rollback
compatible; unknown schemas/contracts fail closed. The frozen fallback and
reproducibility paths are unchanged. No migration of existing data is run.

Existing pointer fields remain; new provenance fields are:
`base_relative_path`, `projected_base_sha256`, `raw_artifacts` (paths and
SHA256 of the complete original responses), and `data_contract`.
`base_sha256` continues to identify the original base, not its projection.
Original SP classification remains retrievable in the original baseline or
hashed raw source, with no loss from those files. Subsequent manifests link
the prior immutable version by path/hash. Raw files are not cleanup targets.

The operational CSV intentionally excludes SP-only classification. This view
is for the unchanged Model D/episode/arrivals/history pipeline, which does
not use type. No filtering, retraining, target change, calibration or change
to Hito1 is implied. `firms_origin`, coverage, lag, status and inputs fingerprint
continue through resolver/ScoringInputs. Changed operational input bytes
legitimately produce a different input fingerprint; the frozen ranking
fingerprint must remain exactly
`33c2eacc49bd0cc130928b5bd182ec523e63614f0e3dd97a129a8d4657f231ff`.

Serialization/content hashes are deterministic for equal data. Whole manifests
are deterministic for equal inputs including clock and raw locations, tested
with a fixed clock. Real `created_at`/run locations remain actual provenance;
no claim of identical manifests across different runtime inputs is made.

## Version-controlled offline gate

`scripts/validate_firms.py` is the new read-only v3 gate. It delegates to
`src/refresh/firms_validation.py` and prints ACCEPTED/REJECTED without writes.
It verifies baseline/base hashes, projected-base hash, source raw hashes and
strict schemas, complete requested-window coverage, deterministic rebuild of
the entire CSV, row counts, CURRENT/sidecar/history agreement and lock absence.
The source resolver validates v3 contract/metadata, canonical CSV, coverage
and content hash; it retains the v2 reader. The full forensic raw reconstruction
belongs to the offline gate rather than every scoring call.

The old Attempt 1 validator and evidence are preserved unmodified. A future
operational gate must still verify the complete store inventory, original
command exit/output and absence of consumers; CSV validation alone does not
establish those external conditions. A passing self-test is not an operation.

## Validation and restart conditions

Tests use a header-only fixture with the real observed 14-column shape and
clearly synthetic rows. No new real API data is used. Test sockets are blocked
for the source/normalizer/refresh suites. Coverage includes required/extra/
duplicate fields, malformed/invalid values, SP preservation, NRT without type,
empty windows, deterministic content/manifest, second generation, tampering,
v2 compatibility, v3 resolver/scoring metadata and the exact ranking fingerprint.
NRT fixtures previously containing a manufactured type=0 have been corrected.

Validation commands and actual counts are recorded outside Git in the fix
validation evidence and in the prepared PR body; no operational data or secret
belongs to this branch. Existing immutable Hito1 snapshot tests remain in use.

Attempt 1 remains CLOSED with its original three outputs and five raw files.
No rollback was needed because nothing was published. Only after tests,
review and merge to a new main SHA may Attempt 2 be considered: new evidence,
new pre-flight, inventory baseline = actual post-Attempt-1 state (463 files,
including the five preserved raw files), and new explicit human authorization.
Attempt 2 is NOT STARTED and no real refresh command is prepared here.
