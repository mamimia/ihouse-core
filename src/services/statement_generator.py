"""
Phase 188 (Polish) — PDF Owner Statement Generator

Pure function module: no FastAPI, no DB, no I/O.
Input: structured statement data (already validated by the router).
Output: raw PDF bytes (application/pdf).

Layout (top → bottom, A4):
    1. Header   — title, subtitle, Statement ID + metadata grid
    2. Divider
    3. Summary  — key/value rows + Owner Net highlighted block
    4. Confidence note (plain-language explanation of A/B/C)
    5. Section  — "BOOKING DETAILS" heading
    6. Table    — per-booking line items (Booking ID, Channel, Check-in, Check-out, Nights, Gross, Net, Tier)
    7. Divider
    8. Footer   — configurable platform name via STATEMENT_PLATFORM_NAME env var

Fonts: Helvetica (built-in, no external font files needed).
Library: reportlab (platypus + lib).
"""
from __future__ import annotations

import hashlib
import io
import os
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# ---------------------------------------------------------------------------
# Palette — professional, neutral, no brand colour locked in
# ---------------------------------------------------------------------------

_DARK = colors.HexColor("#111827")
_MID = colors.HexColor("#374151")
_DIM = colors.HexColor("#6B7280")
_FAINT = colors.HexColor("#9CA3AF")
_ACCENT = colors.HexColor("#1D4ED8")       # deep blue — owner net
_ACCENT_BG = colors.HexColor("#EFF6FF")    # light blue — owner net background block
_RULE = colors.HexColor("#E5E7EB")
_BG_HEAD = colors.HexColor("#F3F4F6")
_BG_ALT = colors.HexColor("#FAFAFA")

# ---------------------------------------------------------------------------
# Platform branding — configurable, neutral default
# ---------------------------------------------------------------------------

_PLATFORM_NAME_DEFAULT = "Property Management Platform"


def _platform_name(override: Optional[str] = None) -> str:
    """Return platform name: override → env var → neutral default."""
    if override:
        return override
    return os.environ.get("STATEMENT_PLATFORM_NAME", _PLATFORM_NAME_DEFAULT)


# ---------------------------------------------------------------------------
# Paragraph style factory
# ---------------------------------------------------------------------------

_BASE = "Helvetica"
_BOLD = "Helvetica-Bold"
_MONO = "Courier"


def _s(
    name: str,
    font: str = _BASE,
    size: float = 9,
    color: Any = _MID,
    align: int = TA_LEFT,
    leading: Optional[float] = None,
    sb: float = 0,
    sa: float = 0,
) -> ParagraphStyle:
    return ParagraphStyle(
        name=name,
        fontName=font,
        fontSize=size,
        textColor=color,
        alignment=align,
        leading=leading or size * 1.4,
        spaceBefore=sb,
        spaceAfter=sa,
    )


_S_TITLE     = _s("title",    font=_BOLD, size=18, color=_DARK, sb=0, sa=1 * mm)
_S_SUBTITLE  = _s("subtitle", size=9,     color=_DIM, sa=0)
_S_META_LBL  = _s("mlbl",     size=7.5,   color=_FAINT)
_S_META_VAL  = _s("mval",     font=_BOLD, size=8, color=_MID)
_S_SECTION   = _s("section",  font=_BOLD, size=7.5, color=_DIM, sb=4 * mm, sa=2 * mm)
_S_LABEL     = _s("label",    size=8.5,   color=_DIM)
_S_VALUE     = _s("value",    font=_BOLD, size=8.5, color=_DARK)
_S_VALUE_R   = _s("valr",     font=_BOLD, size=8.5, color=_DARK, align=TA_RIGHT)
_S_NET_LBL   = _s("netlbl",   font=_BOLD, size=11, color=_ACCENT)
_S_NET_VAL   = _s("netval",   font=_BOLD, size=13, color=_ACCENT, align=TA_RIGHT)
_S_TH        = _s("th",       font=_BOLD, size=7.5, color=_MID)
_S_TH_R      = _s("thr",      font=_BOLD, size=7.5, color=_MID, align=TA_RIGHT)
_S_TD        = _s("td",       size=7.5,   color=_MID)
_S_TD_MONO   = _s("tdm",      font=_MONO, size=6.5, color=_MID)
_S_TD_R      = _s("tdr",      size=7.5,   color=_MID,  align=TA_RIGHT)
_S_NOTE      = _s("note",     size=7,     color=_FAINT, sb=1 * mm)
_S_FOOTER    = _s("footer",   size=6.5,   color=_FAINT, align=TA_CENTER)
_S_TIER_A    = _s("ta",       font=_BOLD, size=7.5, color=colors.HexColor("#059669"))
_S_TIER_B    = _s("tb",       font=_BOLD, size=7.5, color=colors.HexColor("#D97706"))
_S_TIER_C    = _s("tc",       font=_BOLD, size=7.5, color=colors.HexColor("#DC2626"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _p(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(text, style)


def _rule(w: int = 480, t: float = 0.5) -> HRFlowable:
    return HRFlowable(width=w, thickness=t, color=_RULE, spaceAfter=2 * mm, spaceBefore=2 * mm)


def _fmt(val: Optional[str], currency: str = "") -> str:
    if not val:
        return "—"
    try:
        d = Decimal(val)
        s = f"{d:,.2f}"
        return f"{currency}\u00a0{s}".strip() if currency else s
    except (InvalidOperation, TypeError):
        return val or "—"


def _nights(check_in: Optional[str], check_out: Optional[str]) -> str:
    """Return number of nights as a string, or '—'."""
    if not check_in or not check_out:
        return "—"
    try:
        ci = date.fromisoformat(check_in)
        co = date.fromisoformat(check_out)
        n = (co - ci).days
        return str(n) if n >= 0 else "—"
    except (ValueError, TypeError):
        return "—"


def _tier_style(tier: str) -> ParagraphStyle:
    t = (tier or "").upper()
    return {
        "A": _S_TIER_A,
        "B": _S_TIER_B,
    }.get(t, _S_TIER_C)


def _tier_label(tier: str) -> str:
    return {"A": "Tier A", "B": "Tier B", "C": "Tier C"}.get((tier or "").upper(), tier or "—")


def _lifecycle_label(status: str) -> str:
    return {
        "GUEST_PAID": "Guest paid",
        "OTA_COLLECTING": "OTA collecting",
        "PAYOUT_PENDING": "Payout pending",
        "PAYOUT_RELEASED": "Payout released",
        "RECONCILIATION_PENDING": "Reconciliation",
        "OWNER_NET_PENDING": "Net pending",
        "CANCELED": "Canceled",
    }.get(status or "", status or "—")


def _statement_id(property_id: str, month: str, tenant_id: str) -> str:
    """Short stable reference ID: 8-char hex from sha256 of key fields."""
    raw = f"{tenant_id}|{property_id}|{month}"
    return hashlib.sha256(raw.encode()).hexdigest()[:8].upper()


# ---------------------------------------------------------------------------
# Main public function
# ---------------------------------------------------------------------------

def generate_owner_statement_pdf(
    property_id: str,
    month: str,
    tenant_id: str,
    summary: Dict[str, Any],
    line_items: List[Dict[str, Any]],
    generated_at: str,
    platform_name: Optional[str] = None,
) -> bytes:
    """
    Generate a professional owner statement PDF.

    Args:
        property_id:    The property identifier.
        month:          Statement month (YYYY-MM).
        tenant_id:      Tenant identifier.
        summary:        Aggregated financial summary dict.
        line_items:     Per-booking line item dicts.
        generated_at:   ISO timestamp string.
        platform_name:  Optional platform name for footer.
                        Falls back to STATEMENT_PLATFORM_NAME env var,
                        then "Property Management Platform".

    Returns:
        Raw PDF bytes (starts with b'%PDF').
    """
    buf = io.BytesIO()
    pname = _platform_name(platform_name)
    stmt_id = _statement_id(property_id, month, tenant_id)
    currency = summary.get("currency", "")

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"Owner Statement — {property_id} — {month}",
        author=pname,
        subject="Monthly Owner Financial Statement",
    )

    story: list = []

    # -----------------------------------------------------------------------
    # 1. Header
    # -----------------------------------------------------------------------
    story.append(_p("OWNER STATEMENT", _S_TITLE))
    story.append(_p("Monthly Financial Statement", _S_SUBTITLE))
    story.append(Spacer(1, 4 * mm))

    # Metadata grid — 3 columns: Property | Period | Reference
    meta_data = [[
        [_p("PROPERTY", _S_META_LBL), _p(property_id, _S_META_VAL)],
        [_p("PERIOD", _S_META_LBL),   _p(month, _S_META_VAL)],
        [_p("STATEMENT REF", _S_META_LBL), _p(stmt_id, _S_META_VAL)],
    ]]
    # Flatten to single-row table with sub-tables in each cell
    meta_row = []
    for cell_items in meta_data[0]:
        sub = Table([[_p(cell_items[0].text, _S_META_LBL)], [_p(cell_items[1].text, _S_META_VAL)]])
        sub.setStyle(TableStyle([
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        meta_row.append(sub)

    meta_table = Table([meta_row], colWidths=[60 * mm, 55 * mm, 55 * mm])
    meta_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 3 * mm))

    # Generated at + currency line
    story.append(_p(
        f"Generated: {generated_at}   ·   Currency: {currency}",
        _s("genmeta", size=7.5, color=_FAINT),
    ))
    story.append(Spacer(1, 4 * mm))
    story.append(_rule())

    # -----------------------------------------------------------------------
    # 2. Summary block
    # -----------------------------------------------------------------------
    story.append(_p("FINANCIAL SUMMARY", _S_SECTION))

    def _sum_row(label: str, value: Optional[str]) -> list:
        return [_p(label, _S_LABEL), _p(_fmt(value, currency), _S_VALUE_R)]

    summary_data = [
        _sum_row("Gross Revenue", summary.get("gross_total")),
        _sum_row("OTA Commission", summary.get("ota_commission_total")),
        _sum_row("Net to Property", summary.get("net_to_property_total")),
        _sum_row(f"Management Fee  ({summary.get('management_fee_pct', '0.00')}%)",
                 summary.get("management_fee_amount")),
    ]

    summ_table = Table(summary_data, colWidths=[95 * mm, 75 * mm])
    summ_table.setStyle(TableStyle([
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, _BG_ALT]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(summ_table)

    # Owner Net — highlighted block
    story.append(Spacer(1, 2 * mm))
    net_row = [[
        _p("OWNER NET TOTAL", _S_NET_LBL),
        _p(_fmt(summary.get("owner_net_total"), currency), _S_NET_VAL),
    ]]
    net_table = Table(net_row, colWidths=[95 * mm, 75 * mm])
    net_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _ACCENT_BG),
        ("ROUNDEDCORNERS", [4]),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOX", (0, 0), (-1, -1), 0.8, _ACCENT),
    ]))
    story.append(net_table)

    # Epistemic tier note — plain-language explanation
    tier = summary.get("overall_epistemic_tier", "—")
    excluded = summary.get("ota_collecting_excluded_from_net", 0)
    story.append(Spacer(1, 2 * mm))
    tier_note = (
        "Data confidence — Tier A: amounts confirmed directly by the channel · "
        "Tier B: estimated from available fields · "
        "Tier C: incomplete data, treat with caution. "
        f"This statement: <b>Tier {tier}</b>."
    )
    if excluded:
        tier_note += f"  {excluded} booking(s) marked OTA-collecting are excluded from net (payout not yet received)."
    story.append(_p(tier_note, _S_NOTE))

    story.append(Spacer(1, 3 * mm))
    story.append(_rule())

    # -----------------------------------------------------------------------
    # 3. Line items table
    # -----------------------------------------------------------------------
    booking_count = len(line_items)
    story.append(_p(
        f"BOOKING DETAILS  —  {booking_count} booking{'s' if booking_count != 1 else ''}",
        _S_SECTION,
    ))

    # Columns: Booking ID | Channel | Check-in | Check-out | Nights | Gross | Net | Tier
    # Total usable width ≈ 174mm
    COL_W = [42 * mm, 20 * mm, 17 * mm, 17 * mm, 12 * mm, 22 * mm, 22 * mm, 14 * mm]
    HEADERS = [
        _p("Booking ID", _S_TH),
        _p("Channel", _S_TH),
        _p("Check-in", _S_TH),
        _p("Check-out", _S_TH),
        _p("Nights", _S_TH_R),
        _p("Gross", _S_TH_R),
        _p("Net", _S_TH_R),
        _p("Tier", _S_TH),
    ]

    table_data = [HEADERS]
    for item in line_items:
        cur = item.get("currency") or currency
        ci = item.get("check_in") or "—"
        co = item.get("check_out") or "—"
        row = [
            _p(item.get("booking_id") or "—", _S_TD_MONO),
            _p(item.get("provider") or "—", _S_TD),
            _p(ci, _S_TD),
            _p(co, _S_TD),
            _p(_nights(item.get("check_in"), item.get("check_out")), _S_TD_R),
            _p(_fmt(item.get("gross"), cur), _S_TD_R),
            _p(_fmt(item.get("net_to_property"), cur), _S_TD_R),
            _p(_tier_label(item.get("epistemic_tier", "")), _tier_style(item.get("epistemic_tier", ""))),
        ]
        table_data.append(row)

    items_table = Table(table_data, colWidths=COL_W, repeatRows=1)
    items_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _BG_HEAD),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, _RULE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _BG_ALT]),
        ("BOX", (0, 0), (-1, -1), 0.5, _RULE),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, _RULE),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        # Right-align Nights, Gross, Net columns
        ("ALIGN", (4, 0), (6, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
    ]))
    story.append(items_table)

    # -----------------------------------------------------------------------
    # 4. Footer
    # -----------------------------------------------------------------------
    story.append(Spacer(1, 6 * mm))
    story.append(_rule(t=0.3))
    story.append(_p(
        f"{pname}   ·   Ref: {stmt_id}   ·   Generated: {generated_at}   ·   Confidential — for recipient only",
        _S_FOOTER,
    ))

    doc.build(story)
    return buf.getvalue()
