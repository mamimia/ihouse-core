"""
Phase 982 — OCR Provider Router
=================================

Dispatches OCR requests to the appropriate provider based on
capture_type, document_type, and tenant configuration.

Provider priority:
  1. Check tenant's ocr_provider_config for enabled providers
  2. Sort by priority (lower number = higher priority)
  3. Filter by capture_type + document_type compatibility
  4. Attempt primary → fallback chain

Scope guard runs FIRST — before any provider lookup.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ocr.provider_base import OcrProvider, OcrRequest, OcrResult, OcrResultStatus
from ocr.scope_guard import validate_capture_type, is_identity_capture, is_meter_capture

logger = logging.getLogger(__name__)


class ProviderRegistry:
    """
    Registry of available OCR providers.

    Providers register themselves at startup. The registry is used by
    the fallback orchestrator to find providers for a given request.
    """

    def __init__(self) -> None:
        self._providers: Dict[str, OcrProvider] = {}

    def register(self, provider: OcrProvider) -> None:
        """Register an OCR provider."""
        name = provider.provider_name
        if name in self._providers:
            logger.warning("OCR provider '%s' already registered — replacing", name)
        self._providers[name] = provider
        logger.info(
            "OCR provider registered: %s (supports: %s)",
            name, sorted(provider.supported_capture_types),
        )

    def unregister(self, provider_name: str) -> None:
        """Remove a provider from the registry."""
        self._providers.pop(provider_name, None)

    def get(self, provider_name: str) -> Optional[OcrProvider]:
        """Get a provider by name."""
        return self._providers.get(provider_name)

    def get_providers_for_request(self, request: OcrRequest) -> List[OcrProvider]:
        """
        Get all providers that can handle this request,
        filtered by capture_type and document_type.
        """
        result = []
        for provider in self._providers.values():
            if not provider.supports_capture_type(request.capture_type):
                continue
            # For identity captures, also check document_type
            if is_identity_capture(request.capture_type) and request.document_type:
                if not provider.supports_document_type(request.document_type):
                    continue
            result.append(provider)
        return result

    @property
    def provider_names(self) -> List[str]:
        """List all registered provider names."""
        return list(self._providers.keys())

    def __len__(self) -> int:
        return len(self._providers)


# Global singleton registry
_registry = ProviderRegistry()


def get_registry() -> ProviderRegistry:
    """Get the global provider registry."""
    return _registry


def register_provider(provider: OcrProvider) -> None:
    """Register a provider in the global registry."""
    _registry.register(provider)


# ─── Tenant config resolution ─────────────────────────────────────

def resolve_provider_order(
    tenant_configs: List[dict],
    available_providers: List[OcrProvider],
) -> List[OcrProvider]:
    """
    Resolve the provider execution order based on tenant config.

    Args:
        tenant_configs: Rows from ocr_provider_config for this tenant,
                       sorted by priority ASC.
        available_providers: Providers from the registry that support
                           this capture_type.

    Returns:
        Ordered list of providers to try (primary first, then fallbacks).
    """
    # Build lookup of available providers by name
    by_name = {p.provider_name: p for p in available_providers}

    # If no tenant config, return all available ordered by name (deterministic)
    if not tenant_configs:
        return sorted(available_providers, key=lambda p: p.provider_name)

    ordered: List[OcrProvider] = []
    seen = set()

    # Primary providers first (sorted by priority)
    for cfg in tenant_configs:
        name = cfg.get("provider_name", "")
        if not cfg.get("enabled", False):
            continue
        if name in seen:
            continue
        if name in by_name:
            ordered.append(by_name[name])
            seen.add(name)

    # Add any remaining available providers not in config (as fallback)
    for provider in available_providers:
        if provider.provider_name not in seen:
            ordered.append(provider)

    return ordered
