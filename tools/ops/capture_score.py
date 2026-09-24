"""Read-only evidence: capture and score the SAME ScoringInputs object."""

import argparse
import hashlib
import json
import os

from src.inference.prototype_service import capture_scoring_inputs, score_current_grid
from tools.n8n_bridge.app import _FALLBACK_DISCLAIMER, _serialize_grid_result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode", choices=["reproducible", "operational"], required=True
    )
    args = parser.parse_args()
    os.environ["SAPI_REPRODUCIBILITY_MODE"] = str(int(args.mode == "reproducible"))
    inputs = capture_scoring_inputs()
    result = score_current_grid(inputs=inputs)
    ranking = "\n".join(f"{c.cell_id},{c.score!r},{c.rank}" for c in result.cells)
    evidence = {
        "mode": args.mode,
        "captured_at": inputs.captured_at.isoformat(),
        "same_scoring_inputs_object": True,
        "inputs_fingerprint": inputs.fingerprint,
        "manifest": inputs.manifest(),
        "operational_series_valid_count": len(inputs.meteo_series),
        "ranking_fingerprint": hashlib.sha256(ranking.encode()).hexdigest(),
        "score": _serialize_grid_result(result, _FALLBACK_DISCLAIMER),
    }
    # ASCII-only JSON survives cp1252 console redirection and PowerShell parsing.
    print(json.dumps(evidence, ensure_ascii=True, indent=2, default=str))


if __name__ == "__main__":
    main()
