import os
import logging
import uuid
import re
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Header, Depends, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Any, Dict
from dotenv import load_dotenv

from core.runtime import build_core


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("ihouse-api")

load_dotenv(dotenv_path=".env")

API_KEY = os.getenv("IHOUSE_API_KEY")
if not API_KEY:
    raise RuntimeError("IHOUSE_API_KEY must be set in environment")


# =========================
# Canonical Event Gate
# =========================

EXTERNAL_CANONICAL = {
    "BOOKING_CREATED",
    "BOOKING_UPDATED",
    "BOOKING_CANCELED",
    "BOOKING_CHECKED_IN",
    "BOOKING_CHECKED_OUT",
    "BOOKING_SYNC_ERROR",
    "AVAILABILITY_UPDATED",
    "RATE_UPDATED",
}

INTERNAL_ONLY = {
    "STATE_UPSERT",
}

SCREAMING = re.compile(r"^[A-Z][A-Z0-9_]*$")


def validate_event_type(event_type: str) -> None:
    if not isinstance(event_type, str) or not event_type:
        raise HTTPException(status_code=400, detail="Invalid event type")

    if not SCREAMING.match(event_type):
        raise HTTPException(status_code=400, detail="Event type must be SCREAMING_SNAKE_CASE")

    if event_type in INTERNAL_ONLY:
        raise HTTPException(status_code=400, detail="Event type is internal-only")

    if event_type not in EXTERNAL_CANONICAL:
        raise HTTPException(status_code=400, detail="Unknown canonical event type")


def _is_no_route_message(msg: str) -> bool:
    if not msg:
        return False
    return ("NO_ROUTE" in msg) or ("Unknown canonical event type" in msg)


# =========================
# Auth
# =========================

def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")


# =========================
# Models
# =========================

class Actor(BaseModel):
    actor_id: str = Field(..., min_length=1)
    role: str = Field(..., min_length=1)


class Idempotency(BaseModel):
    request_id: str = Field(..., min_length=1)


class CoreEnvelope(BaseModel):
    type: str = Field(..., min_length=1)
    idempotency: Idempotency
    actor: Actor
    payload: Dict[str, Any]


# =========================
# App Init
# =========================

core = build_core()
app = FastAPI()


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
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/health")
def health():
    return {"status": "ok"}


def _ensure_actor(payload: Dict[str, Any], actor_id: str, role: str) -> None:
    a = payload.get("actor")
    if not isinstance(a, dict):
        payload["actor"] = {"actor_id": actor_id, "role": role}
        return

    if not isinstance(a.get("actor_id"), str) or not a.get("actor_id"):
        a["actor_id"] = actor_id

    if not isinstance(a.get("role"), str) or not a.get("role"):
        a["role"] = role


def _ensure_idempotency(payload: Dict[str, Any], request_id: str) -> None:
    idem = payload.get("idempotency")
    if not isinstance(idem, dict):
        payload["idempotency"] = {"request_id": request_id}
        return

    if not isinstance(idem.get("request_id"), str) or not idem.get("request_id"):
        idem["request_id"] = request_id


@app.post("/events", dependencies=[Depends(verify_api_key)])
def append_event(envelope: CoreEnvelope, request: Request):
    validate_event_type(envelope.type)

    occurred_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    payload = dict(envelope.payload)
    _ensure_actor(payload, envelope.actor.actor_id, envelope.actor.role)
    _ensure_idempotency(payload, envelope.idempotency.request_id)

    try:
        result = core.ingest.append_event(
            {
                "type": envelope.type,
                "idempotency": {"request_id": envelope.idempotency.request_id},
                "actor": {"actor_id": envelope.actor.actor_id, "role": envelope.actor.role},
                "payload": payload,
                "occurred_at": occurred_at,
            },
            idempotency_key=envelope.idempotency.request_id,
        )

        return {"event_id": result.event_id}

    except ValueError as e:
        msg = str(e) or "Invalid event"
        logger.warning(f"[{request.state.request_id}] Event rejected detail={msg}")

        if _is_no_route_message(msg):
            return JSONResponse(
                status_code=status.HTTP_202_ACCEPTED,
                content={
                    "status": "accepted",
                    "persisted": True,
                    "executed": False,
                    "reason": "NO_ROUTE",
                    "event_type": envelope.type,
                    "envelope_id": envelope.idempotency.request_id,
                },
            )

        raise HTTPException(status_code=400, detail=msg)

    except Exception as e:
        msg = f"{type(e).__name__}:{str(e) or 'NO_MESSAGE'}"
        logger.exception(f"[{request.state.request_id}] Event append failed detail={msg}")
        raise HTTPException(status_code=400, detail=msg)


@app.get("/query/{name}", dependencies=[Depends(verify_api_key)])
def query(name: str, request: Request):
    try:
        result = core.query.fetch(name, {})
        return {"rows": result.rows}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e) or "Invalid query")
    except Exception:
        logger.exception(f"[{request.state.request_id}] Query failed")
        raise HTTPException(status_code=500, detail="Internal error")
