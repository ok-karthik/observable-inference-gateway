import time
from typing import Callable, override

from fastapi import Request, Response
from fastapi.routing import APIRoute
from prometheus_client import Counter, Histogram
from rich.console import Console

# --- Prometheus Metrics Definitions ---

REQUEST_COUNT = Counter(
    "inference_requests_total",
    "Total inference requests",
    labelnames=["endpoint", "method", "status", "model"],
)

REQUEST_LATENCY = Histogram(
    "inference_request_latency_seconds",
    "Latency of requests in seconds",
    labelnames=["endpoint", "method", "status", "model"],
    buckets=[0.001, 0.002, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5],
)

HEALTH_COUNT = Counter(
    "inference_health_total", "Total health requests", labelnames=["endpoint", "status"]
)


def record_metrics(
    endpoint: str, method: str, start_time: float, model: str, status: int
):
    """Calculates request latency and records metrics into Prometheus counters and histograms."""
    latency_seconds = time.perf_counter() - start_time
    REQUEST_COUNT.labels(
        endpoint=endpoint, method=method, status=status, model=model
    ).inc()
    REQUEST_LATENCY.labels(
        endpoint=endpoint, method=method, status=status, model=model
    ).observe(latency_seconds)


# --- Custom FastAPI Route for Telemetry Instrumentation ---


class TelemetryRoute(APIRoute):
    """
    A custom route class that automatically measures latency and records
    Prometheus metrics for any endpoint that uses it.
    """

    @override
    def get_route_handler(self) -> Callable:
        # 1. Grab the default route runner from FastAPI.
        # This is the function that actually executes your endpoint code.
        run_endpoint = super().get_route_handler()

        # 2. Define our wrapper function (the closure).
        # This function receives the raw HTTP Request and returns the Response.
        async def route_runner_with_metrics(request: Request) -> Response:
            start_time = time.perf_counter()
            status_code = 200

            try:
                # Execute the endpoint logic
                response: Response = await run_endpoint(request)
                status_code = response.status_code
                return response

            except Exception as e:
                # If the code inside the route crashed, mark it as 500
                status_code = 500
                Console().print_exception(show_locals=True)
                raise e

            finally:
                # This block ALWAYS runs (even if an exception was raised).
                # We fetch the model if it was set in request.state, otherwise default to "default".
                model_name = getattr(request.state, "model", "default")

                # Record the metrics safely using our helper function defined above
                record_metrics(
                    endpoint=request.url.path,
                    method=request.method,
                    start_time=start_time,
                    model=model_name,
                    status=status_code,
                )

        # 3. Return the wrapper function.
        # FastAPI will save this function and run it whenever a user hits the endpoint.
        return route_runner_with_metrics
