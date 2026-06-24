# 🤖 Agent & Developer Guidelines (AGENTS.md)

Welcome! This file provides context, architectural constraints, and styling/tooling rules for AI coding assistants (and human developers) working on the **Observable Inference Gateway** codebase.

---

## 📂 Codebase Layout

* **/gateway**: Entry point service. Acts as a reverse proxy.
* **/model_service**: Service interfacing with Ollama, containing FastAPI routes with integrated OpenTelemetry custom metrics and standard library logging routing.
* **pyrightconfig.json**: Configures type-checking environments for both subprojects.
* **docker-compose.yaml**: Multi-container service configuration (includes application services and the `otel-lgtm` telemetry stack).

---

## 🐍 Python & Dependency Management (`uv`)

This project uses **Python 3.14** and **Astral `uv`** for dependency management. 

* Do NOT use standard `pip` or `requirements.txt`.
* Dependencies are declared in the respective `pyproject.toml` files:
  * [/gateway/pyproject.toml](file:///Users/karthik.orugonda/lab/observable-inference-gateway/gateway/pyproject.toml)
  * [/model_service/pyproject.toml](file:///Users/karthik.orugonda/lab/observable-inference-gateway/model_service/pyproject.toml)
* Each service manages its own isolated virtual environment located in `./.venv` within its directory.
* Run `uv sync` in the respective directory to sync dependencies and regenerate the lockfile (`uv.lock`).

---

## 🔍 Static Analysis & Type Checking (Basedpyright)

We use **Basedpyright** for static analysis.

### `pyrightconfig.json` Configuration
* Keep [pyrightconfig.json](file:///Users/karthik.orugonda/lab/observable-inference-gateway/pyrightconfig.json) updated with separate `executionEnvironments` mapping the individual service `.venv` folders using `extraPaths`. This allows the editor to resolve imports correctly.
* ⚠️ **Strict Constraint**: Ensure there are **no trailing commas** in `pyrightconfig.json`. Standard JSON parsers used by Pyright will fail to parse the file, causing it to ignore all environment paths and fallback to system defaults.

---

## 📊 Telemetry & Observability Guidelines (OpenTelemetry)

We use **OpenTelemetry** for unified metrics, tracing, and logging.

### 1. Instrumentation
We use the **Zero-Code Auto-Instrumentation** agent (`opentelemetry-instrument`) at the container entrypoint level rather than manual SDK bootstrapping in Python code. 
* Avoid manual TracerProvider/MeterProvider initialization in `main.py` unless explicitly required.
* Ensure `model_service/pyproject.toml` lists required instrumentation packages (e.g., `opentelemetry-instrumentation-fastapi`, `opentelemetry-instrumentation-logging`, `opentelemetry-instrumentation-httpx`, `opentelemetry-exporter-otlp`).

### 2. Logging Integration
To ensure OTel captures application logs, `structlog` must be configured to route events through Python's standard `logging` library when running in production (Docker). OTel intercepts standard logging and propagates traces and span context automatically.

### 3. Required Environment Variables
Ensure the following variables are specified in `docker-compose.yaml` for services instrumented by OTel:
* `OTEL_SERVICE_NAME`: Logical name of the service (e.g., `model-service`).
* `OTEL_EXPORTER_OTLP_ENDPOINT`: Endpoint of the collector (e.g., `http://otel-lgtm:4317`).
* `OTEL_LOGS_EXPORTER`: Set to `otlp` to enable log exporting.
* `OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED`: Set to `true` to enable Python standard logging interception.

---

## 🐳 Containerization Guidelines

* Base Image: `python:3.14-slim-bookworm`
* Both Dockerfiles use multi-stage builds. They copy Astral `uv` binaries and utilize Docker cache mounts to speed up dependency synchronization:
  ```dockerfile
  RUN --mount=type=cache,target=/root/.cache/uv \
      uv sync --frozen --no-install-project --no-dev
  ```
* Ensure that any added dependency is registered in `pyproject.toml` and verified via a fresh `docker compose build` before committing.
* Application processes must run under the non-root user `appuser` for container security.

