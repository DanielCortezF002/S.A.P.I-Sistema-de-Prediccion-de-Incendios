"""Explicit Attempt 2 operator states (no silent skips)."""

from __future__ import annotations

from enum import Enum


class Attempt2State(str, Enum):
    NEW = "NEW"
    PREFLIGHT_PENDING = "PREFLIGHT_PENDING"
    PREFLIGHT_FAILED = "PREFLIGHT_FAILED"
    PREFLIGHT_READY = "PREFLIGHT_READY"
    ATTEMPT2_AUTHORIZATION_REQUIRED = "ATTEMPT2_AUTHORIZATION_REQUIRED"
    ATTEMPT2_AUTHORIZED = "ATTEMPT2_AUTHORIZED"
    FIRMS_WRITER_REQUIRED = "FIRMS_WRITER_REQUIRED"
    FIRMS_RESULT_PENDING = "FIRMS_RESULT_PENDING"
    FIRMS_VALIDATION_FAILED = "FIRMS_VALIDATION_FAILED"
    FIRMS_VALIDATED = "FIRMS_VALIDATED"
    DMC_WRITER_REQUIRED = "DMC_WRITER_REQUIRED"
    DMC_RESULT_PENDING = "DMC_RESULT_PENDING"
    DMC_VALIDATION_FAILED = "DMC_VALIDATION_FAILED"
    DMC_VALIDATED = "DMC_VALIDATED"
    SCORING_READY = "SCORING_READY"
    SCORING_FAILED = "SCORING_FAILED"
    SCORING_VALIDATED = "SCORING_VALIDATED"
    BRIDGE_READY = "BRIDGE_READY"
    BRIDGE_FAILED = "BRIDGE_FAILED"
    BRIDGE_VALIDATED = "BRIDGE_VALIDATED"
    N8N_MANUAL_READY = "N8N_MANUAL_READY"
    N8N_FAILED = "N8N_FAILED"
    N8N_VALIDATED = "N8N_VALIDATED"
    ACCEPTANCE_READY = "ACCEPTANCE_READY"
    ACCEPTED = "ACCEPTED"
    STOPPED = "STOPPED"


# Allowed transitions: from -> frozenset(to)
ALLOWED_TRANSITIONS: dict[Attempt2State, frozenset[Attempt2State]] = {
    Attempt2State.NEW: frozenset({Attempt2State.PREFLIGHT_PENDING, Attempt2State.STOPPED}),
    Attempt2State.PREFLIGHT_PENDING: frozenset(
        {
            Attempt2State.PREFLIGHT_READY,
            Attempt2State.PREFLIGHT_FAILED,
            Attempt2State.STOPPED,
        }
    ),
    Attempt2State.PREFLIGHT_FAILED: frozenset(
        {Attempt2State.PREFLIGHT_PENDING, Attempt2State.STOPPED}
    ),
    Attempt2State.PREFLIGHT_READY: frozenset(
        {
            Attempt2State.ATTEMPT2_AUTHORIZATION_REQUIRED,
            Attempt2State.STOPPED,
        }
    ),
    Attempt2State.ATTEMPT2_AUTHORIZATION_REQUIRED: frozenset(
        {Attempt2State.ATTEMPT2_AUTHORIZED, Attempt2State.STOPPED}
    ),
    Attempt2State.ATTEMPT2_AUTHORIZED: frozenset(
        {Attempt2State.FIRMS_WRITER_REQUIRED, Attempt2State.STOPPED}
    ),
    Attempt2State.FIRMS_WRITER_REQUIRED: frozenset(
        {Attempt2State.FIRMS_RESULT_PENDING, Attempt2State.STOPPED}
    ),
    Attempt2State.FIRMS_RESULT_PENDING: frozenset(
        {
            Attempt2State.FIRMS_VALIDATED,
            Attempt2State.FIRMS_VALIDATION_FAILED,
            Attempt2State.STOPPED,
        }
    ),
    Attempt2State.FIRMS_VALIDATION_FAILED: frozenset({Attempt2State.STOPPED}),
    Attempt2State.FIRMS_VALIDATED: frozenset(
        {Attempt2State.DMC_WRITER_REQUIRED, Attempt2State.STOPPED}
    ),
    Attempt2State.DMC_WRITER_REQUIRED: frozenset(
        {Attempt2State.DMC_RESULT_PENDING, Attempt2State.STOPPED}
    ),
    Attempt2State.DMC_RESULT_PENDING: frozenset(
        {
            Attempt2State.DMC_VALIDATED,
            Attempt2State.DMC_VALIDATION_FAILED,
            Attempt2State.STOPPED,
        }
    ),
    Attempt2State.DMC_VALIDATION_FAILED: frozenset({Attempt2State.STOPPED}),
    Attempt2State.DMC_VALIDATED: frozenset(
        {Attempt2State.SCORING_READY, Attempt2State.STOPPED}
    ),
    Attempt2State.SCORING_READY: frozenset(
        {
            Attempt2State.SCORING_VALIDATED,
            Attempt2State.SCORING_FAILED,
            Attempt2State.STOPPED,
        }
    ),
    Attempt2State.SCORING_FAILED: frozenset({Attempt2State.STOPPED}),
    Attempt2State.SCORING_VALIDATED: frozenset(
        {Attempt2State.BRIDGE_READY, Attempt2State.STOPPED}
    ),
    Attempt2State.BRIDGE_READY: frozenset(
        {
            Attempt2State.BRIDGE_VALIDATED,
            Attempt2State.BRIDGE_FAILED,
            Attempt2State.STOPPED,
        }
    ),
    Attempt2State.BRIDGE_FAILED: frozenset({Attempt2State.STOPPED}),
    Attempt2State.BRIDGE_VALIDATED: frozenset(
        {Attempt2State.N8N_MANUAL_READY, Attempt2State.STOPPED}
    ),
    Attempt2State.N8N_MANUAL_READY: frozenset(
        {
            Attempt2State.N8N_VALIDATED,
            Attempt2State.N8N_FAILED,
            Attempt2State.STOPPED,
        }
    ),
    Attempt2State.N8N_FAILED: frozenset({Attempt2State.STOPPED}),
    Attempt2State.N8N_VALIDATED: frozenset(
        {Attempt2State.ACCEPTANCE_READY, Attempt2State.STOPPED}
    ),
    Attempt2State.ACCEPTANCE_READY: frozenset(
        {Attempt2State.ACCEPTED, Attempt2State.STOPPED}
    ),
    Attempt2State.ACCEPTED: frozenset(),
    Attempt2State.STOPPED: frozenset(),
}


HUMAN_GATES = (
    "ATTEMPT2_AUTHORIZATION",
    "FIRMS_WRITER_AUTHORIZATION",
    "DMC_WRITER_AUTHORIZATION",
    "TELEGRAM_AUTHORIZATION",
    "SCHEDULE_AUTHORIZATION",
)

# Gates required before protected writer / late automations
GATE_FOR_STATE: dict[Attempt2State, str | None] = {
    Attempt2State.ATTEMPT2_AUTHORIZATION_REQUIRED: "ATTEMPT2_AUTHORIZATION",
    Attempt2State.FIRMS_WRITER_REQUIRED: "FIRMS_WRITER_AUTHORIZATION",
    Attempt2State.DMC_WRITER_REQUIRED: "DMC_WRITER_AUTHORIZATION",
}

FIRMS_HARD_EXIT_CODES = frozenset({65, 69, 75, 78})
