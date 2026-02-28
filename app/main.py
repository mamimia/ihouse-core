import os
import logging
import uuid
from fastapi import FastAPI, HTTPException, Header, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from dotenv import load_dotenv

from core.api import CoreAPI
from core.db.sqlite import Sqlite
from core.db.config import db_path
from app.db_adapter import SqliteAdapter


# ----------------------------
# Logging Configuration
# ----------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger("ihouse-api")


# ----------------------------
# Load Environment
# ----------------------------

load_dotenv()

API_KEY = os.getenv("IHOUSE_API_KEY")

if not API_KEY:
    raise RuntimeError("IHOUSE_API_KEY must be set in environment")


def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")


# ----------------------------
# HTTP Event Contract
# ----------------------------

class EventEnvelope(BaseModel):
    type: str = Field(..., description="Domain event type")
    version: int = Field(..., ge=1)
    payload: Dict[str, Any]
    idempotency_key: str = Field(..., description="Required idempotency key")


# ----------------------------
# Composition Root
# ----------------------------

sqlite = Sqlite(path=db_path())
adapter = SqliteAdapter(sqlite)
core = CoreAPI(db=adapter)

app = FastAPI()


# ----------------------------
# Middleware – Request ID
# ----------------------------

@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id

    logger.info(f"[{request_id}] Incoming {request.method} {request.url.path}")

    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
    except Exception:
        logger.exception(f"[{request_id}] Unhandled error")
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )


# ----------------------------
# Endpoints
# ----------------------------

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/events", dependencies=[Depends(verify_api_key)])
def append_event(event: EventEnvelope, request: Request):
    try:
        result = core.ingest.append_event(
            {
                "type": event.type,
                "version": event.version,
                "payload": event.payload,
            },
            idempotency_key=event.idempotency_key,
        )
        return {"event_id": result.event_id}
    except Exception:
        logger.exception(f"[{request.state.request_id}] Event append failed")
        raise HTTPException(status_code=400, detail="Invalid event")


@app.get("/query/{name}", dependencies=[Depends(verify_api_key)])
def query(name: str, request: Request):
    try:
        result = core.query.fetch(name, {})
        return {"rows": result.rows}
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid query")
    except Exception:
        logger.exception(f"[{request.state.request_id}] Query failed")
        raise HTTPException(status_code=500, detail="Internal error")
