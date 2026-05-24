from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import httpx
import re
import time
import logging

class ChatRequest(BaseModel):
    message: str

from guardrails import input_guard
from judge import output_judge
from logging_conf import setup_logging

# Prometheus
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response as StarletteResponse
from metrics import (
    REQUESTS_TOTAL,
    ERRORS_TOTAL,
    ATTACKS_DETECTED_TOTAL,
    API_LATENCY,
    LLM_CALL_LATENCY,
    GUARDRAIL_LATENCY,
    QUALITY_SCORE,
    SECURITY_SCORE,
    IN_PROGRESS_REQUESTS,
    compute_quality_score,
    normalize_path,
    status_class,
    registry
)

# ─────────────────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────────────────
setup_logging()
logger = logging.getLogger()

# ─────────────────────────────────────────────────────────────────────────────
# App
# ─────────────────────────────────────────────────────────────────────────────
app = FastAPI(title="CITADEL-Y API", version="1.0.0")

limiter = Limiter(key_func=get_remote_address, default_limits=["5/second"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ─────────────────────────────────────────────────────────────────────────────
LLM_SERVICE_URL = "http://llm_service:8001/query"
KEY_PATTERN = re.compile(r'PHOENIX-\d{2}-[A-Z]+', re.IGNORECASE)

# ─────────────────────────────────────────────────────────────────────────────
# Middleware
# ─────────────────────────────────────────────────────────────────────────────
@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    start = time.perf_counter()
    path = normalize_path(request.url.path)

    IN_PROGRESS_REQUESTS.labels(endpoint=path).inc()

    try:
        response = await call_next(request)
        return response

    finally:
        duration = time.perf_counter() - start
        IN_PROGRESS_REQUESTS.labels(endpoint=path).dec()

        status = response.status_code if 'response' in locals() else 500

        REQUESTS_TOTAL.labels(
            method=request.method,
            endpoint=path,
            status_code=str(status),
        ).inc()

        API_LATENCY.labels(
            endpoint=path,
            status_class=status_class(status),
        ).observe(duration)

        logger.info({
            "event": "request_complete",
            "path": path,
            "status": status,
            "latency_ms": round(duration * 1000, 2),
        })

# ─────────────────────────────────────────────────────────────────────────────
# /metrics
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/metrics", include_in_schema=False)
def metrics():
    return StarletteResponse(
        content=generate_latest(registry),
        media_type=CONTENT_TYPE_LATEST,
    )

# ─────────────────────────────────────────────────────────────────────────────
# /chat
# ─────────────────────────────────────────────────────────────────────────────
@app.post("/chat")
@limiter.limit("5/second")
async def chat(request: Request, payload: ChatRequest):
    endpoint = "/chat"

    # ✅ correctement indenté
    user_message = payload.message

    # ── Input guard ─────────────────────────────
    t0 = time.perf_counter()
    verdict = input_guard(user_message)
    GUARDRAIL_LATENCY.labels(layer="input_guard").observe(time.perf_counter() - t0)

    if verdict.get("block"):
        ATTACKS_DETECTED_TOTAL.labels(layer="input_guard").inc()
        SECURITY_SCORE.labels(endpoint=endpoint).set(0.0)
        raise HTTPException(403, "Requête bloquée")

    # ── LLM call ────────────────────────────────
    t1 = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=600.0) as client:
            resp = await client.post(LLM_SERVICE_URL, json={"message": user_message})
            resp.raise_for_status()
            llm_response = resp.json().get("response", "")
    except Exception as e:
        LLM_CALL_LATENCY.observe(time.perf_counter() - t1)
        ERRORS_TOTAL.labels(endpoint=endpoint, error_type="llm_error").inc()
        logger.error({"event": "llm_error", "error": str(e)})
        raise HTTPException(500, "Erreur LLM")

    LLM_CALL_LATENCY.observe(time.perf_counter() - t1)

    # ── Regex detection ─────────────────────────
    if KEY_PATTERN.search(llm_response):
        ATTACKS_DETECTED_TOTAL.labels(layer="key_regex").inc()
        SECURITY_SCORE.labels(endpoint=endpoint).set(0.0)
        return {"response": "Information confidentielle"}

    # ── Output judge ────────────────────────────
    t2 = time.perf_counter()
    is_safe, reason = output_judge.scan(llm_response)
    GUARDRAIL_LATENCY.labels(layer="output_judge").observe(time.perf_counter() - t2)

    if not is_safe:
        ATTACKS_DETECTED_TOTAL.labels(layer="output_judge").inc()
        SECURITY_SCORE.labels(endpoint=endpoint).set(0.0)
        return {"response": "Information bloquée"}

    # ── Final metrics ───────────────────────────
    quality = compute_quality_score(llm_response)

    QUALITY_SCORE.labels(endpoint=endpoint).set(quality)
    SECURITY_SCORE.labels(endpoint=endpoint).set(1.0)

    return {"response": llm_response}

# ─────────────────────────────────────────────────────────────────────────────
# /health
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok"}