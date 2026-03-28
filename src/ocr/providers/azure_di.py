"""
Phase 984 — Azure Document Intelligence Provider
==================================================

Track A: External OCR provider using Azure Document Intelligence (ADI).

Model used: prebuilt-idDocument
  - Supports: passport, national ID, driving license, residence permit
  - Returns: firstName, lastName, documentNumber, dateOfBirth, dateOfExpiration,
             nationality, countryRegion, sex, machineReadableZone, ...

Credentials:
  - endpoint URL and API key read from ocr_provider_config.config JSONB
  - Keys NEVER logged, NEVER returned to frontend (masked display only)
  - INV-OCR-03: credential security is enforced here

Fallback:
  - If Azure returns an error → OcrResult(FAILED) — never raises
  - Caller (fallback orchestrator) will retry with Track B providers

Circuit breaker:
  - HTTP timeout: 30s (configurable)
  - On timeout or 5xx: FAILED result, do not retry internally
  - Retry logic is the caller's responsibility (fallback.py)

API version: 2024-11-30 (GA, Analyze Document)
"""
from __future__ import annotations

import base64
import json
import logging
import time
from typing import Any, Dict, Optional

from ocr.provider_base import (
    OcrProvider, OcrRequest, OcrResult, OcrResultStatus, ImageQualityFlag
)
from ocr.image_preprocessing import preprocess_document, image_to_bytes, estimate_quality

logger = logging.getLogger(__name__)

# Azure Document Intelligence Analyze API
_API_VERSION = "2024-11-30"
_MODEL_ID = "prebuilt-idDocument"
_ANALYZE_PATH = f"/documentintelligence/documentModels/{_MODEL_ID}:analyze"
_RESULT_PATH = "/documentintelligence/documentModels/{model}/analyzeResults/{result_id}"

# Field name mappings: Azure field name → normalized field name
_FIELD_MAP: Dict[str, str] = {
    "FirstName":          "first_name",
    "LastName":           "last_name",
    "DocumentNumber":     "document_number",
    "DateOfBirth":        "date_of_birth",
    "DateOfExpiration":   "expiry_date",
    "Sex":                "sex",
    "CountryRegion":      "issuing_country",
    "Nationality":        "nationality",
    "PlaceOfBirth":       "place_of_birth",
    "MachineReadableZone": "mrz_raw",
    "DocumentType":       "document_type",
    "Address":            "address",
}

# Azure document type → normalized document type
_DOC_TYPE_MAP: Dict[str, str] = {
    "passport":           "PASSPORT",
    "nationalIdentityCard": "NATIONAL_ID",
    "drivingLicense":     "DRIVING_LICENSE",
    "residencePermit":    "RESIDENCE_PERMIT",
}

_DEFAULT_TIMEOUT = 30.0  # seconds


class AzureDocumentIntelligenceProvider(OcrProvider):
    """
    Track A OCR provider: Azure Document Intelligence prebuilt-idDocument.

    Reads credentials from the config dict passed at construction, which
    comes from ocr_provider_config.config JSONB (never from env directly).

    Design:
      - Uses httpx for async HTTP (already in requirements)
      - Polls the operation result URL (async analyze API)
      - Maps Azure field schema → normalized OcrResult
      - Masks credentials in all log output (INV-OCR-03)
    """

    SUPPORTED_CAPTURES = frozenset({"identity_document_capture"})
    SUPPORTED_DOCUMENTS = frozenset({
        "PASSPORT", "NATIONAL_ID", "DRIVING_LICENSE", "RESIDENCE_PERMIT",
    })

    def __init__(self, endpoint: str = "", api_key: str = "", timeout: float = _DEFAULT_TIMEOUT):
        """
        Args:
            endpoint: Azure DI endpoint URL (e.g. https://{resource}.cognitiveservices.azure.com)
            api_key:  Azure DI API key (never logged)
            timeout:  HTTP timeout in seconds
        """
        self._endpoint = endpoint.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout

    @classmethod
    def from_config(cls, config: dict) -> "AzureDocumentIntelligenceProvider":
        """
        Create provider from config dict (from ocr_provider_config.config JSONB).

        Expected config keys:
            endpoint  — Azure DI endpoint URL
            api_key   — Azure DI API key
            timeout   — Optional HTTP timeout in seconds (default 30)
        """
        return cls(
            endpoint=config.get("endpoint", ""),
            api_key=config.get("api_key", ""),
            timeout=float(config.get("timeout", _DEFAULT_TIMEOUT)),
        )

    @property
    def provider_name(self) -> str:
        return "azure_document_intelligence"

    @property
    def supported_capture_types(self) -> frozenset:
        return self.SUPPORTED_CAPTURES

    @property
    def supported_document_types(self) -> frozenset:
        return self.SUPPORTED_DOCUMENTS

    @property
    def _is_configured(self) -> bool:
        return bool(self._endpoint and self._api_key)

    @property
    def _masked_key(self) -> str:
        """Return masked API key for safe logging."""
        k = self._api_key
        if not k:
            return "<not set>"
        return k[:4] + "****" + k[-4:] if len(k) >= 8 else "****"

    async def process(self, request: OcrRequest) -> OcrResult:
        start = time.monotonic()

        if not self._is_configured:
            return self._make_failed_result(
                request,
                "Azure DI not configured: endpoint or api_key missing",
                elapsed_ms=0,
            )

        # Preprocess image
        prep = preprocess_document(request.image_bytes)
        if not prep.ok:
            return self._make_failed_result(request, prep.error or "Preprocess failed")

        quality_warnings = [
            ImageQualityFlag(w) for w in prep.warnings
            if w in {f.value for f in ImageQualityFlag}
        ]

        # Convert to base64 for Azure API
        img_bytes = image_to_bytes(prep.image, fmt="JPEG")
        img_b64 = base64.b64encode(img_bytes).decode("utf-8")

        # Call Azure API
        try:
            raw_response, result_id = await self._submit_analyze(img_b64)
        except Exception as exc:
            elapsed = int((time.monotonic() - start) * 1000)
            logger.error(
                "Azure DI submit failed (endpoint=%s key=%s): %s",
                self._endpoint, self._masked_key, exc,
            )
            return self._make_failed_result(request, f"Azure API error: {exc}", elapsed_ms=elapsed)

        if raw_response is None:
            elapsed = int((time.monotonic() - start) * 1000)
            return self._make_failed_result(request, "Azure API returned no result", elapsed_ms=elapsed)

        # Parse response
        elapsed = int((time.monotonic() - start) * 1000)
        return self._parse_response(
            raw_response=raw_response,
            request=request,
            quality_warnings=quality_warnings,
            image_quality_score=prep.quality_score,
            processing_time_ms=elapsed,
        )

    async def _submit_analyze(self, img_b64: str) -> tuple:
        """
        Submit an image for analysis and poll for result.

        Returns: (result_dict, operation_id) or raises on error.
        """
        try:
            import httpx
        except ImportError:
            raise RuntimeError("httpx not installed — cannot call Azure DI API")

        url = f"{self._endpoint}{_ANALYZE_PATH}?api-version={_API_VERSION}"
        headers = {
            "Ocp-Apim-Subscription-Key": self._api_key,
            "Content-Type": "application/json",
        }
        body = {
            "base64Source": img_b64,
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            # Submit job
            resp = await client.post(url, headers=headers, json=body)

            if resp.status_code == 202:
                # Async operation — poll result URL
                operation_url = resp.headers.get("Operation-Location", "")
                if not operation_url:
                    raise RuntimeError("Azure DI returned 202 but no Operation-Location header")

                result_id = operation_url.split("/")[-1].split("?")[0]
                result = await self._poll_result(client, operation_url, headers)
                return result, result_id

            elif resp.status_code == 200:
                # Synchronous response (some API versions)
                return resp.json(), "sync"

            else:
                body_text = resp.text[:500]
                raise RuntimeError(
                    f"Azure DI HTTP {resp.status_code}: {body_text}"
                )

    async def _poll_result(
        self,
        client: Any,
        operation_url: str,
        headers: dict,
        max_polls: int = 20,
        poll_interval: float = 1.5,
    ) -> dict:
        """Poll the operation URL until status is succeeded or failed."""
        import asyncio

        for attempt in range(max_polls):
            await asyncio.sleep(poll_interval if attempt > 0 else 0.5)

            resp = await client.get(operation_url, headers=headers)
            if resp.status_code != 200:
                raise RuntimeError(f"Azure DI poll HTTP {resp.status_code}")

            data = resp.json()
            status = data.get("status", "")

            if status == "succeeded":
                return data
            elif status in ("failed", "canceled"):
                error = data.get("error", {})
                raise RuntimeError(f"Azure DI job {status}: {error.get('message', 'unknown')}")
            # else: running/notStarted — keep polling

        raise RuntimeError(f"Azure DI did not complete after {max_polls} polls")

    def _parse_response(
        self,
        raw_response: dict,
        request: OcrRequest,
        quality_warnings: list,
        image_quality_score: float,
        processing_time_ms: int,
    ) -> OcrResult:
        """
        Parse Azure DI response → normalized OcrResult.

        Azure prebuilt-idDocument response structure:
        {
          "analyzeResult": {
            "documents": [{
              "docType": "idDocument.passport",
              "confidence": 0.99,
              "fields": {
                "FirstName": {"content": "JOHN", "confidence": 0.99},
                ...
              }
            }]
          }
        }
        """
        try:
            analyze = raw_response.get("analyzeResult", raw_response)
            documents = analyze.get("documents", [])

            if not documents:
                return OcrResult(
                    status=OcrResultStatus.FAILED,
                    provider_name=self.provider_name,
                    capture_type=request.capture_type,
                    document_type=request.document_type,
                    image_quality_score=image_quality_score,
                    quality_warnings=quality_warnings,
                    processing_time_ms=processing_time_ms,
                    raw_response=raw_response,
                    error_message="Azure DI found no documents in image",
                )

            doc = documents[0]
            azure_doc_type = doc.get("docType", "")
            doc_confidence = float(doc.get("confidence", 0.0))
            fields_raw = doc.get("fields", {})

            # Detect document type
            detected_doc_type = self._detect_doc_type(azure_doc_type, request.document_type)

            # Extract fields
            extracted: Dict[str, Optional[str]] = {}
            confidences: Dict[str, float] = {}

            for azure_field, norm_field in _FIELD_MAP.items():
                field_data = fields_raw.get(azure_field)
                if not field_data:
                    continue

                value = field_data.get("content") or field_data.get("valueString")
                if not value:
                    # Try typed value
                    value = self._extract_typed_value(field_data)

                if value is None:
                    continue

                confidence = float(field_data.get("confidence", doc_confidence))
                # Scale down if doc-level confidence is low
                confidence = min(confidence, doc_confidence + 0.05)

                extracted[norm_field] = str(value).strip()
                confidences[norm_field] = round(confidence, 4)

            # Build full_name from first + last if not directly provided
            if "full_name" not in extracted:
                first = extracted.get("first_name", "")
                last = extracted.get("last_name", "")
                if first or last:
                    extracted["full_name"] = f"{first} {last}".strip()
                    confidences["full_name"] = min(
                        confidences.get("first_name", 0.5),
                        confidences.get("last_name", 0.5),
                    )

            if not extracted:
                return OcrResult(
                    status=OcrResultStatus.FAILED,
                    provider_name=self.provider_name,
                    capture_type=request.capture_type,
                    document_type=detected_doc_type,
                    image_quality_score=image_quality_score,
                    quality_warnings=quality_warnings,
                    processing_time_ms=processing_time_ms,
                    raw_response=_sanitize_response(raw_response),
                    error_message="Azure DI returned no extractable fields",
                )

            return OcrResult(
                status=OcrResultStatus.SUCCESS,
                provider_name=self.provider_name,
                capture_type=request.capture_type,
                document_type=detected_doc_type,
                extracted_fields=extracted,
                field_confidences=confidences,
                image_quality_score=image_quality_score,
                quality_warnings=quality_warnings,
                processing_time_ms=processing_time_ms,
                raw_response=_sanitize_response(raw_response),
            )

        except Exception as exc:
            logger.exception("Azure DI response parsing failed: %s", exc)
            return OcrResult(
                status=OcrResultStatus.FAILED,
                provider_name=self.provider_name,
                capture_type=request.capture_type,
                document_type=request.document_type,
                image_quality_score=image_quality_score,
                quality_warnings=quality_warnings,
                processing_time_ms=processing_time_ms,
                error_message=f"Response parsing error: {exc}",
            )

    def _detect_doc_type(self, azure_doc_type: str, fallback: Optional[str]) -> str:
        """Map Azure docType → normalized document type."""
        lower = azure_doc_type.lower()
        for key, mapped in _DOC_TYPE_MAP.items():
            if key.lower() in lower:
                return mapped
        return fallback or "UNKNOWN"

    def _extract_typed_value(self, field_data: dict) -> Optional[str]:
        """Try to extract value from Azure typed field (date, string, etc.)."""
        for key in ("valueDate", "valueString", "valueInteger", "valueNumber"):
            v = field_data.get(key)
            if v is not None:
                return str(v)
        return None

    async def test_connection(self) -> dict:
        """
        Test Azure DI connectivity with a minimal API call.
        INV-OCR-03: API key is never logged, only masked in message.
        """
        if not self._is_configured:
            return {
                "success": False,
                "message": "Azure DI not configured: endpoint or api_key missing",
                "response_time_ms": 0,
            }

        start = time.monotonic()
        try:
            import httpx

            # Probe the models list endpoint (lightweight, no image needed)
            url = f"{self._endpoint}/documentintelligence/documentModels/{_MODEL_ID}?api-version={_API_VERSION}"
            headers = {"Ocp-Apim-Subscription-Key": self._api_key}

            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers=headers)

            elapsed = int((time.monotonic() - start) * 1000)

            if resp.status_code == 200:
                model_info = resp.json()
                return {
                    "success": True,
                    "message": (
                        f"Azure DI connected (key={self._masked_key}): "
                        f"model={model_info.get('modelId', _MODEL_ID)}"
                    ),
                    "response_time_ms": elapsed,
                }
            else:
                return {
                    "success": False,
                    "message": f"Azure DI HTTP {resp.status_code} (key={self._masked_key})",
                    "response_time_ms": elapsed,
                }
        except Exception as exc:
            elapsed = int((time.monotonic() - start) * 1000)
            return {
                "success": False,
                "message": f"Azure DI connection failed: {exc}",
                "response_time_ms": elapsed,
            }


# ─── Security utility ─────────────────────────────────────────────

def _sanitize_response(response: dict) -> dict:
    """
    Remove any credential-adjacent fields from raw_response before storage.
    The raw_response is stored in ocr_results.raw_response for debugging,
    but must never contain secrets.
    """
    if not response:
        return {}
    # Shallow copy — the Azure response has no credentials in it,
    # but we sanitize defensively
    sanitized = dict(response)
    for key in ("apiKey", "api_key", "key", "secret", "token"):
        sanitized.pop(key, None)
    return sanitized


# ─── Factory from DB config ───────────────────────────────────────

def make_azure_provider_from_db_config(config_row: dict) -> AzureDocumentIntelligenceProvider:
    """
    Build an AzureDocumentIntelligenceProvider from a DB config row.

    Args:
        config_row: Row from ocr_provider_config table.
                   The `config` JSONB field should contain endpoint + api_key.

    Returns:
        Configured provider instance.
    """
    config = config_row.get("config") or {}
    if isinstance(config, str):
        try:
            config = json.loads(config)
        except (json.JSONDecodeError, TypeError):
            config = {}
    return AzureDocumentIntelligenceProvider.from_config(config)
