"""
Phase 982 — OCR Fallback Orchestrator
=======================================

Priority + fallback orchestration for OCR providers.

Flow:
  1. Scope guard validates capture_type (hard block)
  2. Registry filters providers by capture_type + document_type
  3. Tenant config sorts providers by priority
  4. Try providers in order: primary → fallback
  5. First success wins
  6. All fail → return aggregated failure result

INV-OCR-04: If all providers fail, the wizard falls back to manual
entry. OCR failure is never blocking.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from ocr.provider_base import OcrProvider, OcrRequest, OcrResult, OcrResultStatus
from ocr.provider_router import get_registry, resolve_provider_order
from ocr.scope_guard import validate_capture_type, OcrScopeViolation

logger = logging.getLogger(__name__)


async def process_ocr_request(
    request: OcrRequest,
    tenant_configs: Optional[List[dict]] = None,
) -> OcrResult:
    """
    Process an OCR request through the provider chain.

    This is the main entry point for OCR processing.

    Args:
        request: The OCR request with image bytes and metadata.
        tenant_configs: Optional tenant-specific provider configs
                       (from ocr_provider_config table, sorted by priority).

    Returns:
        OcrResult from the first successful provider, or a FAILED result
        if all providers fail.

    Raises:
        OcrScopeViolation: If capture_type is not in the allowed scope.
    """
    # ── Step 1: Scope guard (hard block) ──────────────────────────
    validate_capture_type(request.capture_type)

    start = time.monotonic()

    # ── Step 2: Find compatible providers ─────────────────────────
    registry = get_registry()
    compatible = registry.get_providers_for_request(request)

    if not compatible:
        logger.warning(
            "OCR: no providers found for capture_type='%s' document_type='%s'",
            request.capture_type, request.document_type,
        )
        return OcrResult(
            status=OcrResultStatus.FAILED,
            provider_name="none",
            capture_type=request.capture_type,
            document_type=request.document_type,
            processing_time_ms=int((time.monotonic() - start) * 1000),
            error_message="No OCR providers available for this capture type",
        )

    # ── Step 3: Sort by tenant config priority ────────────────────
    ordered = resolve_provider_order(
        tenant_configs=tenant_configs or [],
        available_providers=compatible,
    )

    # ── Step 4: Try providers in order ────────────────────────────
    errors: List[str] = []

    for provider in ordered:
        provider_start = time.monotonic()
        try:
            logger.info(
                "OCR: trying provider '%s' for capture_type='%s'",
                provider.provider_name, request.capture_type,
            )
            result = await provider.process(request)

            if result.status in (OcrResultStatus.SUCCESS, OcrResultStatus.PARTIAL):
                elapsed = int((time.monotonic() - start) * 1000)
                result.processing_time_ms = elapsed
                logger.info(
                    "OCR: provider '%s' succeeded (status=%s, confidence=%.2f, %dms)",
                    provider.provider_name,
                    result.status.value,
                    result.overall_confidence,
                    elapsed,
                )
                return result

            # Provider returned FAILED or UNSUPPORTED — try next
            error_msg = (
                f"{provider.provider_name}: {result.error_message or result.status.value}"
            )
            errors.append(error_msg)
            logger.warning("OCR: provider '%s' returned %s: %s",
                         provider.provider_name, result.status.value, result.error_message)

        except Exception as exc:
            provider_elapsed = int((time.monotonic() - provider_start) * 1000)
            error_msg = f"{provider.provider_name}: exception: {exc}"
            errors.append(error_msg)
            logger.exception(
                "OCR: provider '%s' raised exception (%dms): %s",
                provider.provider_name, provider_elapsed, exc,
            )

    # ── Step 5: All providers failed ──────────────────────────────
    elapsed = int((time.monotonic() - start) * 1000)
    logger.error(
        "OCR: all %d providers failed for capture_type='%s' (%dms). Errors: %s",
        len(ordered), request.capture_type, elapsed, "; ".join(errors),
    )
    return OcrResult(
        status=OcrResultStatus.FAILED,
        provider_name="all_failed",
        capture_type=request.capture_type,
        document_type=request.document_type,
        processing_time_ms=elapsed,
        error_message=f"All {len(ordered)} providers failed: {'; '.join(errors)}",
    )


async def test_provider(provider_name: str) -> dict:
    """
    Test a specific provider's connection.

    Returns:
        {"success": bool, "message": str, "response_time_ms": int, "provider": str}
    """
    registry = get_registry()
    provider = registry.get(provider_name)
    if not provider:
        return {
            "success": False,
            "message": f"Provider '{provider_name}' not found in registry",
            "response_time_ms": 0,
            "provider": provider_name,
        }

    start = time.monotonic()
    try:
        result = await provider.test_connection()
        result["provider"] = provider_name
        result["response_time_ms"] = int((time.monotonic() - start) * 1000)
        return result
    except Exception as exc:
        return {
            "success": False,
            "message": f"Test failed: {exc}",
            "response_time_ms": int((time.monotonic() - start) * 1000),
            "provider": provider_name,
        }
