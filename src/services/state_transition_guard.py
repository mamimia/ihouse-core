"""
Phase 326 — State Transition Guard
====================================

Pure, deterministic implementation of the validating-state-transitions skill
(.agent/skills/state-transition-guard/SKILL.md).

Contract:
    validate(payload: dict) -> TransitionResult

Key invariants:
    1. No implicit time — caller supplies now_utc.
    2. No storage reads or writes.
    3. No network calls, no randomness.
    4. One AuditEvent per request_id.
    5. Priority stack: first terminal match wins.
    6. Invariants evaluated after priority rules.

Input payload:
    {
      "actor":   { "actor_id": str, "role": str },
      "entity":  { "entity_type": str, "entity_id": str },
      "current": { "current_state": str, "current_version": int },
      "requested": { "requested_state": str, "reason_code": str, "request_id": str },
      "context": {
          "priority_stack": [ { "rule_id": str, "from_states": [...], "to_states": [...], "roles": [...], "effect": "allow"|"deny", "terminal": bool } ],
          "invariants": { "name": condition_dict, ... },
          "related_facts": {}
      },
      "time": { "now_utc": str }
    }

Output:
    TransitionResult:
        .decision { allowed, allowed_next_state, denial_code, applied_rules }
        .audit_event dict
        .side_effects []
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Output types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TransitionDecision:
    allowed: bool
    allowed_next_state: str
    denial_code: str = ""
    applied_rules: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class TransitionResult:
    decision: TransitionDecision
    audit_event: Dict[str, Any]
    side_effects: List[Any] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Denial codes
# ---------------------------------------------------------------------------

DENIAL_INPUT_INVALID    = "INPUT_INVALID"
DENIAL_UNKNOWN_TRANS    = "UNKNOWN_TRANSITION"
DENIAL_RULE_DENIED      = "RULE_DENIED"
DENIAL_INVARIANT_ERROR  = "INVARIANT_ERROR"
DENIAL_RULE_CONFLICT    = "RULE_CONFLICT"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _s(v: Any) -> str:
    return "" if v is None else str(v)


def _build_audit_event(
    request_id: str,
    actor_id: str,
    role: str,
    entity_type: str,
    entity_id: str,
    current_state: str,
    requested_state: str,
    allowed_next_state: str,
    allowed: bool,
    denial_code: str,
    applied_rules: List[str],
    now_utc: str,
) -> Dict[str, Any]:
    return {
        "event_type":         "AuditEvent",
        "request_id":         request_id,
        "actor_id":           actor_id,
        "role":               role,
        "entity_type":        entity_type,
        "entity_id":          entity_id,
        "current_state":      current_state,
        "requested_state":    requested_state,
        "allowed_next_state": allowed_next_state,
        "decision_allowed":   allowed,
        "denial_code":        denial_code,
        "applied_rules":      applied_rules,
        "now_utc":            now_utc,
    }


# ---------------------------------------------------------------------------
# Core function
# ---------------------------------------------------------------------------

def validate(payload: Dict[str, Any]) -> TransitionResult:
    """
    Deterministic state transition validation.

    Returns:
        TransitionResult with decision, audit_event, side_effects=[].

    Never raises — missing or malformed inputs produce INPUT_INVALID denials.
    """
    # --- 1. Unpack with safe fallbacks ---
    try:
        actor         = payload.get("actor") or {}
        entity        = payload.get("entity") or {}
        current       = payload.get("current") or {}
        requested     = payload.get("requested") or {}
        context       = payload.get("context") or {}
        time_block    = payload.get("time") or {}

        actor_id      = _s(actor.get("actor_id"))
        role          = _s(actor.get("role"))
        entity_type   = _s(entity.get("entity_type"))
        entity_id     = _s(entity.get("entity_id"))
        current_state = _s(current.get("current_state"))
        req_state     = _s(requested.get("requested_state"))
        reason_code   = _s(requested.get("reason_code"))
        request_id    = _s(requested.get("request_id"))
        now_utc       = _s(time_block.get("now_utc"))
        priority_stack: List[Dict] = context.get("priority_stack") or []
        invariants: Dict[str, Any] = context.get("invariants") or {}
        related_facts: Dict[str, Any] = context.get("related_facts") or {}

        # Validate required fields
        if not request_id or not entity_type or not entity_id or not current_state or not req_state:
            missing = [k for k, v in {
                "request_id": request_id, "entity_type": entity_type,
                "entity_id": entity_id, "current_state": current_state,
                "requested_state": req_state,
            }.items() if not v]
            denial = DENIAL_INPUT_INVALID
            decision = TransitionDecision(
                allowed=False,
                allowed_next_state=current_state,
                denial_code=denial,
                applied_rules=[],
            )
            audit = _build_audit_event(
                request_id, actor_id, role, entity_type, entity_id,
                current_state, req_state, current_state, False, denial, [], now_utc,
            )
            return TransitionResult(decision=decision, audit_event=audit, side_effects=[])

    except Exception:
        decision = TransitionDecision(
            allowed=False,
            allowed_next_state="",
            denial_code=DENIAL_INPUT_INVALID,
            applied_rules=[],
        )
        audit = _build_audit_event("", "", "", "", "", "", "", "", False, DENIAL_INPUT_INVALID, [], "")
        return TransitionResult(decision=decision, audit_event=audit, side_effects=[])

    # --- 2. Evaluate priority stack ---
    applied_rules: List[str] = []
    terminal_decision: Optional[bool] = None
    terminal_next_state: str = req_state
    terminal_denial: str = ""

    for rule in priority_stack:
        rule_id        = _s(rule.get("rule_id", ""))
        from_states    = rule.get("from_states") or []
        to_states      = rule.get("to_states") or []
        allowed_roles  = rule.get("roles") or []
        effect         = _s(rule.get("effect", "allow"))
        is_terminal    = bool(rule.get("terminal", True))
        force_state    = rule.get("force_next_state")  # optional override

        from_match = (not from_states) or (current_state in from_states)
        to_match   = (not to_states) or (req_state in to_states)
        role_match = (not allowed_roles) or (role in allowed_roles)

        if from_match and to_match and role_match:
            applied_rules.append(rule_id)
            if is_terminal:
                if effect == "allow":
                    terminal_decision   = True
                    terminal_next_state = _s(force_state) if force_state else req_state
                else:
                    terminal_decision   = False
                    terminal_next_state = current_state
                    terminal_denial     = DENIAL_RULE_DENIED
                break  # first terminal match wins

    # --- 3. Evaluate invariants ---
    invariant_failed = False
    invariant_denial = ""

    if terminal_decision is not False:  # only check if not already denied
        for inv_name, inv_condition in invariants.items():
            try:
                # Invariant is a dict with { "field": ..., "must_equal": ... }
                # (simple equality-check invariants)
                if isinstance(inv_condition, dict):
                    field_path = inv_condition.get("field", "")
                    must_equal = inv_condition.get("must_equal")
                    fact_value = related_facts.get(field_path)
                    if must_equal is not None and fact_value != must_equal:
                        invariant_failed = True
                        invariant_denial = DENIAL_INVARIANT_ERROR
                        break
            except Exception:
                invariant_failed = True
                invariant_denial = DENIAL_INVARIANT_ERROR
                break

    # --- 4. Compute final decision ---
    if invariant_failed:
        final_allowed     = False
        final_next_state  = current_state
        final_denial      = invariant_denial
    elif terminal_decision is True:
        final_allowed     = True
        final_next_state  = terminal_next_state
        final_denial      = ""
    elif terminal_decision is False:
        final_allowed     = False
        final_next_state  = current_state
        final_denial      = terminal_denial
    else:
        # No matching rule — unknown transition
        final_allowed     = False
        final_next_state  = current_state
        final_denial      = DENIAL_UNKNOWN_TRANS

    # --- 5. Build and return result ---
    decision = TransitionDecision(
        allowed=final_allowed,
        allowed_next_state=final_next_state,
        denial_code=final_denial,
        applied_rules=applied_rules,
    )
    audit = _build_audit_event(
        request_id, actor_id, role, entity_type, entity_id,
        current_state, req_state, final_next_state,
        final_allowed, final_denial, applied_rules, now_utc,
    )
    return TransitionResult(decision=decision, audit_event=audit, side_effects=[])
