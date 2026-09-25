"""Stable quiescence finding IDs and human remediation hints (observe-only)."""

from __future__ import annotations

# QG-xxx finding IDs
QG_ACTIVE_WRITER = "QG-001"
QG_ACTIVE_FIRMS_LOCK = "QG-002"
QG_ACTIVE_DMC_LOCK = "QG-003"
QG_STALE_LOCK = "QG-004"
QG_ACTIVE_N8N_EXECUTION = "QG-005"
QG_ENABLED_SCHEDULE = "QG-006"
QG_TELEGRAM_ARMED = "QG-007"
QG_UNKNOWN_N8N_STATE = "QG-008"
QG_CONFLICTING_SERVICE = "QG-009"
QG_UNKNOWN_WRITER_STATE = "QG-010"
QG_UNKNOWN_LOCK_STATE = "QG-011"
QG_TELEGRAM_UNKNOWN = "QG-012"
QG_SCHEDULE_UNKNOWN = "QG-013"
QG_N8N_MUST_BE_STOPPED = "QG-014"
QG_BRIDGE_MUST_BE_STOPPED = "QG-015"
QG_WEB_MUST_BE_STOPPED = "QG-016"

FINDING_REMEDIATION: dict[str, str] = {
    QG_ACTIVE_WRITER: (
        "Stop the active FIRMS/DMC/scoring writer process, then rerun preflight. "
        "Operator will not kill it."
    ),
    QG_ACTIVE_FIRMS_LOCK: (
        "Wait for the active FIRMS refresh lock holder to finish, then rerun preflight. "
        "Operator will not delete locks."
    ),
    QG_ACTIVE_DMC_LOCK: (
        "Wait for the active DMC refresh lock holder to finish, then rerun preflight. "
        "Operator will not delete locks."
    ),
    QG_STALE_LOCK: (
        "Inspect/resolve the stale refresh lock manually; operator will not delete it."
    ),
    QG_ACTIVE_N8N_EXECUTION: (
        "Wait for the running n8n execution to finish, then rerun preflight. "
        "Operator will not cancel executions."
    ),
    QG_ENABLED_SCHEDULE: (
        "Disable the relevant n8n schedule, then rerun preflight. "
        "Operator will not disable schedules."
    ),
    QG_TELEGRAM_ARMED: (
        "Disarm the Telegram path (inactive workflow / disconnect Telegram nodes), "
        "then rerun preflight. Operator will not mutate n8n."
    ),
    QG_UNKNOWN_N8N_STATE: (
        "Resolve n8n activation-state visibility before authorization."
    ),
    QG_CONFLICTING_SERVICE: (
        "Resolve the conflicting operational service state, then rerun preflight. "
        "Operator will not stop services."
    ),
    QG_UNKNOWN_WRITER_STATE: (
        "Resolve writer-process visibility before authorization."
    ),
    QG_UNKNOWN_LOCK_STATE: (
        "Resolve refresh-lock visibility before authorization."
    ),
    QG_TELEGRAM_UNKNOWN: (
        "Resolve Telegram-path visibility before authorization."
    ),
    QG_SCHEDULE_UNKNOWN: (
        "Resolve n8n schedule visibility before authorization."
    ),
    QG_N8N_MUST_BE_STOPPED: (
        "Stop the n8n container (FIRST-CONTROLLED-REFRESH requires it stopped), "
        "then rerun preflight. Operator will not stop it."
    ),
    QG_BRIDGE_MUST_BE_STOPPED: (
        "Stop the n8n-bridge container, then rerun preflight. Operator will not stop it."
    ),
    QG_WEB_MUST_BE_STOPPED: (
        "Stop the web-presentation container, then rerun preflight. Operator will not stop it."
    ),
}

# Priority for `next` (highest first)
FINDING_PRIORITY: tuple[str, ...] = (
    QG_ACTIVE_WRITER,
    QG_ACTIVE_FIRMS_LOCK,
    QG_ACTIVE_DMC_LOCK,
    QG_ACTIVE_N8N_EXECUTION,
    QG_ENABLED_SCHEDULE,
    QG_TELEGRAM_ARMED,
    QG_N8N_MUST_BE_STOPPED,
    QG_BRIDGE_MUST_BE_STOPPED,
    QG_WEB_MUST_BE_STOPPED,
    QG_STALE_LOCK,
    QG_CONFLICTING_SERVICE,
    QG_UNKNOWN_WRITER_STATE,
    QG_UNKNOWN_LOCK_STATE,
    QG_UNKNOWN_N8N_STATE,
    QG_SCHEDULE_UNKNOWN,
    QG_TELEGRAM_UNKNOWN,
)
