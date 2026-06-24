import random
from anyio import sleep
from fastapi import FastAPI, Request
from pydantic import BaseModel
import time, uuid, structlog
from prometheus_client import Histogram
from prometheus_fastapi_instrumentator import Instrumentator, metrics
from typing import Callable

app = FastAPI(title="Inference Gateway", version="1.0")

def record_model_latency() -> Callable[[metrics.Info], None]:
    MODEL_LATENCY = Histogram(
        "model_latency_seconds", 
        "Latency of models in seconds", 
        labelnames=("model",),
        buckets=(0.001, 0.002, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5)
    )
    def model_latency_observer(info: metrics.Info):
        if info.modified_handler == "/v1/predict":
            model_name = getattr(info.request.state, "model", "unknown")
            MODEL_LATENCY.labels(
                model=model_name
            ).observe(info.modified_duration)
    return model_latency_observer

instrumentator = Instrumentator()
instrumentator.add(
    metrics.latency(
        buckets=(0.001, 0.002, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5)
    )
).add(
    record_model_latency()
)

instrumentator.instrument(app).expose(app)

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso", utc=False),
        structlog.processors.JSONRenderer()
    ]
)
logger = structlog.get_logger()

class PredictRequest(BaseModel):
    text: str
    max_tokens: int = 100
    model: str = "default"

class PredictResponse(BaseModel):
    request_id: uuid.UUID
    result: str
    latency_ms: float
    tokens_used: int

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.perf_counter()
    response = await call_next(request)
    latency_seconds = round(float(time.perf_counter() - start_time), 4)
    response.headers["X-Process-Time"] = str(latency_seconds)
    return response

@app.post("/v1/predict", response_model=PredictResponse)
async def predict(req: PredictRequest, request: Request):
    start_time = time.perf_counter()
    request_id = str(uuid.uuid4())
    logger.info("predict_request", request_id=request_id, request_payload=req)

    latency_ms = round(float((time.perf_counter() - start_time) * 1000), 4)
    tokens_used=len(req.text.split())
    request.state.model=req.model

    await sleep(random.uniform(0, 1))
    print(request.state)

    result = f"[MOCK] Processed {tokens_used} tokens with model {req.model}"
    logger.info("predict_response", request_id=request_id, latency_ms=latency_ms, result=result, tokens_used=tokens_used)
    
    return {
        "request_id": request_id, 
        "latency_ms": latency_ms,
        "result": result,
        "tokens_used": tokens_used
    }

@app.get("/health")
async def health_check() -> dict:
    return {"status": "ok"}

@app.get("/ready")
async def readiness_check() -> dict:
    return {"status": "ready", "model_loaded": True}
