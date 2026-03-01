from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Literal

ApplyResult = Literal["APPLIED", "REJECTED", "NOOP"]

@dataclass(frozen=True)
class Actor:
    actor_id: str
    role: str

@dataclass(frozen=True)
class Idempotency:
    request_id: str

@dataclass(frozen=True)
class Envelope:
    type: str
    occurred_at: str
    actor: Actor
    idempotency: Idempotency
    payload: Dict[str, Any]
    envelope_id: Optional[str] = None

@dataclass(frozen=True)
class KernelMode:
    mode: Literal["LIVE", "REPLAY"]

@dataclass(frozen=True)
class SkillInput:
    envelope: Envelope
    state: Optional[Dict[str, Any]]
    mode: KernelMode
    policy: Optional[Dict[str, Any]]
    trace_id: str

@dataclass(frozen=True)
class StateUpsert:
    key: str
    value: Dict[str, Any]
    expected_last_envelope_id: Optional[str] = None

@dataclass(frozen=True)
class EmittedEvent:
    type: str
    payload: Dict[str, Any]

@dataclass(frozen=True)
class SkillOutput:
    apply_result: ApplyResult
    reason: Optional[str]
    state_upserts: List[StateUpsert]
    events_to_emit: List[EmittedEvent]
    domain_effects: Dict[str, Any]
