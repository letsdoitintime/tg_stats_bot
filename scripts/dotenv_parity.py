"""Killer question for python-dotenv: does it parse the REAL .env identically?
Secrets never printed or stored — key names + SHA256 of each value only.
Exceptions are results too."""
import sys, hashlib, json
from importlib.metadata import version
from dotenv import dotenv_values
def digest(path):
    try:
        vals = dotenv_values(path)
    except Exception as e:
        return {"__error__": f"{type(e).__name__}: {e}"}
    return {k: ("<None>" if v is None else hashlib.sha256(v.encode()).hexdigest()[:16])
            for k, v in vals.items()}
res = {p: digest(p) for p in sys.argv[2:]}
json.dump(res, open(sys.argv[1], "w"), indent=1, sort_keys=True)
print(f"python-dotenv {version('python-dotenv')}: " +
      ", ".join(f"{p}={len(d)} keys" for p, d in res.items()))
