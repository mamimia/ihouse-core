from __future__ import annotations
from typing import Any, Dict, Optional
from core.skill_contract import SkillOutput, StateUpsert, EmittedEvent

def legacy_dict_to_skill_output(result: Any) -> SkillOutput:
    if isinstance(result, SkillOutput):
        return result

    if isinstance(result, dict) and "error" in result:
        return SkillOutput(
            apply_result="REJECTED",
            reason=str(result.get("error")),
            state_upserts=[],
            events_to_emit=[],
            domain_effects={"legacy_error": result},
        )

    if isinstance(result, dict) and ("state_upserts" in result or "events_to_emit" in result):
        return SkillOutput(
            apply_result=result.get("apply_result", "APPLIED"),
            reason=result.get("reason"),
            state_upserts=[StateUpsert(**x) for x in result.get("state_upserts", [])],
            events_to_emit=[EmittedEvent(**x) for x in result.get("events_to_emit", [])],
            domain_effects=result.get("domain_effects", {}),
        )

    return SkillOutput(
        apply_result="APPLIED",
        reason=None,
        state_upserts=[],
        events_to_emit=[],
        domain_effects={"legacy_result": result},
    )
