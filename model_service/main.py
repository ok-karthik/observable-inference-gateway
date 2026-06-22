import json
import os
import sys
import uuid
from contextlib import asynccontextmanager

import httpx
import structlog
from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from prometheus_client import make_asgi_app
from pydantic import BaseModel
from rich.console import Console
from rich.traceback import install

from metrics import TelemetryRoute

load_dotenv()

HOST = os.getenv("HOST", "http://localhost:11434")
MODEL = os.getenv("MODEL", "gemma3:1b")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.client = httpx.AsyncClient(base_url=HOST, timeout=60.0)
    yield
    await app.state.client.aclose()


app = FastAPI(lifespan=lifespan, title="Inference Model Service", version="1.0")
predict_router = APIRouter(route_class=TelemetryRoute)

metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# Logging
# Determine if we are running in a local terminal (interactive console)
is_local = sys.stderr.isatty()
install(show_locals=True)
processors = [
    structlog.processors.TimeStamper(fmt="iso", utc=False),
]
if is_local:
    # Local Development: Pretty colors, console layout, and rich tracebacks
    from structlog.dev import ConsoleRenderer, plain_traceback

    processors.append(
        ConsoleRenderer(exception_formatter=plain_traceback)  # or rich traceback
    )
else:
    # Production (Docker/Kubernetes): Flat, searchable JSON logs
    processors.append(structlog.processors.JSONRenderer())
structlog.configure(processors=processors)
logger = structlog.get_logger()


class ChatRequest(BaseModel):
    model: str = MODEL
    content: str = "How are you?"


@predict_router.post("/chat/stream", response_class=StreamingResponse)
async def chat_stream(chatreq: ChatRequest, request: Request) -> StreamingResponse:
    async def generate_stream():
        """
        A generator function to return a streaming response
        """
        try:
            async with app.state.client.stream(
                "POST",
                "/api/chat",
                json={
                    "model": chatreq.model,
                    "messages": [{"role": "user", "content": chatreq.content}],
                    "stream": True,
                },
            ) as response:
                response.raise_for_status()
                request.state.model = chatreq.model

                async for line in response.aiter_lines():
                    if line:
                        yield json.dumps(map_chunk(json.loads(line))) + "\n"
                logger.info(f"Model: {chatreq.model}, Tokens: {response}")
        except Exception as e:
            logger.error(f"Stream error: {e}")
            Console().print_exception(show_locals=True)
            yield f"\n[Stream connection failed: {e}]"

    return StreamingResponse(generate_stream(), media_type="application/x-ndjson")


@predict_router.post("/chat")
async def chat_non_stream(chatreq: ChatRequest, request: Request):
    try:
        response = await app.state.client.post(
            "/api/chat",
            json={
                "model": chatreq.model,
                "messages": [{"role": "user", "content": chatreq.content}],
                "stream": False,
            },
        )

        response.raise_for_status()
        request.state.model = chatreq.model

        return map_chunk(response.json())
    except httpx.HTTPError as exc:
        logger.error(f"HTTP connection error: {exc}")
        Console().print_exception(show_locals=True)

        status_code = (
            exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else 503
        )
        raise HTTPException(status_code=status_code, detail=str(exc))


def map_chunk(chunk: dict) -> dict:
    content = chunk.get("message", {}).get("content", "")

    # 1. If it's a streaming token chunk (not done yet), keep it minimal
    if not chunk.get("done", False):
        return {"content": content}

    # 2. If it's the final chunk (or non-streaming response), include usage and metrics
    prompt_tokens = chunk.get("prompt_eval_count", 0)
    completion_tokens = chunk.get("eval_count", 0)
    eval_duration_sec = chunk.get("eval_duration", 0) / 1e9

    return {
        "content": chunk.get("message", {}).get("content", ""),
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
        "metrics": {
            "total_duration_sec": round(chunk.get("total_duration", 0) / 1e9, 4),
            "tokens_per_sec": round(completion_tokens / eval_duration_sec, 2)
            if eval_duration_sec > 0
            else 0.0,
        },
    }


app.include_router(predict_router)

# @app.middleware("http")
# async def add_process_time_header(request: Request, call_next):
#    response = await call_next(request)
#    return response


# @predict_router.post("/v1/predict", response_model=PredictResponse)
# async def predict(req: PredictRequest, request: Request):
#    start_time = time.perf_counter()
#    request_id = str(uuid.uuid4())
#    logger.info("predict_request", request_id=request_id, request_payload=req)
#
#    # Mock model processing time
#    await sleep(random.uniform(0, 1))
#    # await asyncio.sleep(random_sleep)
#
#    # request.state.model = req.model
#    latency_ms = float((time.perf_counter() - start_time) * 1000)
#
#    request.state.model = req.model
#
#    tokens_used = len(req.text.split())
#    result = f"[MOCK] Processed {tokens_used} tokens with model {req.model}"
#    logger.info(
#        "predict_response",
#        request_id=request_id,
#        latency_ms=latency_ms,
#        result=result,
#        tokens_used=tokens_used,
#    )
#    return {
#        "request_id": request_id,
#        "latency_ms": latency_ms,
#        "result": result,
#        "tokens_used": tokens_used,
#    }


@app.get("/health")
async def health_check() -> dict:
    return {"status": "ok"}


@app.get("/ready")
async def readiness_check() -> dict:
    return {"status": "ready", "model_loaded": True}
