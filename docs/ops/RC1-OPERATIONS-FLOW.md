# SAPI Operations Plane RC1 — Operational Flow & Execution Guide

## Overview

This document specifies the authoritative operational flow for executing **Attempt 2** using the **Release Candidate 1 (RC1)** Operations Plane execution toolchain.

The toolchain integrates:
- **Canonical Operational Workspace Materializer** (`src/ops/operational_workspace.py`)
- **Workspace Safety Guard** (`src/ops/workspace_safety.py`)
- **Attempt 2 Operator & State Machine** (`src/ops/attempt2_operator/operator.py`)
- **Quiescence Engine** (`src/ops/attempt2_operator/quiescence/`)
- **Readiness Manifest Contracts**:
  - Workspace Manifest (`WORKSPACE-MANIFEST.json`)
  - Data Plane Manifest (`DATA-PLANE-MANIFEST.json`)
  - Output Plane Manifest (`OUTPUT-PLANE-MANIFEST.json`)
- **RC1 Diagnostic Command** (`python -m src.ops.attempt2_operator rc-status`)

> [!IMPORTANT]
> **Strict Operational Boundary**:
> Automated tools NEVER perform live refresh, container starts/stops, message dispatch, or store mutations without human action.
> Real execution remains strictly human-gated at all times.

---

## Architecture of the RC1 Operations Plane

```mermaid
flowchart TD
    A["1. RC1 Git SHA (Main)"] --> B["2. Operational Workspace Materializer"]
    B --> C["WORKSPACE-MANIFEST.json"]
    C --> D["3. Workspace Safety Guard (OPERATIONAL_REAL_DATA)"]
    D --> E["4. External Data Readiness Manifest"]
    E --> F["5. Attempt 2 Operator Init (expected_code_sha)"]
    F --> G["6. Preflight Assessment & Quiescence Evaluation"]
    G --> H{"Quiescent & All Guards Pass?"}
    H -- No --> H_Fail["PREFLIGHT_FAILED (Safe Stop)"]
    H -- Yes --> I["7. Human Authorization Gate (ATTEMPT2_AUTHORIZATION)"]
    I --> J["8. Manual FIRMS Writer Refresh (Human Execution)"]
    J --> K["Import & Validate FIRMS Evidence"]
    K --> L["9. Manual DMC Writer Refresh (Human Execution)"]
    L --> M["Import & Validate DMC Evidence"]
    M --> N["10. Scoring Inference Execution & Evidence Import"]
    N --> O["11. Consumer / Output Plane Acceptance"]
    O --> P["12. Final Operational Acceptance (ACCEPTED)"]
```

---

## Step-by-Step Execution Sequence

### Step 1: Human Creation & Selection of RC1 Code SHA
The human operator identifies the authoritative git commit SHA intended for RC1 execution:
```bash
export RC1_CODE_SHA="<authoritative_40_char_sha>"
```
No run may proceed with an unknown or drifting SHA.

### Step 2: Canonical Operational Workspace Materialization
The operator materializes an isolated, verifiable operational workspace using the materializer tool:
```bash
python -m src.ops.operational_workspace materialize \
    --source-repo . \
    --target-dir ./workspaces/operational-rc1 \
    --sha "$RC1_CODE_SHA"
```
This produces:
- Clean code worktree checked out at `$RC1_CODE_SHA`.
- Verified store structure (`data/raw`, `data/processed`).
- Signed and fingerprinted `WORKSPACE-MANIFEST.json`.

### Step 3: Workspace Safety Guard Evaluation
Before any process touches the operational workspace, the safety guard validates the environment under `OPERATIONAL_REAL_DATA` mode:
```bash
python -m src.ops.workspace_safety check \
    --workspace ./workspaces/operational-rc1 \
    --mode OPERATIONAL_REAL_DATA \
    --json
```
**Safety Invariants**:
- Symlinks / NTFS reparse points / junctions are strictly forbidden (`TOPOLOGY_SAFE`).
- Uncommitted changes in the materialized workspace cause immediate `FAIL`.
- Source store integrity must be verified (`ow.verify()`).
- `INCOMPLETE` or `NOT_AVAILABLE` status must never be promoted to `PASS`.

### Step 4: External Data Readiness Manifest Generation
The data engineer or human operator establishes the data readiness manifest linking raw/processed sources:
- FIRMS raw Parquet and pointer status.
- DMC meteorological dataset status.
- Frozen model artifact (`models/model.pkl` or baseline artifact).
- Hito 1 validation benchmarks.

The resulting `DATA-PLANE-MANIFEST.json` contains SHA-256 fingerprints of all inputs and states `readiness: READY`.

### Step 5: Operator Run Initialization
Initialize the Attempt 2 Operator run directory:
```bash
python -m src.ops.attempt2_operator init \
    --expected-code-sha "$RC1_CODE_SHA" \
    --workspace-manifest ./workspaces/operational-rc1/WORKSPACE-MANIFEST.json \
    --data-manifest ./manifests/DATA-PLANE-MANIFEST.json
```
This creates:
- `identity/run.json`
- `identity/rc1_execution_context.json`
- Initial operator state `NEW`.

### Step 6: Preflight & Quiescence Evaluation
Run the automated preflight collection and validation:
```bash
python -m src.ops.attempt2_operator preflight
```
The quiescence engine inspects:
1. **Processes & Writers**: No active Python refresh processes (`firms_refresh`, `dmc_refresh`).
2. **Locks**: No active `.refresh.lock` files in `data/processed/firms` or `data/processed/dmc`.
3. **Container State**: Under `FIRST-CONTROLLED-REFRESH` policy, the n8n container must be **STOPPED**.
4. **Telegram**: Path must be verified `DISARMED`.
5. **Schedule**: Cron / activation schedules must be absent or disabled.

If all preflight checks pass, state transitions to `PREFLIGHT_READY`. Otherwise, state transitions to `PREFLIGHT_FAILED`.

### Step 7: Human Authorization Gate
Advancement to writer phases requires explicit human cryptographic or logged authorization:
```bash
python -m src.ops.attempt2_operator authorize \
    --gate ATTEMPT2_AUTHORIZATION \
    --actor "Daniel Cortez"
```
State transitions: `PREFLIGHT_READY` -> `ATTEMPT2_AUTHORIZATION_REQUIRED` -> `ATTEMPT2_AUTHORIZED`.

### Step 8: Manual FIRMS Writer Refresh
1. Human authorizer issues FIRMS writer token:
   ```bash
   python -m src.ops.attempt2_operator authorize --gate FIRMS_WRITER_AUTHORIZATION --actor "Daniel Cortez"
   ```
2. Operator advances to `FIRMS_RESULT_PENDING`.
3. Human runs the FIRMS refresh manually in the operational workspace:
   ```bash
   python -m src.refresh.firms_refresh refresh
   ```
4. Human imports execution evidence payload into operator:
   ```bash
   python -m src.ops.attempt2_operator import-result --phase firms --payload firms_evidence.json
   ```
5. Operator validates exit code, logs sanitization, Parquet schema, and pointers. State transitions to `FIRMS_VALIDATED`.

### Step 9: Manual DMC Writer Refresh
1. Human authorizer issues DMC writer token:
   ```bash
   python -m src.ops.attempt2_operator authorize --gate DMC_WRITER_AUTHORIZATION --actor "Daniel Cortez"
   ```
2. Operator advances to `DMC_RESULT_PENDING`.
3. Human runs the DMC refresh manually:
   ```bash
   python -m src.refresh.dmc_refresh refresh
   ```
4. Human imports execution evidence payload into operator:
   ```bash
   python -m src.ops.attempt2_operator import-result --phase dmc --payload dmc_evidence.json
   ```
5. Operator validates exit code, pointer, quality, and non-modification of Attempt 1 baseline. State transitions to `DMC_VALIDATED`.

### Step 10: Scoring Execution & Evidence Import
1. Operator advances to `SCORING_READY`.
2. Human runs the inference scoring pipeline with operational live inputs.
3. Import scoring output payload:
   ```bash
   python -m src.ops.attempt2_operator import-result --phase scoring --payload scoring_evidence.json
   ```
4. Operator validates:
   - 50 grid cells populated.
   - Distinct live input fingerprint vs. frozen reference fingerprint.
   - Model SHA validation.
   State transitions to `SCORING_VALIDATED`.

### Step 11: Output Plane Manifest Acceptance
1. Operator advances to `BRIDGE_READY`.
2. Capture the accepted bridge result as an Output accepted-run artifact (GET only). This
   prints the artifact path and its `artifact_fingerprint`:
   ```bash
   python -m src.output.accepted_run capture --url http://127.0.0.1:8600/score
   ```
3. Build the per-run acceptance record in the Operations consumer contract. It is built
   from the persistent Output plane manifest (anchored fingerprint) and that artifact:
   ```bash
   python -m src.convergence.output_acceptance build \
       --output-manifest <OUTPUT_PLANE_MANIFEST.json> --expect-output-fingerprint <fp> \
       --accepted-run <accepted-run.json> --expect-artifact-fingerprint <fp> --out <run dir>
   ```
   The Output plane's own `OUTPUT_PLANE_MANIFEST.json` is plane readiness evidence, not the
   per-run record. The Operations consumer rejects it if it is passed directly. For the same
   reason, do not pass it to `init --output-manifest`: `init` records the fingerprint without
   enforcing verification.
4. Bind the record while importing the bridge result (there is no separate `accept-output`
   command):
   ```bash
   python -m src.ops.attempt2_operator import-result --run <RUN> --phase bridge \
       --from bridge.json --output-manifest <run dir>/OUTPUT-PLANE-MANIFEST.json
   ```
5. Step through manual review of downstream orchestrations (`N8N_MANUAL_READY`).

### Step 12: Final Operational Acceptance
1. Operator advances to `ACCEPTANCE_READY`.
2. Final acceptance check executes:
   ```bash
   python -m src.ops.attempt2_operator next --run <RUN> --advance
   ```
3. State transitions to `ACCEPTED`.
4. Run report generation:
   ```bash
   python -m src.ops.attempt2_operator report --run <RUN>
   ```
5. Only after `ACCEPTED`, open the Control Center live
   (`python -m app.control_center --live`). Telegram and the schedule remain separate human
   gates and are not part of this flow.

> [!CAUTION]
> **Scientific Integrity Rule**:
> The final report and state explicitly certify:
> - `software_operational_acceptance`: **TRUE**
> - `scientific_model_validation`: **FALSE**
>
> Operational acceptance certifies software, pipeline, schema, and quiescence correctness. It does NOT constitute scientific validation of the predictive wildfire risk model.

---

## Diagnostic Command Reference

To inspect readiness at any time without mutating system state:
```bash
python -m src.ops.attempt2_operator rc-status --json
```

This read-only command evaluates:
1. `code_identity_ready`: Working tree clean and matching RC1 commit.
2. `workspace_ready`: Operational workspace present, clean, and uncorrupted.
3. `data_manifest_ready`: Validated data readiness manifest present.
4. `quiescence_ready`: Strict quiescence policy satisfied.
5. `output_contract_known`: Presentation artifact schema established.
