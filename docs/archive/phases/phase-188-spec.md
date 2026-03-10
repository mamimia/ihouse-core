# Phase 188 — PDF Owner Statements

**Status:** Closed
**Prerequisite:** Phase 187 (Rakuten Travel Adapter)
**Date Closed:** 2026-03-10

## Goal

Replace the Phase 121 `text/plain` stub in `owner_statement_router.py` with a real `application/pdf` response using `reportlab`. The endpoint `GET /owner-statement/{property_id}?month=YYYY-MM&format=pdf` now returns a professional financial document — property/period header, financial summary block, per-booking line items table, and a quiet system attribution footer. The Owner Portal's StatementDrawer gains a "↓ PDF" download button.

## Invariant

`?format=pdf` must return `Content-Type: application/pdf` with `%PDF` magic bytes and a `Content-Disposition: attachment; filename="owner-statement-{property_id}-{month}.pdf"` header.

## Design / Files

| File | Change |
|------|--------|
| `src/services/statement_generator.py` | NEW — `generate_owner_statement_pdf()`: pure function (data → bytes), reportlab platypus layout: header, summary table, line items table, footer |
| `src/api/owner_statement_router.py` | MODIFIED — `format=pdf` branch now calls `generate_owner_statement_pdf()`, `media_type="application/pdf"`, `.pdf` filename; `_render_pdf_text` kept as private fallback |
| `ihouse-ui/app/owner/page.tsx` | MODIFIED — `StatementDrawer` gains "↓ PDF" anchor with `download` attribute beside close button |
| `tests/test_pdf_owner_statement_contract.py` | NEW — 9 contract tests (Groups F1–F9): status 200, Content-Type, Content-Disposition attachment, .pdf filename, non-empty body, real `%PDF` magic bytes (f6), JSON fallback, JSON-explicit fallback, 404-still-JSON on empty data |

## Result

**37 tests pass (9 new + 28 existing owner-statement tests). 0 regressions.**
Sample PDF: 3,627 bytes. `%PDF` magic confirmed. reportlab installed into `.venv`.
