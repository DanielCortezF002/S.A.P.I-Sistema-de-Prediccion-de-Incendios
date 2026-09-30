"""Version-controlled offline replacement gate; prints JSON, writes nothing."""
from __future__ import annotations

import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.refresh.firms_refresh import FirmsPaths
from src.refresh.firms_validation import validate_publication


def main(paths: FirmsPaths | None = None) -> int:
    try:
        result = validate_publication(paths or FirmsPaths())
    except (ValueError, RuntimeError, OSError, KeyError, TypeError):
        # Paths/exception strings could come from untrusted provenance. Don't echo them.
        print(json.dumps({"result": "FIRMS REJECTED", "reason": "publication validation failed"}))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
