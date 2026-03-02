from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from core.event_log import ApplyStatus, EventLog
from core.ports import EventLogPort, StateStorePort
from core.skill_contract import SkillOutput
from core.skill_shim import legacy_dict_to_skill_output


class CoreExecutionError(Exception):
    pass


def _core_dir() -> Path:
    return Path(__file__).resolve().parent


def _load_json_map(path: Path) -> Dict[str, str]:
    raw = path.read_text(encoding="utf-8")
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise CoreExecutionError(f"REGISTRY_INVALID path={path.name}")
    out: Dict[str, str] = {}
    for k, v in parsed.items():
        if not isinstance(k, str) or not isinstance(v, str):
            raise CoreExecutionError(f"REGISTRY_SCHEMA_INVALID path={path.name}")
        out[k] = v
    return out


def _run_skill(module_path: str, payload: Mapping[str, Any]) -> Any:
    import importlib

    mod = importlib.import_module(module_path)
    fn = getattr(mod, "run", None)
    if not callable(fn):
        raise CoreExecutionError(f"SKILL_RUN_MISSING module={module_path}")
    return fn(dict(payload))


def _normalize_emitted_events(skill_out: Any) -> List[Dict[str, Any]]:
    decision: SkillOutput = legacy_dict_to_skill_output(skill_out)
    emitted: List[Dict[str, Any]] = []
    for ev in decision.events_to_emit:
        emitted.append({"type": ev.type, "payload": dict(ev.payload)})
    return emitted


def _state_upserts_to_state_events(skill_decision: SkillOutput) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    upserts = getattr(skill_decision, "state_upserts", None) or []
    for u in upserts:
        out.append(
            {
                "kind": "StateUpsert",
                "payload": {
                    "booking_id": u.key,
                    "state_json": u.value,
                    "expected_last_envelope_id": u.expected_last_envelope_id,
                },
            }
        )
    return out


@dataclass(frozen=True)
class ExecuteResult:
    envelope_id: str
    apply_status: Optional[ApplyStatus]
    emitted_events: List[Dict[str, Any]]
    skill_result: Any


@dataclass
class CoreExecutor:
    """
    Canonical executor shell.

    Commit policy:
    commit only after apply_status == "APPLIED"
    never commit when replay_mode is True
    no adapter-level state writes
    """

    event_log_port: EventLogPort
    event_log_applier: Optional[EventLog]
    state_store: Optional[StateStorePort]
    replay_mode: bool = False

    def execute(
        self,
        *,
        envelope: Mapping[str, Any],
        idempotency_key: Optional[str] = None,
    ) -> ExecuteResult:
        env = dict(envelope)

        envelope_id = self.event_log_port.append_event(
            envelope=env,
            idempotency_key=str(idempotency_key or ""),
        )

        if self.event_log_applier is None:
            return ExecuteResult(
                envelope_id=envelope_id,
                apply_status=None,
                emitted_events=[],
                skill_result={"warning": "NO_APPLIER"},
            )

        typ = env.get("type")
        if not isinstance(typ, str) or not typ:
            raise CoreExecutionError("ENVELOPE_TYPE_REQUIRED")

        payload = env.get("payload")
        if not isinstance(payload, dict):
            raise CoreExecutionError("ENVELOPE_PAYLOAD_REQUIRED")

        occurred_at = env.get("occurred_at")
        if not isinstance(occurred_at, str) or not occurred_at:
            raise CoreExecutionError("ENVELOPE_OCCURRED_AT_REQUIRED")

        core_dir = _core_dir()
        kind_map = _load_json_map(core_dir / "kind_registry.core.json")
        exec_map = _load_json_map(core_dir / "skill_exec_registry.core.json")

        if typ not in kind_map:
            raise CoreExecutionError(f"NO_ROUTE type={typ}")

        skill_name = kind_map[typ]
        if skill_name not in exec_map:
            raise CoreExecutionError(f"NO_SKILL_EXEC kind={skill_name}")

        skill_out = _run_skill(exec_map[skill_name], payload)
        skill_decision: SkillOutput = legacy_dict_to_skill_output(skill_out)
        emitted = _normalize_emitted_events(skill_out)

        apply_env: Dict[str, Any] = dict(env)
        apply_env["envelope_id"] = envelope_id

        apply_result: Dict[str, Any] = {
            "apply_result": getattr(skill_decision, "apply_result", None),
            "reason": getattr(skill_decision, "reason", None),
            "domain_effects": getattr(skill_decision, "domain_effects", None),
            "skill_result": skill_out,
        }

        apply_status = self.event_log_applier.append_envelope_result(
            envelope=apply_env,
            result=apply_result,
            emitted_events=emitted,
        )

        if apply_status == "APPLIED" and (not self.replay_mode) and self.state_store is not None:
            self.state_store.ensure_schema()

            has_state_upserts = bool(getattr(skill_decision, "state_upserts", None))
            if has_state_upserts:
                if hasattr(self.state_store, "commit_upserts"):
                    upserts = [
                        {
                            "key": u.key,
                            "value": u.value,
                            "expected_last_envelope_id": u.expected_last_envelope_id,
                        }
                        for u in skill_decision.state_upserts
                    ]
                    self.state_store.commit_upserts(envelope_id=envelope_id, upserts=upserts)
                else:
                    state_events = _state_upserts_to_state_events(skill_decision)
                    self.state_store.commit(envelope_id=envelope_id, events=state_events)
            else:
                self.state_store.commit(envelope_id=envelope_id, events=emitted)

        return ExecuteResult(
            envelope_id=envelope_id,
            apply_status=apply_status,
            emitted_events=emitted,
            skill_result=skill_out,
        )
