# Data Plane RC1 contract for Operations

The candidate composes FIRMS final fix `5a92419c7b1a2463d7870556658abd11087676f4`
and DMC probe `a4bab186493ea9fe747d5904706a803d267d4ed4`. Original branches and
the former CI commit remain preserved. FIRMS requires independent review of the
exact final SHA; the earlier `95e3174` checkpoint is not the final review target.
Integration commit `616841a947c3061a9263c7f42c04cec76d56c12a` additionally fixes
ScoringInputs' versioned-only DMC path: when legacy is empty, preserve the parsed
datetime/numeric dtypes instead of concatenating with an untyped empty frame.
The original DMC branch is unchanged; policy binds this integration component
separately. A regression and the clean-store E2E exercise the corrected path.

## Read-only command

From the candidate checkout, run:

```powershell
python -m src.ops.data_readiness --workspace-root '<operational workspace>' --dmc-evidence '<sanitized live-result.json>'
```

Add `--manifest` to print a DATA_PLANE_MANIFEST instead. No output path is accepted:
capture stdout only into the approved evidence directory. No network requests,
writers, inference, CURRENT writes, or database calls are performed. Credentials
are reported as presence booleans only. Exceptions produce fixed finding codes;
all output strings pass through project redaction.

Policy lives in `config/data_plane_rc1.json`. It pins component commits and their
source files, model, baseline, Attempt1 raw evidence, existing operational DEM
rasters/grid/derived table, and the sanitized DMC observation's file hash.
Git ancestry, component blobs and clean candidate worktree are checked. Operational
data is read from the explicitly supplied workspace, independently of code checkout.
No automatic fallback to frozen inputs, substitute meteorology or another workspace.

Exit codes: 0 PREPARED, 65 NOT_PREPARED, 78 INCOMPLETE. Unknown never passes.
PREPARED means the pinned implementation/artifacts satisfy preparation policy.
It does **not** mean approval, fresh sources, operational scoring readiness or
permission to execute Attempt 2. Default pre-Attempt2 policy expects both CURRENTs
ABSENT. Present pointers are validated before the policy mismatch is reported;
FIRMS uses the production publication validator, DMC uses verified monthly payload
preparation and ScoringInputs parsing. Both raw/processed inventories are hashed
before and after observation; concurrent changes make the result INCOMPLETE.

The earlier DMC observation is historical evidence, not a new health check. Its
scope is one monthly payload against empty prior state. FIRMS is not re-probed.
The operational topography has existing missing values: identity verification
does not assert complete terrain coverage or scientific validity. No geometry,
features, model, target definition or score meaning is changed.

## Machine interface

Readiness schema v1 contains `code_identity`, `firms`, `dmc`, `model`, `topography`,
`stores`, `current_state`, `findings`, `status`, and observation start/end times.
`firms.current.state` and `dmc.current.state` are PRESENT/ABSENT/INVALID/UNKNOWN.
The DMC evidence includes its original observation time, coverage, usable record
count and null percentage. `data_ready_for_scoring` stays NOT_EVALUATED: the gate
does not run the operational scoring capture or model.

Manifest schema v1 has `identity`, `fingerprint`, `created_at`, `observation` and
`operational_roots`. Fingerprint recipe:

```python
sha256(json.dumps(identity, sort_keys=True, separators=(",", ":"),
                  ensure_ascii=True, allow_nan=False).encode()).hexdigest()
```

Creation/observation clocks and machine-specific workspace/code roots are outside
stable identity. The historical source observation time is inside evidence and
does not change on regeneration. File identities remain byte-exact; existing
CURRENT files can themselves contain absolute raw paths, so moving a published
store may legitimately require new identities. The manifest is not a signature.
Operations must trust the approved candidate SHA/policy and expected fingerprint,
not a manifest supplied by an untrusted party merely because its checksum matches.

Consumers can import `verify_manifest` to check schema, checksum, status coherence
and absence of authorization. Then compare component SHAs, root policy and
expected CURRENT state with the intended operator workspace. Every authorization
flag (`attempt2`, `writers`, `telegram`, `schedule`) is false. Independent approval
remains PENDING. Run a separate current operational preflight and obtain explicit
authorization before writers; do not infer either from PREPARED.

## Synthetic integration evidence

`tests/test_data_readiness.py` publishes synthetic FIRMS and DMC via production
writers into temporary stores, captures real ScoringInputs, compares its input
fingerprint, then evaluates readiness. Only synthetic policy expects PRESENT.
It checks bad inputs, missing/wrong identities, altered pointers and version
bytes, unknown states, source-evidence hash mismatch, concurrent store changes,
secret suppression, write prohibition, deterministic manifest identity and tamper
detection. No real Model D inference or real store publication is needed.

These are software contract tests, not scientific validation of the exploratory
Model D ranking. This candidate changes no other agent's branch, n8n, Telegram,
Jira, main or remote repository.
