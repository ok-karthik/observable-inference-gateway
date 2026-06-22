# 🚀 Observable Inference Gateway

An ultra-modern, production-grade LLM inference proxy and gateway built on the cutting-edge **Python 3.14** runtime. It orchestrates traffic to local or remote LLMs (via Ollama) while providing native, high-fidelity observability using FastAPI, Prometheus, and structured logging.

Designed as a **portfolio showcase**, this project demonstrates modern Python development best practices, high-performance containerized microservices, and clean system design.

---

## 🏗️ Architecture Overview

The system is split into two lightweight microservices coordinated via Docker Compose:

1. **Inference Gateway (`gateway`):**
   * Acts as the external entry point (reverse proxy).
   * Decouples clients from the actual model services.
   * Handles service availability probing (`/health` and `/ready`).
2. **Model Service (`model_service`):**
   * Direct interface to the Ollama server.
   * Exposes streaming and non-streaming prediction routes (`/chat` and `/chat/stream`).
   * Hosts a custom ASGI-mounted Prometheus `/metrics` registry.
   * Uses custom FastAPI `APIRoute` telemetry instrumentation to automatically track request latency, volume, and exceptions.

```mermaid
graph TD
    Client[Client Request] -->|Port 8000| Gateway[Inference Gateway]
    Gateway -->|Forward Health/Ready| ModelService[Model Service]
    Client -->|Direct Stream/Chat| ModelService
    ModelService -->|Orchestrate| Ollama[Ollama Local LLM]
    ModelService -->|Expose| Prometheus[/metrics Endpoint]
```

---

## 🛠️ Tech Stack & Key Features

* **Python 3.14-slim (Bookworm):** Leverages the latest runtime improvements and features.
* **FastAPI & Uvicorn:** Asynchronous HTTP framework for low-latency streaming endpoints.
* **Astral `uv`:** Used for blazing-fast package installation, pinning, and multi-stage Docker build caching.
* **Custom Telemetry Layer (`APIRoute`):** Instead of standard high-overhead middleware, latency and counters are hooked directly into FastAPI's route handler pipeline.
* **Prometheus Metrics:** Native export of inference statistics:
  * `inference_requests_total` (Labeled by endpoint, method, status code, and LLM model)
  * `inference_request_latency_seconds` (Latency histogram)
  * `inference_health_total` (Health check counts)
* **Structured Logging:** Unified `structlog` & `rich` system displaying clean, colorized terminal output locally and flat JSON logs in production.

---

## 🚦 Getting Started

### Prerequisites

* [Docker & Docker Compose](https://docs.docker.com/get-docker/)
* [Ollama](https://ollama.com/) (running on your host machine)
* Python 3.14+ (if running locally without containers)

### Running with Docker Compose

1. **Start Ollama** and ensure you have a model downloaded (e.g. `gemma3:1b`):
   ```bash
   ollama pull gemma3:1b
   ```

2. **Configure Environment:**
   Create a `.env` file in the `model_service` directory if you need to point to a custom Ollama host:
   ```env
   HOST=http://host.docker.internal:11434
   MODEL=gemma3:1b
   ```

3. **Spin up the stack:**
   ```bash
   docker compose up --build
   ```

4. **Verify the services:**
   * Gateway: [http://localhost:8000/health](http://localhost:8000/health)
   * Model Service: [http://localhost:8001/health](http://localhost:8001/health)
   * Prometheus Metrics: [http://localhost:8001/metrics](http://localhost:8001/metrics)

---

## 🧪 API Usage Examples

### Non-streaming Chat Request
```bash
curl -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -d '{"model": "gemma3:1b", "content": "Explain quantum computing in one sentence."}'
```

### Streaming Chat Request
```bash
curl -N -X POST http://localhost:8001/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"model": "gemma3:1b", "content": "Count from 1 to 5."}'
```

---

## 📊 Observability

Custom telemetry is handled inside `model_service/metrics.py`. It wraps the route handler (`APIRoute.get_route_handler`) allowing it to access `request.state` and automatically calculate precise execution time even in the case of failures:

```python
class TelemetryRoute(APIRoute):
    def get_route_handler(self) -> Callable:
        run_endpoint = super().get_route_handler()
        async def route_runner_with_metrics(request: Request) -> Response:
            # ... tracks latency, catches exceptions, sends to Prometheus registry
```
