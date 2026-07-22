"""Killer question for prometheus_client: what goes over the WIRE?
Canonicalize only the wall-clock VALUE of _created series; keep the line itself
so an added/removed series still shows in the diff."""
import sys, re
from importlib.metadata import version
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest
r = CollectorRegistry()
c = Counter("tg_messages_total", "msgs", ["chat"], registry=r); c.labels(chat="1").inc(3)
g = Gauge("tg_active_users", "users", registry=r); g.set(42)
h = Histogram("tg_req_seconds", "latency", registry=r); h.observe(0.25)
lines = generate_latest(r).decode().splitlines()
canon = [re.sub(r"(_created(?:\{[^}]*\})?) .*", r"\1 <WALLCLOCK>", ln) for ln in lines]
open(sys.argv[1], "w").write("\n".join(canon) + "\n")
print(f"prometheus_client {version('prometheus_client')}: {len(canon)} wire lines")
