"""Cross-version parity harness for the web framework: fastapi + starlette + uvicorn.

Killer question for a web framework is NOT "does the app import" — it is do the
MECHANISMS still fire: lifespan/startup, every middleware layer, exception
handlers, CORS preflight, gzip, and dependency overrides. A scar worth
repeating: `TestClient(app)` built WITHOUT a `with` block never runs startup at
all — tests/test_improvements.py and tests/test_api_rate_limiting.py both do
exactly that today, so nothing in this repo has ever exercised any of it.

Builds a small FastAPI app IN-PROCESS that mirrors tgstats/web/app.py's own
mechanisms — a lifespan handler, two `@app.middleware("http")` layers shaped
like add_request_id, CORS, GZip, a custom-exception -> JSON-shape handler
mirroring error_handlers.py's ErrorResponse, and a dependency + override — and
records observable behaviour for each. Deliberately self-contained (no tgstats
import): importing the real app needs BOT_TOKEN/DATABASE_URL and the full prod
dependency graph just to construct, which a bare probe venv holding only
fastapi/starlette/uvicorn does not have.

    venv/bin/python scripts/framework_parity.py /tmp/fw_old.json
    probe/bin/python scripts/framework_parity.py /tmp/fw_new.json
    diff /tmp/fw_old.json /tmp/fw_new.json
"""

import json
import re
import sys
import uuid
from contextlib import asynccontextmanager
from importlib.metadata import version

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from pydantic import BaseModel

# Mask only what is genuinely non-deterministic: the uuid4 request id generated
# when the caller sends none. Everything else that moves is a real behaviour
# change and must show up in the diff.
MASKS = [
    (re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"), "<UUID>"),
]


def mask(value):
    if isinstance(value, str):
        for pattern, repl in MASKS:
            value = pattern.sub(repl, value)
        return value
    if isinstance(value, dict):
        return {k: mask(v) for k, v in value.items()}
    if isinstance(value, list):
        return [mask(v) for v in value]
    return value


class AppError(Exception):
    """Mirrors tgstats.core.exceptions.TgStatsError's shape: message + details."""

    def __init__(self, message, details=None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundAppError(AppError):
    """Mirrors NotFoundError, a subclass whose OWN handler must win over the
    AppError catch-all registered below it — real MRO-dispatch behaviour."""


class Item(BaseModel):
    name: str
    qty: int


def get_greeting():
    return "hello"


def error_shape(code, exc, request_id):
    """Mirrors error_handlers.ErrorResponse.to_dict()."""
    body = {"error": {"code": code, "message": exc.message}}
    if exc.details:
        body["error"]["details"] = exc.details
    if request_id:
        body["request_id"] = request_id
    return body


def validation_error_shape(exc, request_id):
    """Mirrors error_handlers.validation_error_handler exactly, including its
    field extraction. That handler reads exc.errors()[i]["loc"/"msg"/"type"]
    directly — if fastapi ever renames or drops one of those keys, THIS raises
    (visible as a 500 in the diff) instead of silently returning a different
    shape. The real app always returns this wrapped shape, never fastapi's
    raw default, so this is the 422 body a real caller actually sees.
    """
    errors = [
        {
            "field": ".".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"],
        }
        for error in exc.errors()
    ]
    body = {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "Request validation failed",
            "details": {"errors": errors},
        }
    }
    if request_id:
        body["request_id"] = request_id
    return body


def build_app(events):
    @asynccontextmanager
    async def lifespan(app):
        events.append("startup")
        yield
        events.append("shutdown")

    app = FastAPI(lifespan=lifespan)

    # Mirrors app.py: app.add_middleware(GZipMiddleware, minimum_size=1000) and
    # the CORSMiddleware block right after it (same kwargs, a fixed origin list
    # standing in for settings.cors_origins).
    app.add_middleware(GZipMiddleware, minimum_size=500)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://allowed.example"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
    )

    # Mirrors app.py's add_request_id: read-or-generate, bind to request.state,
    # echo on the response. A second stacked layer proves it is not just ONE
    # middleware that still fires but the whole stack.
    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    @app.middleware("http")
    async def add_second_layer(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Probe-Second-Layer"] = "seen"
        return response

    async def not_found_handler(request: Request, exc: NotFoundAppError):
        request_id = getattr(request.state, "request_id", None)
        return JSONResponse(status_code=404, content=error_shape("NOT_FOUND", exc, request_id))

    async def generic_handler(request: Request, exc: AppError):
        request_id = getattr(request.state, "request_id", None)
        return JSONResponse(
            status_code=500, content=error_shape("APPLICATION_ERROR", exc, request_id)
        )

    async def validation_handler(request: Request, exc: RequestValidationError):
        request_id = getattr(request.state, "request_id", None)
        return JSONResponse(status_code=422, content=validation_error_shape(exc, request_id))

    # Registration order mirrors register_error_handlers: specific subclass
    # first, base-class catch-all after.
    app.add_exception_handler(RequestValidationError, validation_handler)
    app.add_exception_handler(NotFoundAppError, not_found_handler)
    app.add_exception_handler(AppError, generic_handler)

    @app.get("/ok")
    async def ok():
        return {"status": "ok"}

    @app.get("/big")
    async def big():
        # Comfortably over minimum_size so GZipMiddleware always compresses it.
        return {"data": "x" * 2000}

    @app.get("/boom-notfound")
    async def boom_notfound():
        raise NotFoundAppError("missing thing", details={"id": 1})

    @app.get("/boom-generic")
    async def boom_generic():
        raise AppError("broke")

    @app.post("/validate")
    async def validate(item: Item):
        return {"name": item.name, "qty": item.qty}

    @app.get("/dep")
    async def dep(greeting: str = Depends(get_greeting)):
        return {"greeting": greeting}

    return app


KEEP_HEADERS = {
    "content-encoding",
    "access-control-allow-origin",
    "access-control-allow-methods",
    "access-control-allow-headers",
    "access-control-allow-credentials",
    "x-request-id",
    "x-probe-second-layer",
}


def record(resp):
    """Canonicalize one httpx.Response into comparable, masked data."""
    try:
        body = resp.json()
    except ValueError:
        body = resp.text
    headers = {k: v for k, v in resp.headers.items() if k.lower() in KEEP_HEADERS}
    return {"status": resp.status_code, "headers": mask(headers), "body": mask(body)}


def probe():
    out = {}
    events = []
    app = build_app(events)

    # --- lifespan: proven only by actually entering the `with` block. -------
    out["lifespan_before_enter"] = list(events)
    with TestClient(app) as client:
        out["lifespan_during_context"] = list(events)

        # --- normal 200 route + two stacked middleware layers ---------------
        out["route_200"] = record(client.get("/ok", headers={"X-Request-ID": "fixed-id"}))
        out["route_200_generated_request_id"] = record(client.get("/ok"))

        # --- unmatched route: the framework's own 404, not a raised one -----
        out["route_404_unmatched"] = record(client.get("/no-such-route"))

        # --- custom exception -> JSON shape (specific subclass must win) ----
        out["exception_handler_notfound"] = record(
            client.get("/boom-notfound", headers={"X-Request-ID": "fixed-id"})
        )
        out["exception_handler_catchall"] = record(
            client.get("/boom-generic", headers={"X-Request-ID": "fixed-id"})
        )

        # --- 422 validation body SHAPE: a public API contract ---------------
        out["route_422_validation"] = record(client.post("/validate", json={"qty": "not-a-number"}))

        # --- CORS preflight: allowed origin vs a disallowed one --------------
        out["cors_preflight_allowed"] = record(
            client.options(
                "/ok",
                headers={
                    "Origin": "http://allowed.example",
                    "Access-Control-Request-Method": "GET",
                    "Access-Control-Request-Headers": "X-Custom-Header",
                },
            )
        )
        out["cors_preflight_disallowed_origin"] = record(
            client.options(
                "/ok",
                headers={
                    "Origin": "http://not-allowed.example",
                    "Access-Control-Request-Method": "GET",
                },
            )
        )
        out["cors_actual_request"] = record(
            client.get("/ok", headers={"Origin": "http://allowed.example"})
        )

        # --- gzip: a large response is compressed, a tiny one is not --------
        out["gzip_large_response"] = record(client.get("/big", headers={"Accept-Encoding": "gzip"}))
        out["gzip_small_response_not_compressed"] = record(
            client.get("/ok", headers={"Accept-Encoding": "gzip"})
        )

        # --- dependency injection + app.dependency_overrides -----------------
        out["dependency_default"] = record(client.get("/dep"))
        app.dependency_overrides[get_greeting] = lambda: "overridden"
        out["dependency_overridden"] = record(client.get("/dep"))
        del app.dependency_overrides[get_greeting]

    out["lifespan_after_exit"] = list(events)
    return out


def main():
    if len(sys.argv) < 2:
        sys.exit(f"usage: {sys.argv[0]} <out.json>")

    result = probe()
    with open(sys.argv[1], "w") as handle:
        json.dump(result, handle, indent=1, sort_keys=True)

    versions = " | ".join(f"{pkg} {version(pkg)}" for pkg in ("fastapi", "starlette", "uvicorn"))
    print(f"{versions}: {len(result)} mechanism checks recorded")


if __name__ == "__main__":
    main()
