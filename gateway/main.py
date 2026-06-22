# from auto_metrics_inference_gateway import logger
import logging
import os
from urllib import response

import httpx
from fastapi import FastAPI, HTTPException

# from auto_metrics_inference_gateway import logger
# import logger
from httpcore import request

app = FastAPI()
client = httpx.AsyncClient(timeout=10.0)
logger = logging.getLogger(__name__)

MODEL_SERVICE_URL = os.getenv("MODEL_SERVICE_URL", "http://model-service:8001")


@app.get("/health")
async def health_check():
    try:
        response = await client.get(MODEL_SERVICE_URL + "/health")
        return response.json()
    except httpx.ConnectError as e:
        logger.error(
            f"Could not connect to model service {MODEL_SERVICE_URL}. Error: {e}"
        )
        raise HTTPException(status_code=503, detail="Model service unavailable")
    except Exception as e:
        logger.error(
            f"An error occurred while connecting to model service {MODEL_SERVICE_URL}. Error: {e}"
        )
        raise HTTPException(status_code=500, detail="Unexpected Error occurred")


@app.get("/ready")
async def readiness_check() -> dict:
    response = await client.get(MODEL_SERVICE_URL + "/ready")
    return response.json()


# @app.post("/v1/predict")
# async def readiness_check() -> dict:
#    response = await client.get(MODEL_SERVICE_URL + "/ready")
#    return response.json()
