"""Entry point: collect_quiescence — read-only operational quiescence gate."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from src.ops.attempt2_operator.collectors.runtime import (
    collect_runtime,
    list_containers_readonly,
)
from src.ops.attempt2_operator.paths import StoreRoots
from src.ops.attempt2_operator.quiescence.locks import inspect_refresh_locks
from src.ops.attempt2_operator.quiescence.n8n_inspect import collect_n8n_quiescence_signals
from src.ops.attempt2_operator.quiescence.policy import QuiescencePolicy
from src.ops.attempt2_operator.quiescence.processes import inventory_processes
from src.ops.attempt2_operator.quiescence.result import evaluate_quiescence
from src.ops.attempt2_operator.quiescence.writers import detect_writers


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def collect_quiescence(
    *,
    repo: Path,
    data_root: Path | None = None,
    runtime: dict[str, Any] | None = None,
    policy: QuiescencePolicy | None = None,
    host_process_lister: Callable[[], list[dict[str, Any]]] | None = None,
    skip_host_processes: bool = False,
) -> dict[str, Any]:
    """Run the full read-only quiescence collection + evaluation."""
    started = _utc_now()
    policy = policy or QuiescencePolicy.from_env()
    roots = StoreRoots.from_repo(repo, data_root=data_root)

    if runtime is None:
        runtime = collect_runtime()

    containers = list_containers_readonly()
    if skip_host_processes:
        processes = inventory_processes(
            host_lister=lambda: [],
            containers=containers,
        )
        processes["status"] = "PARTIAL"
        processes["detail"] = "host_process_scan_skipped"
    elif host_process_lister is not None:
        processes = inventory_processes(
            host_lister=host_process_lister,
            containers=containers,
        )
    else:
        processes = inventory_processes(containers=containers)

    writers = detect_writers(
        processes,
        process_scan_ok=processes.get("status") != "UNKNOWN",
    )

    firms_lock = roots.firms_store() / ".refresh.lock"
    dmc_lock = roots.dmc_store() / ".refresh.lock"
    locks = inspect_refresh_locks(firms_lock=firms_lock, dmc_lock=dmc_lock)

    n8n_signals = collect_n8n_quiescence_signals(
        n8n_runtime=runtime.get("n8n") or {"status": "UNKNOWN"},
        containers=containers,
    )

    bridge = runtime.get("bridge") or {"status": "UNKNOWN"}
    web = runtime.get("web") or {"status": "UNKNOWN"}

    finished = _utc_now()
    return evaluate_quiescence(
        processes=processes,
        writers=writers,
        locks=locks,
        n8n=n8n_signals,
        bridge=bridge,
        web=web,
        policy=policy,
        observed_at_start=started,
        observed_at_end=finished,
    )
