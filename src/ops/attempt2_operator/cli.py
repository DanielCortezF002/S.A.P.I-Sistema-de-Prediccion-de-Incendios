"""CLI: python -m src.ops.attempt2_operator <command>"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.ops.attempt2_operator.operator import Attempt2Operator
from src.ops.attempt2_operator.rc_status import collect_rc_status, format_rc_status_human
from src.ops.attempt2_operator.run_store import InvalidTransitionError, resolve_evidence_root


def _print(obj: object) -> None:
    # Prefer UTF-8 on Windows consoles so notes with non-ASCII survive.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass
    if isinstance(obj, (dict, list)):
        text = json.dumps(obj, indent=2, ensure_ascii=False, default=str) + "\n"
    else:
        text = str(obj) + "\n"
    try:
        sys.stdout.write(text)
    except UnicodeEncodeError:
        sys.stdout.buffer.write(text.encode("utf-8", errors="replace"))


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m src.ops.attempt2_operator",
        description="S.A.P.I. Attempt 2 controlled operator (human-gated; no auto refresh)",
    )
    parser.add_argument(
        "--evidence-root",
        default=None,
        help="Root for attempt2 runs (default SAPI_ATTEMPT2_EVIDENCE_ROOT or SAPI-71-evidence/attempt2)",
    )
    parser.add_argument(
        "--repo",
        default=None,
        help="Git repo path for identity (default: cwd)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate without stores/APIs/Docker/n8n/Telegram",
    )

    sub = parser.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="Create a new Attempt 2 run")
    p_init.add_argument("--expected-code-sha", required=True)
    p_init.add_argument("--run-id", default=None)
    p_init.add_argument("--workspace-manifest", default=None, help="Verified operational workspace manifest")
    p_init.add_argument("--data-readiness-manifest", default=None, help="Verified Astra data plane manifest")
    p_init.add_argument("--output-manifest", default=None, help="Claude output plane manifest")

    p_status = sub.add_parser("status", help="Show run status (idempotent)")
    p_status.add_argument("--run", required=True)

    p_next = sub.add_parser("next", help="Show next action; optional --advance")
    p_next.add_argument("--run", required=True)
    p_next.add_argument("--advance", action="store_true")

    p_pre = sub.add_parser("preflight", help="Collect/validate preflight")
    p_pre.add_argument("--run", required=True)
    p_pre.add_argument("--snapshot", default=None, help="Optional snapshot JSON (dry-run/synthetic)")
    p_pre.add_argument("--workspace-manifest", default=None, help="Verified operational workspace manifest")
    p_pre.add_argument("--data-readiness-manifest", default=None, help="Verified Astra data plane manifest")

    p_auth = sub.add_parser("authorize", help="Explicit human gate authorization")
    p_auth.add_argument("--run", required=True)
    p_auth.add_argument("--gate", required=True)
    p_auth.add_argument("--actor", default="local-operator")

    p_imp = sub.add_parser("import-result", help="Import manual command evidence")
    p_imp.add_argument("--run", required=True)
    p_imp.add_argument("--phase", required=True, choices=["firms", "dmc", "scoring", "bridge", "n8n"])
    p_imp.add_argument("--from", dest="from_path", required=True)
    p_imp.add_argument("--output-manifest", default=None, help="Optional output plane manifest for bridge/scoring")

    p_val = sub.add_parser("validate", help="Re-read validation artifacts (idempotent)")
    p_val.add_argument("--run", required=True)

    p_rep = sub.add_parser("report", help="Write acceptance/status report (idempotent)")
    p_rep.add_argument("--run", required=True)

    p_rc = sub.add_parser("rc-status", help="RC1 preparation readiness status check")
    p_rc.add_argument("--expected-code-sha", default=None, help="Expected RC1 final code SHA")
    p_rc.add_argument("--workspace-manifest", default=None, help="Operational workspace manifest")
    p_rc.add_argument("--data-readiness-manifest", default=None, help="Astra data plane readiness manifest")
    p_rc.add_argument("--output-manifest", default=None, help="Output plane manifest")
    p_rc.add_argument("--json", action="store_true", help="Output machine-readable JSON")

    args = parser.parse_args(argv)
    repo = Path(args.repo) if args.repo else Path.cwd()
    evidence_root = resolve_evidence_root(args.evidence_root)

    try:
        if args.cmd == "rc-status":
            res = collect_rc_status(
                repo=repo,
                expected_code_sha=args.expected_code_sha,
                workspace_manifest_path=args.workspace_manifest,
                data_plane_manifest_path=args.data_readiness_manifest,
                output_manifest_path=args.output_manifest,
            )
            if getattr(args, "json", False):
                _print(res)
            else:
                _print(format_rc_status_human(res))
            return 0 if res["all_prerequisites_ready"] else 2

        if args.cmd == "init":
            op = Attempt2Operator.init_run(
                evidence_root=evidence_root,
                repo=repo if not args.dry_run else None,
                expected_code_sha=args.expected_code_sha,
                dry_run=args.dry_run,
                run_id=args.run_id,
                workspace_manifest=args.workspace_manifest,
                data_plane_manifest=args.data_readiness_manifest,
                output_manifest=args.output_manifest,
                synthetic_identity=(
                    {
                        "code_sha": args.expected_code_sha,
                        "tree_sha": "synthetic-tree",
                        "worktree_clean": True,
                    }
                    if args.dry_run
                    else None
                ),
            )
            _print({"run_dir": str(op.run.root), **op.status()})
            return 0

        run_dir = Path(args.run)
        op = Attempt2Operator.open_run(run_dir, repo=repo)

        if args.cmd == "status":
            _print(op.status())
            return 0
        if args.cmd == "next":
            if args.advance:
                _print(op.advance())
            else:
                _print(op.next_action())
            return 0
        if args.cmd == "preflight":
            snap = _load_json(Path(args.snapshot)) if args.snapshot else None
            _print(
                op.preflight(
                    snapshot=snap,
                    workspace_manifest=args.workspace_manifest,
                    data_plane_manifest=args.data_readiness_manifest,
                )
            )
            return 0 if op.run.current_state().value == "PREFLIGHT_READY" else 2
        if args.cmd == "authorize":
            _print(op.authorize(args.gate, actor=args.actor))
            return 0
        if args.cmd == "import-result":
            payload = _load_json(Path(args.from_path))
            out = op.import_result(
                args.phase,
                payload,
                output_manifest=args.output_manifest,
            )
            _print(out)
            return 0 if out.get("result") in ("PASS", "DUPLICATE") else 2
        if args.cmd == "validate":
            vals = sorted((run_dir / "validation").glob("*.json")) if (run_dir / "validation").exists() else []
            _print(
                {
                    "state": op.status()["state"],
                    "validation_files": [str(p.name) for p in vals],
                    "manifest_ok": op.verify_manifest_integrity(),
                }
            )
            return 0
        if args.cmd == "report":
            _print(op.report())
            return 0
    except InvalidTransitionError as exc:
        _print({"error": "INVALID_TRANSITION", "detail": str(exc)})
        return 3
    except PermissionError as exc:
        _print({"error": "UNAUTHORIZED", "detail": str(exc)})
        return 4
    except Exception as exc:  # noqa: BLE001
        _print({"error": type(exc).__name__, "detail": str(exc)})
        return 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
