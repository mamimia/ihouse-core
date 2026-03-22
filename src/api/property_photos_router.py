"""
Phases 591–592 — Property Reference & Marketing Photos API

Endpoints:
    POST   /properties/{id}/reference-photos   — upload reference photo
    GET    /properties/{id}/reference-photos    — list reference photos
    DELETE /properties/{id}/reference-photos/{photo_id}
    POST   /properties/{id}/marketing-photos   — upload marketing photo
    GET    /properties/{id}/marketing-photos    — list marketing photos
    DELETE /properties/{id}/marketing-photos/{photo_id}
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

import uuid
import time

from fastapi import APIRouter, Depends, UploadFile, File, Form
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from api.capability_guard import require_capability
from api.error_models import ErrorCode, make_error_response

import io
from PIL import Image as PilImage

_ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
_ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
_MAX_UPLOAD_BYTES = 15 * 1024 * 1024  # 15 MB hard limit (locked policy)
_TARGET_BYTES = 2 * 1024 * 1024        # ~2 MB optimized asset target
_MAX_DIMENSION = 2048                  # longest side for full image
_THUMB_DIMENSION = 400                 # thumbnail longest side

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/properties", tags=["properties"])


def _get_supabase_client() -> Any:
    from supabase import create_client
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])


def _get_storage_public_url(path: str) -> str:
    """Return public CDN URL for a storage path."""
    base = os.environ["SUPABASE_URL"].rstrip("/")
    return f"{base}/storage/v1/object/public/property-photos/{path}"


def _process_image(data: bytes, max_dim: int, target_bytes: int) -> tuple[bytes, str]:
    """Resize + compress image using Pillow. Returns (processed_bytes, format_ext)."""
    img = PilImage.open(io.BytesIO(data))

    # Convert RGBA/P to RGB for JPEG output
    if img.mode in ("RGBA", "P", "LA"):
        background = PilImage.new("RGB", img.size, (255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")
        background.paste(img, mask=img.split()[-1] if "A" in img.mode else None)
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")

    # Resize if larger than max_dim
    w, h = img.size
    if max(w, h) > max_dim:
        ratio = max_dim / max(w, h)
        new_w, new_h = int(w * ratio), int(h * ratio)
        img = img.resize((new_w, new_h), PilImage.LANCZOS)

    # Compress: start at quality 85, reduce until under target or quality 30
    buf = io.BytesIO()
    quality = 85
    while quality >= 30:
        buf.seek(0)
        buf.truncate()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        if buf.tell() <= target_bytes:
            break
        quality -= 5

    return buf.getvalue(), "jpg"


# ---------------------------------------------------------------------------
# Phase 844 v3 — Server-side upload proxy (bypasses client RLS)
# Image policy: jpg/jpeg/png/webp only, 15 MB max, auto-compress to ~2 MB,
# generate 400px thumbnail, upload both to Supabase Storage.
# ---------------------------------------------------------------------------

@router.post("/{property_id}/upload-photo",
             summary="Upload photo via server proxy (Phase 844 — bypasses browser RLS)",
             responses={200: {}, 400: {}, 500: {}},
             openapi_extra={"security": [{"BearerAuth": []}]})
async def upload_photo_proxy(
    property_id: str,
    file: UploadFile = File(...),
    photo_type: str = Form("reference"),  # "reference" | "gallery"
    tenant_id: str = Depends(jwt_auth),
    _cap: None = Depends(require_capability("properties")),
) -> JSONResponse:
    """
    Accept a raw file from the browser, validate format/size, process with Pillow
    (resize + compress + thumbnail), upload both versions to Supabase Storage
    using the service-role key, and return the public CDN URLs.
    """
    content_type = getattr(file, "content_type", "") or ""
    if content_type == "image/jpg":
        content_type = "image/jpeg"

    if content_type not in _ALLOWED_CONTENT_TYPES:
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": f"Unsupported file type: {content_type}. Allowed: jpg, png, webp only."},
        )

    data = await file.read()
    size_bytes = len(data)

    if size_bytes > _MAX_UPLOAD_BYTES:
        mb = round(size_bytes / (1024 * 1024), 1)
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": f"Image is too large ({mb} MB). Maximum allowed is 15 MB."},
        )

    # --- Process image with Pillow ---
    try:
        full_data, ext = _process_image(data, _MAX_DIMENSION, _TARGET_BYTES)
        thumb_data, _ = _process_image(data, _THUMB_DIMENSION, 200 * 1024)  # ~200 KB thumb
    except Exception as exc:
        logger.exception("image processing error: %s", exc)
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": f"Could not process image: {exc}"},
        )

    ts = int(time.time())
    uid = uuid.uuid4().hex[:8]
    full_path = f"{property_id}/{photo_type}/{ts}_{uid}.{ext}"
    thumb_path = f"{property_id}/{photo_type}/thumb_{ts}_{uid}.{ext}"

    try:
        db = _get_supabase_client()
        # Upload full image
        db.storage.from_("property-photos").upload(
            path=full_path, file=full_data,
            file_options={"content-type": "image/jpeg", "upsert": "true"},
        )
        # Upload thumbnail
        db.storage.from_("property-photos").upload(
            path=thumb_path, file=thumb_data,
            file_options={"content-type": "image/jpeg", "upsert": "true"},
        )

        full_url = _get_storage_public_url(full_path)
        thumb_url = _get_storage_public_url(thumb_path)

        return JSONResponse(status_code=200, content={
            "url": full_url,
            "thumb_url": thumb_url,
            "path": full_path,
            "thumb_path": thumb_path,
            "original_size_bytes": size_bytes,
            "optimized_size_bytes": len(full_data),
            "thumb_size_bytes": len(thumb_data),
        })
    except Exception as exc:
        logger.exception("photo proxy upload error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR,
                                   extra={"detail": str(exc)})






# ---------------------------------------------------------------------------
# Generic photo CRUD (reused for both tables)
# ---------------------------------------------------------------------------

async def _add_photo(
    table: str, property_id: str, body: Dict[str, Any],
    tenant_id: str, client: Optional[Any], extra_fields: Optional[Dict] = None,
) -> JSONResponse:
    if not isinstance(body, dict):
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": "Request body must be a JSON object."})

    photo_url = str(body.get("photo_url") or "").strip()
    if not photo_url:
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": "'photo_url' is required."})

    try:
        db = client if client is not None else _get_supabase_client()

        # Duplicate prevention: check if same photo_url already exists for this property
        existing = (
            db.table(table)
            .select("*")
            .eq("tenant_id", tenant_id)
            .eq("property_id", property_id)
            .eq("photo_url", photo_url)
            .limit(1)
            .execute()
        )
        if existing.data:
            # Already exists — return existing row, no duplicate created
            return JSONResponse(status_code=200, content=existing.data[0])

        row: Dict[str, Any] = {
            "tenant_id": tenant_id, "property_id": property_id,
            "photo_url": photo_url, "display_order": body.get("display_order", 0),
        }
        if extra_fields:
            row.update(extra_fields)

        result = db.table(table).insert(row).execute()
        rows = result.data or []
        if not rows:
            return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
        return JSONResponse(status_code=201, content=rows[0])
    except Exception as exc:
        logger.exception("add photo to %s error: %s", table, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


async def _list_photos(
    table: str, property_id: str, tenant_id: str, client: Optional[Any],
) -> JSONResponse:
    try:
        db = client if client is not None else _get_supabase_client()
        result = (
            db.table(table).select("*")
            .eq("tenant_id", tenant_id).eq("property_id", property_id)
            .order("display_order", desc=False)
            .execute()
        )
        rows = result.data or []
        return JSONResponse(status_code=200, content={
            "property_id": property_id, "count": len(rows), "photos": rows,
        })
    except Exception as exc:
        logger.exception("list photos from %s error: %s", table, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


async def _delete_photo(
    table: str, property_id: str, photo_id: str,
    tenant_id: str, client: Optional[Any],
) -> JSONResponse:
    try:
        db = client if client is not None else _get_supabase_client()
        result = (
            db.table(table).delete()
            .eq("tenant_id", tenant_id).eq("property_id", property_id)
            .eq("id", photo_id)
            .execute()
        )
        rows = result.data or []
        if not rows:
            return make_error_response(status_code=404, code="NOT_FOUND",
                                       extra={"detail": f"Photo '{photo_id}' not found."})
        return JSONResponse(status_code=200, content={"deleted": True, "photo_id": photo_id})
    except Exception as exc:
        logger.exception("delete photo from %s error: %s", table, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# Phase 591 — Reference Photos
# ---------------------------------------------------------------------------

@router.post("/{property_id}/reference-photos", summary="Upload reference photo (Phase 591)",
             responses={201: {}, 400: {}, 500: {}}, openapi_extra={"security": [{"BearerAuth": []}]})
async def add_reference_photo(property_id: str, body: Dict[str, Any],
                              tenant_id: str = Depends(jwt_auth),
                              _cap: None = Depends(require_capability("properties")),
                              client: Optional[Any] = None) -> JSONResponse:
    room_label = str(body.get("room_label", "")).strip() if isinstance(body, dict) else ""
    if not room_label:
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": "'room_label' is required."})
    return await _add_photo("property_reference_photos", property_id, body, tenant_id, client,
                             extra_fields={"room_label": room_label})


@router.get("/{property_id}/reference-photos", summary="List reference photos (Phase 591)",
            responses={200: {}, 500: {}}, openapi_extra={"security": [{"BearerAuth": []}]})
async def list_reference_photos(property_id: str, tenant_id: str = Depends(jwt_auth),
                                client: Optional[Any] = None) -> JSONResponse:
    return await _list_photos("property_reference_photos", property_id, tenant_id, client)


@router.delete("/{property_id}/reference-photos/{photo_id}", summary="Delete reference photo (Phase 591)",
               responses={200: {}, 404: {}, 500: {}}, openapi_extra={"security": [{"BearerAuth": []}]})
async def delete_reference_photo(property_id: str, photo_id: str, tenant_id: str = Depends(jwt_auth),
                                 _cap: None = Depends(require_capability("properties")),
                                 client: Optional[Any] = None) -> JSONResponse:
    return await _delete_photo("property_reference_photos", property_id, photo_id, tenant_id, client)


# ---------------------------------------------------------------------------
# Phase 592 — Marketing Photos
# ---------------------------------------------------------------------------

@router.post("/{property_id}/marketing-photos", summary="Upload marketing photo (Phase 592)",
             responses={201: {}, 400: {}, 500: {}}, openapi_extra={"security": [{"BearerAuth": []}]})
async def add_marketing_photo(property_id: str, body: Dict[str, Any],
                              tenant_id: str = Depends(jwt_auth),
                              _cap: None = Depends(require_capability("properties")),
                              client: Optional[Any] = None) -> JSONResponse:
    caption = body.get("caption") if isinstance(body, dict) else None
    source = str(body.get("source", "upload")).strip() if isinstance(body, dict) else "upload"
    return await _add_photo("property_marketing_photos", property_id, body, tenant_id, client,
                             extra_fields={"caption": caption, "source": source})


@router.get("/{property_id}/marketing-photos", summary="List marketing photos (Phase 592)",
            responses={200: {}, 500: {}}, openapi_extra={"security": [{"BearerAuth": []}]})
async def list_marketing_photos(property_id: str, tenant_id: str = Depends(jwt_auth),
                                client: Optional[Any] = None) -> JSONResponse:
    return await _list_photos("property_marketing_photos", property_id, tenant_id, client)


@router.delete("/{property_id}/marketing-photos/{photo_id}", summary="Delete marketing photo (Phase 592)",
               responses={200: {}, 404: {}, 500: {}}, openapi_extra={"security": [{"BearerAuth": []}]})
async def delete_marketing_photo(property_id: str, photo_id: str, tenant_id: str = Depends(jwt_auth),
                                 _cap: None = Depends(require_capability("properties")),
                                 client: Optional[Any] = None) -> JSONResponse:
    return await _delete_photo("property_marketing_photos", property_id, photo_id, tenant_id, client)
