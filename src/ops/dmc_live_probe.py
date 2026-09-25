"""One bounded, read-only DMC monthly request and shared writer preflight.

No output/store paths are accepted. Only a sanitized JSON summary reaches stdout;
the caller may capture it in an approved evidence directory. Payload stays in memory.
"""

from __future__ import annotations

import argparse
from contextlib import suppress
from datetime import datetime, timezone
import json
import re
import time
from typing import Any

import requests

from src.refresh import dmc_refresh as dmc
from src.refresh.atomic import sha256_bytes
from src.refresh.redact import redact

MAX_BYTES = 16 * 1024 * 1024
MAX_SECONDS = 30
TIMEOUT = (5, 20)
MESSAGES = {
    "VALID": "Monthly payload and canonical candidate accepted by production validation.",
    "NULLS_ALLOWED_WITHIN_CONTRACT": "Explicit null rows are within the monthly limit.",
    "NULLS_EXCEED_LIMIT": "Monthly explicit-null row rate exceeds production limit.",
    "NONNUMERIC_REQUIRED_FIELD": "A required value is not finite numeric data.",
    "MISSING_REQUIRED_FIELD": "A required numeric field is absent.",
    "EMPTY_RESPONSE": "No usable monthly response; no successful fallback is supplied.",
    "MALFORMED_RESPONSE": "Payload fails production structure, count, timestamp or parser checks.",
    "NETWORK_UNAVAILABLE": "Single request failed, timed out or returned non-200 HTTP status.",
    "CONFIG_MISSING": "Required source configuration is unavailable.",
    "RESOURCE_LIMIT": "Bounded response size or elapsed-time limit exceeded.",
    "INCOMPLETE": "Validation could not complete; compatibility is unknown.",
}


def sanitized(value: Any, credentials: tuple[str, str]) -> Any:
    if isinstance(value, str):
        return redact(value, credentials)
    if isinstance(value, dict):
        return {
            redact(k, credentials): sanitized(v, credentials) for k, v in value.items()
        }
    if isinstance(value, list):
        return [sanitized(v, credentials) for v in value]
    return value


def _result(month: str) -> dict:
    return {
        "schema_version": 1,
        "status": "INCOMPLETE",
        "exit_code": dmc.EXIT_USAGE,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "interface": "getDatosRecientesEma",
            "station": dmc.DMC_STATION_ID,
            "month": month,
        },
        "http": {
            "status": None,
            "content_type": None,
            "response_bytes": None,
            "attempts": 0,
            "redirects_followed": False,
        },
        "coverage": {"start": None, "end": None, "timezone": "UTC"},
        "records": {
            "received": None,
            "valid_candidate": None,
            "null_rows": None,
            "null_percentage": None,
            "duplicate_moments": None,
            "conflicts": None,
        },
        "validation": {
            "category": "INCOMPLETE",
            "required_fields": list(dmc.REQUIRED_NUMERIC_FIELDS),
            "required_fields_present": None,
            "numeric_fields_valid": None,
            "null_limit": float(dmc.NULL_ROWS_MAX_RATE),
            "candidate_sha256": None,
            "range_check": "finite numbers only; no physical-range policy in writer",
        },
        "dry_run": {
            "scope": "one monthly candidate against empty prior-month state",
            "production_validator_reused": True,
            "writer_would_accept_payload": None,
            "full_refresh_ready": False,
            "publication_performed": False,
        },
        "findings": [],
    }


def _finish(
    result: dict, category: str, status: str, code: int, credentials: tuple[str, str]
) -> dict:
    result.update(status=status, exit_code=code)
    if status == "INCOMPATIBLE":
        result["dry_run"]["writer_would_accept_payload"] = False
    result["validation"]["category"] = category
    result["findings"].append({"code": category, "message": MESSAGES[category]})
    return sanitized(result, credentials)


def _month_valid(month: str) -> bool:
    try:
        return (
            bool(re.fullmatch(r"\d{4}-\d{2}", month))
            and datetime.strptime(month, "%Y-%m").year > 0
        )
    except (ValueError, TypeError):
        return False


def validate_payload(
    payload: Any,
    month: str,
    *,
    credentials: tuple[str, str] = ("", ""),
    result: dict | None = None,
) -> dict:
    """Pure summary of the SAME monthly candidate preparation used by the writer.

    No CURRENT/versions paths, temporary files or publication hooks are involved.
    Prior published months/permissions/locks are deliberately not claimed checked.
    """
    result = result if result is not None else _result(month)
    if not _month_valid(month):
        return _finish(result, "INCOMPLETE", "INCOMPLETE", dmc.EXIT_USAGE, credentials)
    try:
        _, records = dmc.validate_month_payload(payload, month)
        moments = sorted(r["momento"] for r in records)
        result["coverage"].update(
            received_start=moments[0] if moments else None,
            received_end=moments[-1] if moments else None,
        )
        nulls = sum(
            any(r.get(k, object()) is None for k in dmc.REQUIRED_NUMERIC_FIELDS)
            for r in records
        )
        missing = sum(
            any(k not in r for k in dmc.REQUIRED_NUMERIC_FIELDS) for r in records
        )
        numeric_bad = 0
        for row in records:
            try:
                dmc.assess_rows([row], month)
            except dmc.DmcRefreshError as error:
                numeric_bad += error.reason == "NONNUMERIC_REQUIRED_FIELD"
        result["records"].update(
            received=len(records),
            null_rows=nulls,
            null_percentage=100 * nulls / len(records) if records else None,
            duplicate_moments=len(records) - len({r["momento"] for r in records}),
        )
        result["validation"].update(
            required_fields_present=missing == 0,
            numeric_fields_valid=numeric_bad == 0 and missing == 0,
            missing_field_rows=missing,
            nonnumeric_rows=numeric_bad,
        )
        prepared = dmc.prepare_month_payload(payload, dmc.DMC_STATION_ID, month)
        result["records"].update(
            valid_candidate=len(prepared.valid),
            conflicts=prepared.conflicts,
            candidate_quality=prepared.quality.as_dict(),
        )
        result["coverage"].update(
            start=prepared.valid[0]["momento"], end=prepared.valid[-1]["momento"]
        )
        result["validation"]["candidate_sha256"] = sha256_bytes(prepared.data)
        result["dry_run"]["writer_would_accept_payload"] = True
        if prepared.conflicts:
            result["findings"].append(
                {
                    "code": "ORDER_SENSITIVE_CONFLICTS",
                    "message": "Existing merge contract keeps the first incoming value per momento.",
                }
            )
        category = "NULLS_ALLOWED_WITHIN_CONTRACT" if nulls else "VALID"
        return _finish(result, category, "COMPATIBLE", dmc.EXIT_OK, credentials)
    except dmc.DmcRefreshError as error:
        category = error.reason if error.reason in MESSAGES else "MALFORMED_RESPONSE"
        # Never serialize the exception text: it may contain arbitrary response values.
        result["dry_run"]["writer_would_accept_payload"] = False
        return _finish(result, category, "INCOMPATIBLE", dmc.EXIT_DATA, credentials)
    except (ValueError, TypeError, KeyError, OverflowError):
        return _finish(
            result, "MALFORMED_RESPONSE", "INCOMPATIBLE", dmc.EXIT_DATA, credentials
        )


def probe(
    month: str,
    *,
    credentials: tuple[str, str] | None = None,
    session: requests.Session | None = None,
) -> dict:
    credentials = (
        credentials if credentials is not None else (dmc.DMC_USUARIO, dmc.DMC_TOKEN)
    )
    result = _result(month)
    if not _month_valid(month):
        return _finish(result, "INCOMPLETE", "INCOMPLETE", dmc.EXIT_USAGE, credentials)
    if len(credentials) != 2 or not all(
        isinstance(v, str) and v.strip() for v in credentials
    ):
        return _finish(
            result, "CONFIG_MISSING", "CONFIG_MISSING", dmc.EXIT_CONFIG, credentials
        )
    owned = session is None
    session = session or requests.Session()
    if owned:
        session.trust_env = False  # no ambient auth/netrc/proxy secrets; no retries
    response = None
    start = time.monotonic()
    try:
        result["http"]["attempts"] = 1
        response = session.get(
            dmc.month_source_url(dmc.DMC_STATION_ID, month),
            params={"usuario": credentials[0], "token": credentials[1]},
            timeout=TIMEOUT,
            allow_redirects=False,
            stream=True,
        )
        result["http"]["status"] = response.status_code
        media = response.headers.get("Content-Type", "").split(";", 1)[0].strip()
        if re.fullmatch(r"[A-Za-z0-9!#$&^_.+-]+/[A-Za-z0-9!#$&^_.+-]+", media):
            result["http"]["content_type"] = media
        if response.status_code != 200:
            return _finish(
                result,
                "NETWORK_UNAVAILABLE",
                "NETWORK_UNAVAILABLE",
                dmc.EXIT_NETWORK,
                credentials,
            )
        content = bytearray()
        for chunk in response.iter_content(chunk_size=65536):
            if (
                len(content) + len(chunk) > MAX_BYTES
                or time.monotonic() - start > MAX_SECONDS
            ):
                result["http"]["response_bytes"] = len(content)
                return _finish(
                    result, "RESOURCE_LIMIT", "INCOMPLETE", dmc.EXIT_USAGE, credentials
                )
            content.extend(chunk)
        result["http"]["response_bytes"] = len(content)
        if not content.strip():
            return _finish(
                result, "EMPTY_RESPONSE", "INCOMPATIBLE", dmc.EXIT_DATA, credentials
            )
        try:
            payload = json.loads(content)
        except (ValueError, UnicodeError):
            return _finish(
                result, "MALFORMED_RESPONSE", "INCOMPATIBLE", dmc.EXIT_DATA, credentials
            )
        return validate_payload(payload, month, credentials=credentials, result=result)
    except requests.RequestException:
        return _finish(
            result,
            "NETWORK_UNAVAILABLE",
            "NETWORK_UNAVAILABLE",
            dmc.EXIT_NETWORK,
            credentials,
        )
    except Exception:
        # Operational diagnostics never expose unexpected exception/response text.
        return _finish(result, "INCOMPLETE", "INCOMPLETE", dmc.EXIT_USAGE, credentials)
    finally:
        if response is not None:
            with suppress(Exception):
                response.close()
        if owned:
            with suppress(Exception):
                session.close()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--month",
        default=datetime.now(timezone.utc).strftime("%Y-%m"),
        help="One requested month, YYYY-MM (default: current UTC month).",
    )
    args = parser.parse_args(argv)
    result = probe(args.month)
    print(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2))
    return result["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
