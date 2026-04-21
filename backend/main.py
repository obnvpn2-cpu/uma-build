"""UmaBuild API - No-code horse racing AI builder backend."""

import logging
import os

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from routers import features, learn, models, results, stripe

logger = logging.getLogger(__name__)

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
