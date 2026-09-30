#!/usr/bin/env python3
"""Thin wrapper: python scripts/attempt2_operator.py ..."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ops.attempt2_operator.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
