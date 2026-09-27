# RC1 local release gate

This extends the recovered `c9e9e9431adf8d993e57ceb6bc597441c1dae82f`
CI harness. Run from the Release Engineering checkout, using Python 3.14 with
PyYAML installed. The candidate is a **full committed SHA**, never a branch or
mutable checkout. No push, merge, refresh, materialization or notification is
performed. PASS is evidence, never operational authorization.

```powershell
$python = 'D:\portafolio y seminario\SAPI-71-evidence\release-gates\tooling-venv\Scripts\python.exe'
& $python scripts/ci_local.py gate --candidate-sha <FULL_CANDIDATE_SHA> `
  --data-manifest 'D:\portafolio y seminario\SAPI-71-evidence\data-plane-rc1-2026-09-25\DATA_PLANE_MANIFEST.json' `
  --expected-data-fingerprint 5a6484fc4b047751fa6cec8e29a377c0ed96a19e1873ec25539745bca32a1ae0 `
  --output-manifest 'D:\portafolio y seminario\SAPI-71-evidence\output-plane-rc1-2026-09-25\OUTPUT_PLANE_MANIFEST.json' `
  --expected-output-fingerprint 9441f7178805f48ab6d7f563b8bd5c70e555ba621bfb6779ba2360cec61b01a3 `
  --require-lane operations=<OPERATIONS_SHA_SUPPLIED_WITH_CANDIDATE>
```

Data and Output ancestry also follows their verified producer manifests.
The frozen Data/Output paths and expected fingerprints above are CLI defaults;
`python scripts/ci_local.py gate --candidate-sha <SHA>` runs the complete gate.
Operations has no required symmetric manifest; its updated SHA is an explicit
input. Never assume the current pre-adapter Operations SHA is the final one.
Without an explicit `--require-lane operations=<SHA>`, its required ancestry
check remains INCOMPLETE; producer-manifest absence is not treated as approval.
Missing required plane evidence is never verified: a supplied missing path fails
validation; an omitted input is incomplete. Both manifests are required for a
combined release evaluation. A Data-only candidate can therefore be tested but
is not expected to satisfy a complete combined release gate.

Exit 0 = PASS; 1 = FAIL; 2 = INCOMPLETE. Required failures take precedence over
incomplete checks. Historical absolute Black/flake8 debt is visible; new
multiset findings against base `7ef8d3c9f7ecb4758718255b8e48d6468f8613ea`
fail the differential policy. Black identity is path + hash of changed hunk
lines; flake8 identity is path + code + hash of column, message and offending
source line. Line-number shifts alone do not create lint regressions. A newly
changed Black hunk can count as new debt even in a historically unformatted
file. Changed-file findings and all baseline/candidate findings are retained.

The committed CI workflow is mapped step by step. Unsupported workflow drift
makes the gate incomplete. Local differential acceptance does **not** mean the
absolute GitHub Black/flake8 jobs pass. Remote GitHub CI is **NOT VERIFIED**.
Local Windows, Docker Debian, GitHub Ubuntu and resolved transitive dependency
versions are not bit-identical environments. Requirements are installed as
committed; pip freeze records resolution. No transitive lock is invented.

Sources come from Git archive with line conversion disabled; every exported
blob is independently checked against Git. Links/submodules are rejected.
The candidate also receives a self-contained shallow Git object pack and exact
HEAD/index, without remotes, alternates, links or a checkout operation. This
supports Git-aware tests without inventing a replacement commit. Ancestry is
verified independently against the authoritative repository object database.
Windows subprocesses receive `core.longpaths=true` through process environment,
without modifying user Git configuration. Docker receives the same isolated
metadata after image creation, since the committed `.dockerignore` excludes it.
Candidate and baseline run under a fresh isolated venv. Runtime Python socket
auditing rejects external DNS/connections and operational local ports, allowing
the owned PostGIS port and ephemeral loopback fixtures. This is a test guard,
not an adversarial sandbox for arbitrary native subprocesses. Credentials are
not inherited; dotenv is disabled. Dependency installation/image builds need
package network access. Docker test runtime uses an internal network.

PostGIS uses unique gate-owned names and tmpfs, with a random loopback-only
port for host tests. The database alone joins a separate disposable bridge so
its loopback publication works; the application remains on the internal network.
No real-store mounts, Compose commands or volume deletion.
Cleanup targets only names created by that run. The candidate analytics image
is used with its operational entrypoint overridden; the test image adds git and
Node. Exact manifest copies are placed in the run's sibling evidence directory
and copied into the disposable test container for convergence tests. SQL runs in CI order with
CI options, including its existing lack of `ON_ERROR_STOP`.

`result.json` schema 1 (`kind: RC_GATE_RESULT`) contains candidate SHA/tree,
baseline, gate file hashes/commit, environment identity, checks (id/status/
required/detail), stable findings, tests, coverage, manifests, ancestry and
sentinels. `summary.txt` is the human result; `RC_MANIFEST.json` is the stable
release identity. Individual command receipts/logs survive interruptions.
Evidence stays under `SAPI-71-evidence/release-gates`, with a unique run folder.

The release fingerprint is SHA-256 of canonical JSON (sorted keys, compact
separators, ASCII escaping, no NaN) from `stable_result`: candidate/baseline,
gate/environment, static findings, test counts, coverage, sentinels, producer
identities, findings/status, ancestry/handshake, Docker/PostGIS, cache identity
and normalized check identifiers/statuses. Clocks, durations, random names,
absolute temporary paths and raw log hashes are excluded. Reproducibility
means identical stable inputs/outcomes, not that every candidate must PASS.

```powershell
& $python scripts/ci_local.py compare '<old-run>\result.json' '<new-run>\result.json'
```

Both results are schema/aggregation/fingerprint validated before comparison.
`--resume <old-run>` can reuse a completed isolated environment only when the
candidate/tree, baseline, gate code, interpreter, lane requirements and
manifest bytes/expected fingerprints match, and a fresh pip freeze matches
its installation receipt. All source, manifest, static and test checks rerun;
test PASS is never copied across candidates. Interrupted installs are not reused.
Never move or delete an environment while a resumed run uses it.

Gate-only self-tests need pytest and PyYAML, independent of product conftest:

```powershell
& $python -m pytest tests/test_ci_local.py tests/test_ci_release.py --noconftest -o addopts='' -q
```

The pre-adapter Data consumer mismatch must remain observable. The independent
Data producer verifier uses canonical `identity`; the Operations handshake
executes the candidate's read-only consumer with the real manifest. A consumer
failure is a compatibility blocker, not permission to rewrite the candidate.
The landed consumer's `PREPARED` result is accepted only as contract evidence,
with `prepared=true`, `ready=false` and both writer/Attempt2 flags false. The
machine result retains PREPARED; it is never converted into operational READY.
JSON receipts are written atomically; a RUNNING receipt is incomplete until
replaced by its final command result. Bounded command timeouts terminate only
the process tree owned by that command. Test outcome fingerprints bind each
test's class/name/status, excluding durations and temporary paths.
