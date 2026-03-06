from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .schemas import NormalizedBookingEvent


class OTASemanticKind(str, Enum):
    CREATE = "CREATE"
    CANCEL = "CANCEL"
    MODIFY = "MODIFY"


class OTASemanticError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class ClassifiedBookingEvent:
    normalized_event: NormalizedBookingEvent
    semantic_kind: OTASemanticKind


def _normalized_raw_status(event: NormalizedBookingEvent) -> str:
    return str(event.raw_payload.get("status", "")).strip().lower()


def _kind_from_raw_event_name(raw_event_name: str) -> OTASemanticKind | None:
    value = str(raw_event_name or "").strip().lower()

    if value == "reservation_created":
        return OTASemanticKind.CREATE

    if value == "reservation_cancelled":
        return OTASemanticKind.CANCEL

    if value == "reservation_modified":
        return OTASemanticKind.MODIFY

    return None


def _kind_from_raw_status(status: str) -> OTASemanticKind | None:
    if status == "confirmed":
        return OTASemanticKind.CREATE

    if status == "cancelled":
        return OTASemanticKind.CANCEL

    return None


def _semantic_conflicts(
    raw_kind: OTASemanticKind | None,
    status_kind: OTASemanticKind | None,
) -> bool:
    if raw_kind is None or status_kind is None:
        return False

    if raw_kind == OTASemanticKind.MODIFY:
        return False

    return raw_kind != status_kind


def classify_normalized_event(event: NormalizedBookingEvent) -> ClassifiedBookingEvent:
    raw_kind = _kind_from_raw_event_name(event.raw_event_name)
    status_kind = _kind_from_raw_status(_normalized_raw_status(event))

    if raw_kind is None and status_kind is None:
        raise OTASemanticError(
            code="UNKNOWN_SEMANTIC_KIND",
            message="Could not classify normalized OTA event into a supported semantic kind.",
        )

    if _semantic_conflicts(raw_kind, status_kind):
        raise OTASemanticError(
            code="CONFLICTING_PROVIDER_SEMANTICS",
            message="Provider raw event name and raw payload status map to conflicting semantic kinds.",
        )

    semantic_kind = raw_kind or status_kind
    if semantic_kind is None:
        raise OTASemanticError(
            code="UNSUPPORTED_PROVIDER_EVENT",
            message="Provider event is not supported by the active OTA semantic surface.",
        )

    return ClassifiedBookingEvent(
        normalized_event=event,
        semantic_kind=semantic_kind,
    )


def validate_classified_event(classified: ClassifiedBookingEvent) -> None:
    event = classified.normalized_event
    semantic_kind = classified.semantic_kind
    raw_status = _normalized_raw_status(event)

    if semantic_kind == OTASemanticKind.CREATE:
        if not event.check_in or not event.check_out:
            raise OTASemanticError(
                code="INVALID_CREATE_EVENT",
                message="CREATE event must include check_in and check_out.",
            )

        if raw_status and raw_status != "confirmed":
            raise OTASemanticError(
                code="INVALID_CREATE_EVENT",
                message="CREATE event contains raw status inconsistent with creation semantics.",
            )

        return

    if semantic_kind == OTASemanticKind.CANCEL:
        if raw_status and raw_status != "cancelled":
            raise OTASemanticError(
                code="INVALID_CANCEL_EVENT",
                message="CANCEL event contains raw status inconsistent with cancellation semantics.",
            )

        return

    if semantic_kind == OTASemanticKind.MODIFY:
        return

    raise OTASemanticError(
        code="UNKNOWN_SEMANTIC_KIND",
        message="Semantic kind is not supported.",
    )
