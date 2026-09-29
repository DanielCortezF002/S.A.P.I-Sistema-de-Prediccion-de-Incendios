"""Quiescence policy derived from docs/ops/FIRST-CONTROLLED-REFRESH.md.

Do not relax these rules merely so the current machine reports QUIESCENT.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

# FIRST-CONTROLLED-REFRESH §GO: n8n container stopped; bridge/web stopped during publications.
DEFAULT_N8N_CONTAINER = "MUST_BE_STOPPED"
DEFAULT_BRIDGE = "MUST_BE_STOPPED"
DEFAULT_WEB = "MUST_BE_STOPPED"


@dataclass(frozen=True)
class QuiescencePolicy:
    """Service expectations for Attempt 2 authorization readiness."""

    n8n_container: str = DEFAULT_N8N_CONTAINER
    bridge: str = DEFAULT_BRIDGE
    web: str = DEFAULT_WEB
    # When True, n8n MAY remain RUNNING if activation/schedule/telegram/executions prove safe.
    allow_n8n_running_if_inactive: bool = False

    @classmethod
    def from_env(cls) -> QuiescencePolicy:
        allow = os.environ.get("SAPI_ATTEMPT2_N8N_MAY_RUN_IF_INACTIVE", "").strip() in (
            "1",
            "true",
            "TRUE",
            "yes",
        )
        return cls(
            n8n_container=(
                "MAY_BE_RUNNING_IF_INACTIVE" if allow else DEFAULT_N8N_CONTAINER
            ),
            bridge=DEFAULT_BRIDGE,
            web=DEFAULT_WEB,
            allow_n8n_running_if_inactive=allow,
        )
