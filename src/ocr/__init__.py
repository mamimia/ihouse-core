"""
Phase 982 — OCR Platform Module
================================

Scoped OCR capability for iHouse Core worker wizards.

SCOPE BOUNDARY (LOCKED):
    OCR is limited to exactly 3 capture types:
      1. identity_document_capture    — Check-in Step 6 (passport/ID)
      2. checkin_opening_meter_capture — Check-in Step 3 (opening meter)
      3. checkout_closing_meter_capture — Check-out (closing meter)

    NO OCR on: cleaning photos, gallery, reference photos, atmosphere
    photos, generic task images, or any other uploaded image.

Architecture:
    - provider_base.py  → Abstract OcrProvider interface
    - scope_guard.py    → Whitelist enforcement (sole gatekeeper)
    - confidence.py     → Field-level confidence model
    - provider_router.py → capture_type → provider dispatch
    - fallback.py       → Priority + fallback orchestration
"""
