"""
Wave 9 — i18n API Router (Phases 736, 741–742)
=================================================

736: GET /i18n/{lang} → full language pack
     GET /i18n/{lang}/{category} → category-specific pack
741: POST /translate → auto-translate via LLM
742: PATCH /workers/{worker_id}/language → set worker preference
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from api.error_models import ErrorCode, make_error_response

logger = logging.getLogger(__name__)
router = APIRouter(tags=["i18n"])


def _get_db() -> Any:
    from supabase import create_client
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])


# ===========================================================================
# Phase 736 — i18n: Full Language Pack API
# ===========================================================================

@router.get("/i18n/{lang}", summary="Get full language pack (Phase 736)")
async def get_language_pack_api(lang: str) -> JSONResponse:
    from i18n.i18n_catalog import get_full_pack, SUPPORTED_LANGUAGES, get_all_categories
    lang = lang.lower().strip()
    if lang not in SUPPORTED_LANGUAGES:
        return make_error_response(400, ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": f"Unsupported language: {lang}. Supported: {sorted(SUPPORTED_LANGUAGES)}"})

    pack = get_full_pack(lang)
    return JSONResponse(status_code=200, content={
        "language": lang,
        "categories": get_all_categories(),
        "pack": pack,
    })


@router.get("/i18n/{lang}/{category}", summary="Get category pack (Phase 736)")
async def get_category_pack_api(lang: str, category: str) -> JSONResponse:
    from i18n.i18n_catalog import get_category_pack, SUPPORTED_LANGUAGES, get_all_categories
    lang = lang.lower().strip()
    if lang not in SUPPORTED_LANGUAGES:
        return make_error_response(400, ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": f"Unsupported language: {lang}"})

    categories = get_all_categories()
    if category not in categories:
        return make_error_response(404, "NOT_FOUND",
                                   extra={"detail": f"Unknown category: {category}. Available: {categories}"})

    pack = get_category_pack(category, lang)
    return JSONResponse(status_code=200, content={
        "language": lang,
        "category": category,
        "pack": pack,
    })


# ===========================================================================
# Phase 741 — Auto-Translate Integration
# ===========================================================================

@router.post("/translate", summary="Auto-translate text (Phase 741)")
async def auto_translate(
    body: Dict[str, Any],
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    text = str(body.get("text") or "").strip()
    source_lang = str(body.get("source_lang") or "").strip().lower()
    target_lang = str(body.get("target_lang") or "en").strip().lower()

    if not text:
        return make_error_response(400, ErrorCode.VALIDATION_ERROR, extra={"detail": "text required"})

    try:
        # Try LLM-based translation
        try:
            from services.llm_service import get_llm_response
            prompt = f"Translate the following text from {source_lang} to {target_lang}. Return ONLY the translation, nothing else.\n\nText: {text}"
            translated = get_llm_response(prompt)
            if translated and translated.strip():
                return JSONResponse(status_code=200, content={
                    "original": text,
                    "translated": translated.strip(),
                    "source_lang": source_lang,
                    "target_lang": target_lang,
                    "method": "llm",
                })
        except Exception:
            logger.warning("LLM translation failed, falling back to passthrough")

        # Fallback: return original with note
        return JSONResponse(status_code=200, content={
            "original": text,
            "translated": text,
            "source_lang": source_lang,
            "target_lang": target_lang,
            "method": "passthrough",
            "note": "Translation service unavailable, returning original text",
        })
    except Exception as exc:
        logger.exception("auto_translate error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR)


# ===========================================================================
# Phase 742 — Worker Language Preference
# ===========================================================================

@router.patch("/workers/{worker_id}/language", summary="Set worker language (Phase 742)")
async def set_worker_language(
    worker_id: str, body: Dict[str, Any],
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    from i18n.i18n_catalog import SUPPORTED_LANGUAGES
    lang = str(body.get("language") or "").strip().lower()
    if lang not in SUPPORTED_LANGUAGES:
        return make_error_response(400, ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": f"language must be one of: {sorted(SUPPORTED_LANGUAGES)}"})

    try:
        db = client if client is not None else _get_db()
        db.table("workers").update({"language_preference": lang}).eq("id", worker_id).execute()
        return JSONResponse(status_code=200, content={
            "worker_id": worker_id,
            "language_preference": lang,
        })
    except Exception as exc:
        logger.exception("set_worker_language error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR)


@router.get("/workers/{worker_id}/language", summary="Get worker language (Phase 742)")
async def get_worker_language(
    worker_id: str,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    try:
        db = client if client is not None else _get_db()
        result = db.table("workers").select("language_preference").eq("id", worker_id).limit(1).execute()
        rows = result.data or []
        lang = rows[0].get("language_preference", "en") if rows else "en"
        return JSONResponse(status_code=200, content={
            "worker_id": worker_id,
            "language_preference": lang,
        })
    except Exception as exc:
        logger.exception("get_worker_language error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR)
