"""UmaBuild API - No-code horse racing AI builder backend."""

import logging
import os

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Default root logger to INFO so services.* logger.info() reaches Cloud Run.
# Without this Python defaults root to WARNING and every operational log
# (parquet load, agent stats progress, paywall masking) is silently dropped.
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

from routers import features, learn, models, results, stripe  # noqa: E402

logger = logging.getLogger(__name__)

# Hard-fail in production if the Supabase service-role key is missing,
# so a misconfigured deploy can't silently fall back to in-memory job
# state (which would lose jobs across Cloud Run instances).
if os.environ.get("ENV") == "production" and not os.environ.get("SUPABASE_SERVICE_ROLE_KEY"):
    raise RuntimeError(
        "SUPABASE_SERVICE_ROLE_KEY is required in production "
        "(job_store / rate_limit cannot use in-memory fallback at scale)."
    )

# Sentry error tracking (Free: 5k events/month)
SENTRY_DSN = os.environ.get("SENTRY_DSN", "")
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        traces_sample_rate=0.1,
        environment=os.environ.get("SENTRY_ENV", "production"),
    )
    logger.info("Sentry initialized")

app = FastAPI(title="UmaBuild API", version="0.2.0")

ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
    if o.strip()
]
ALLOWED_ORIGIN_REGEX = os.environ.get("ALLOWED_ORIGIN_REGEX") or None

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=ALLOWED_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(features.router, prefix="/api")
app.include_router(learn.router, prefix="/api")
app.include_router(results.router, prefix="/api")
app.include_router(stripe.router, prefix="/api")
app.include_router(models.router, prefix="/api")


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error("Unhandled: %s", exc, exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/api/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
