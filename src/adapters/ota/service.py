from typing import Dict, Any

from core.api import IngestAPI

from .schemas import IngestionContext, IngestionResult
from .pipeline import process_provider_event


class OTAIngestionService:

    def __init__(self, ingest_api: IngestAPI) -> None:
        self._ingest = ingest_api

    def ingest(
        self,
        *,
        channel: str,
        raw_payload: Dict[str, Any],
        context: IngestionContext,
    ) -> IngestionResult:

        request_id = "unknown"

        try:
            envelope = process_provider_event(
                channel=channel,
                raw_payload=raw_payload,
                tenant_id=context.tenant_id,
                source=context.source,
            )

            request_id = envelope.idempotency_request_id

            ingest_result = self._ingest.append_event(
                envelope={
                    "type": envelope.type,
                    "payload": envelope.payload,
                    "occurred_at": envelope.occurred_at,
                },
                idempotency_key=envelope.idempotency_request_id,
            )

            status = "APPLIED"

            if ingest_result.apply_status == "ALREADY_APPLIED":
                status = "DUPLICATE"

            return IngestionResult(
                status=status,
                channel=channel,
                request_id=request_id,
                reason=None,
            )

        except ValueError as exc:

            return IngestionResult(
                status="REJECTED",
                channel=channel,
                request_id=request_id,
                reason=str(exc),
            )
