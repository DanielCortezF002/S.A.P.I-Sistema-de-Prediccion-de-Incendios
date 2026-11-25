"""p95 por rango más cercano desde las muestras crudas de k6 (--out json). Uso: py -I analizar_rnf03.py <carpeta_corrida>"""
import json, math, sys
from pathlib import Path
d = Path(sys.argv[1])
pts = []
for line in (d / "medicion-muestras.json").read_text(encoding="utf-8").splitlines():
    o = json.loads(line)
    if o.get("type") == "Point" and o["metric"] == "http_req_duration" and o["data"]["tags"].get("endpoint") == "ranking":
        pts.append((o["data"]["time"], o["data"]["value"], o["data"]["tags"].get("status")))
n = len(pts)
fallos = [p for p in pts if p[2] != "200"]
vals = sorted(math.inf if p[2] != "200" else p[1] for p in pts)  # fallos = +inf (RNF-03)
rank = math.ceil(0.95 * n) if n else 0
s = json.loads((d / "medicion-summary-export.json").read_text(encoding="utf-8"))
dur = s["metrics"]["http_req_duration{endpoint:ranking}"] if "http_req_duration{endpoint:ranking}" in s["metrics"] else s["metrics"]["http_req_duration"]
out = {
    "n_muestras": n, "fallos": len(fallos),
    "p95_rango_mas_cercano_ms": vals[rank - 1] if n else None, "posicion": rank,
    "p50_rango_mas_cercano_ms": vals[math.ceil(0.5 * n) - 1] if n else None,
    # JSON no admite Infinity: el máximo con fallos se deja en null y se explica.
    "max_ms": (vals[-1] if math.isfinite(vals[-1]) else None) if n else None,
    "max_ms_nota": ("null porque hay fallos: cada fallo cuenta como +infinito (RNF-03) y la corrida no cumple; "
                    "ver max_ms_respuestas_200 y fallos_detalle") if fallos else None,
    "max_ms_respuestas_200": max((p[1] for p in pts if p[2] == "200"), default=None),
    "n_respuestas_200": sum(1 for p in pts if p[2] == "200"),
    "fallos_detalle": [{"iteracion": i + 1, "status": p[2], "duracion_ms": p[1], "time": p[0]}
                       for i, p in enumerate(pts) if p[2] != "200"],
    "min_ms": vals[0] if n else None,
    "k6_summary_http_req_duration_endpoint_ranking": dur,
    "k6_http_req_failed": s["metrics"].get("http_req_failed"),
    "muestras_ms_en_orden": [round(p[1], 1) for p in pts],
    "estados": [p[2] for p in pts],
}
out["veredicto"] = "CUMPLE" if n == 30 and not fallos and out["p95_rango_mas_cercano_ms"] <= 2000 else "NO CUMPLE"
(d / "analisis-rango-mas-cercano.json").write_text(json.dumps(out, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
print(json.dumps({k: v for k, v in out.items() if k not in ("muestras_ms_en_orden", "estados")}, ensure_ascii=False, indent=1))
