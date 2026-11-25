import json, sys, time, hashlib, urllib.request as u, urllib.error
from datetime import datetime, timezone
o = u.build_opener(u.ProxyHandler({}))
def get(url, t=90):
    s = time.perf_counter(); st = datetime.now(timezone.utc).isoformat()
    try:
        r = o.open(url, timeout=t); code, b = r.status, r.read()
    except urllib.error.HTTPError as e:
        code, b = e.code, e.read()
    return st, code, b, round((time.perf_counter() - s) * 1000)
out = {}
for name, url in [("web", "http://127.0.0.1:18501/_stcore/health"), ("backend", "http://127.0.0.1:18080/health"), ("ml_api", "http://127.0.0.1:18000/health")]:
    st, c, b, ms = get(url, 20); out[name + "_health"] = {"inicio_utc": st, "estado": c, "cuerpo": b.decode()[:200], "ms": ms}
st, c, b, ms = get("http://127.0.0.1:18080/api/v1/ranking")
j = json.loads(b)
keep = {k: v for k, v in j.items() if k != "cells"}
out["ranking"] = {"inicio_utc": st, "estado": c, "ms": ms, "sha256_cuerpo": hashlib.sha256(b).hexdigest(),
                  "n_celdas": len(j.get("cells", [])), "campos_sin_celdas": keep}
json.dump(out, open(sys.argv[1], "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(json.dumps(out, ensure_ascii=False, indent=1))
