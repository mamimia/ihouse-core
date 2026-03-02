from __future__ import annotations

from typing import Any, Dict

from core.skill_contract import SkillOutput


def run(payload: Dict[str, Any]) -> SkillOutput:
    return SkillOutput(
        apply_result="APPLIED",
        reason="NOOP_SMOKE_TEST",
        state_upserts=[],
        events_to_emit=[],
        domain_effects={"noop": True},
    )
