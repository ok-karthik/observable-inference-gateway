# 🤖 Agent & Developer Guidelines (AGENTS.md)

Welcome! This file provides context, architectural constraints, and styling/tooling rules for AI coding assistants (and human developers) working on the **Observable Inference Gateway** codebase.

---

## 📂 Codebase Layout

* **/gateway**: Entry point service. Acts as a reverse proxy.
* **/model_service**: Service interfacing with Ollama, hosting custom telemetry (`metrics.py`).
* **pyrightconfig.json**: Configures type-checking environments for both subprojects.
* **docker-compose.yaml**: Multi-container service configuration.

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
* Keep [pyrightconfig.json](file:///Users/karthik.orugonda/lab/observable-inference-gateway/pyrightconfig.json) updated with separate `executionEnvironments` mapping the individual service `.venv` folders using `extraPaths` (since `venv` and `venvPath` are not valid config options inside an execution environment block and must be declared at the root level). This allows the editor to resolve imports correctly.
* ⚠️ **Strict Constraint**: Ensure there are **no trailing commas** in `pyrightconfig.json`. Standard JSON parsers used by Pyright will fail to parse the file, causing it to ignore all environment paths and fallback to system defaults.

### Method Overrides (`reportImplicitOverride`)
* Currently, the `"reportImplicitOverride": "none"` rule is set in the configuration to silence implicit override warnings.
* If you or the user wish to enforce explicit overrides, remove this config line and decorate any overriding class methods using `@override` from the standard library:
  ```python
  from typing import override

  class CustomRoute(APIRoute):
      @override
      def get_route_handler(self) -> Callable:
          ...
  ```
  *(Note: Since this codebase targets Python 3.14, `@override` is imported directly from `typing` rather than `typing_extensions`).*

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
