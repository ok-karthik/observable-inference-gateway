import json
import os
import sys
import uuid
from contextlib import asynccontextmanager

import httpx
import structlog, logging
from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from rich.console import Console
from rich.traceback import install
from opentelemetry import metrics

load_dotenv()

HOST = os.getenv("HOST", "http://localhost:11434")
MODEL = os.getenv("MODEL", "gemma3:1b")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.client = httpx.AsyncClient(base_url=HOST, timeout=60.0)
    yield
    await app.state.client.aclose()


app = FastAPI(lifespan=lifespan, title="Inference Model Service", version="1.0")

# Logging
install(show_locals=True)
logging.basicConfig(level=logging.INFO)
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso", utc=False),
        structlog.stdlib.render_to_log_kwargs,
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
)
logger = structlog.get_logger()


class ChatRequest(BaseModel):
    model: str = MODEL
    content: str = "How are you?"

meter = metrics.get_meter("model-service")
inference_counter = meter.create_counter("inference_requests_total")


@app.post("/chat/stream", response_class=StreamingResponse)
async def chat_stream(chatreq: ChatRequest, request: Request) -> StreamingResponse:
    async def generate_stream():
        """
        A generator function to return a streaming response
        """
        request_id = str(uuid.uuid4())
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

                inference_counter.add(1, {"model": chatreq.model, "status": "success"})

                async for line in response.aiter_lines():
                    if line:
                        yield json.dumps(map_chunk(json.loads(line), request_id)) + "\n"
                logger.info(f"Model: {chatreq.model}, Tokens: {response}")
        except Exception as e:
            logger.error(f"Stream error: {e}")
            Console().print_exception(show_locals=True)
            yield f"\n[Stream connection failed: {e}]"

    return StreamingResponse(generate_stream(), media_type="application/x-ndjson")


@app.post("/chat")
async def chat_non_stream(chatreq: ChatRequest, request: Request):
    request_id = str(uuid.uuid4())
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

        inference_counter.add(1, {"model": chatreq.model, "status": "success"})

        return map_chunk(response.json(), request_id)
    except httpx.HTTPError as exc:
        logger.error(f"HTTP connection error: {exc}")
        Console().print_exception(show_locals=True)

        status_code = (
            exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else 503
        )
        raise HTTPException(status_code=status_code, detail=str(exc))


def map_chunk(chunk: dict, request_id: str) -> dict:
    content = chunk.get("message", {}).get("content", "")

    # 1. If it's a streaming token chunk (not done yet), keep it minimal
    if not chunk.get("done", False):
        return {"content": content, "request_id": request_id}

    # 2. If it's the final chunk (or non-streaming response), include usage and metrics
    prompt_tokens = chunk.get("prompt_eval_count", 0)
    completion_tokens = chunk.get("eval_count", 0)
    eval_duration_sec = chunk.get("eval_duration", 0) / 1e9

    return {
        "content": chunk.get("message", {}).get("content", ""),
        "request_id": request_id,
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

@app.get("/health")
async def health_check() -> dict:
    return {"status": "ok"}


@app.get("/ready")
async def readiness_check() -> dict:
    return {"status": "ready", "model_loaded": True}
