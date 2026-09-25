"""Contrato canónico de salida de `/score` (sapi-output-v1).

Es una representación de TRANSPORTE del mismo `GridScoreResult` ya validado por
`contract.validate_grid_result`: no hay un segundo resultado de scoring. A los
campos que el bridge ya emitía se agregan, sin cambiarlos:

- `output_schema_version`: "sapi-output-v1";
- `input_identity`: identidades seguras de `ScoringInputs.manifest()` (lista
  blanca; lo que no existe upstream queda en null, nunca se inventa);
- `alert_identity`: identidad canónica de la notificación, calculada con la
  ÚNICA receta de `src.notifications.alert_payload.build_alert` sobre este mismo
  payload (Control Center y ops/n8n/policy.js la verifican con esa receta);
- `limitations`: las limitaciones científicas del payload de alerta.

Mapa de nombres: `forecast_time` es la hora de evaluación (scoring_time del
payload de alerta); `cells`, `firms_*` e `inputs_fingerprint` quedan como estaban.
"""

from __future__ import annotations

from typing import Mapping, Optional

from src.inference.scoring_inputs import _canonical_sha as manifest_fingerprint
from src.notifications.alert_payload import LIMITATIONS, STATUS_READY, build_alert
from src.output.contract import OUTPUT_SCHEMA_VERSION, input_identity
from tools.n8n_bridge.contract import InvalidScoreResultError

__all__ = ["OUTPUT_SCHEMA_VERSION", "attach_output_contract", "input_identity"]


def attach_output_contract(payload: dict, manifest: Optional[Mapping]) -> dict:
    """Agrega el contrato canónico a un payload de `/score` ya serializado.

    Lanza `InvalidScoreResultError` (→ 500 `internal_error`) si el manifest no
    corresponde al `inputs_fingerprint` o si la receta de alerta no acepta el
    resultado: nunca sale un 200 con identidades inconsistentes.
    """
    if isinstance(manifest, Mapping) and manifest_fingerprint(manifest) != payload.get(
        "inputs_fingerprint"
    ):
        raise InvalidScoreResultError(
            ["inputs_fingerprint no corresponde a scoring_inputs"]
        )
    alert = build_alert(payload)
    if alert["status"] != STATUS_READY:
        raise InvalidScoreResultError(
            [
                f"alert_payload rechaza el resultado: {', '.join(alert.get('reasons', []))}"
            ]
        )
    return {
        **payload,
        "output_schema_version": OUTPUT_SCHEMA_VERSION,
        "input_identity": input_identity(manifest),
        "alert_identity": {
            "schema_version": alert["schema_version"],
            "alert_fingerprint": alert["alert_fingerprint"],
            "top_n": alert["summary"]["top_n"],
        },
        "limitations": [dict(x) for x in LIMITATIONS],
    }
