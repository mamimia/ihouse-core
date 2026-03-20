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
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from i18n.i18n_catalog import translate_key

# ---------------------------------------------------------------------------
# Font Registration
# ---------------------------------------------------------------------------
_FONTS_DIR = os.path.join(os.path.dirname(__file__), "..", "assets", "fonts")
try:
    pdfmetrics.registerFont(TTFont('NotoSans', os.path.join(_FONTS_DIR, "NotoSans-Regular.ttf")))
    pdfmetrics.registerFont(TTFont('NotoSansThai', os.path.join(_FONTS_DIR, "NotoSansThai-Regular.ttf")))
    pdfmetrics.registerFont(TTFont('NotoSansHebrew', os.path.join(_FONTS_DIR, "NotoSansHebrew-Regular.ttf")))
    _HAS_NOTO = True
except Exception as e:
    _HAS_NOTO = False

def _get_font_names(lang: str) -> tuple[str, str, str]:
    if not _HAS_NOTO:
        return ("Helvetica", "Helvetica-Bold", "Courier")
    if lang == "th":
        return ("NotoSansThai", "NotoSansThai", "Courier")
    if lang == "he":
        return ("NotoSansHebrew", "NotoSansHebrew", "Courier")
    return ("NotoSans", "NotoSans", "Courier")

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

def _s(
    name: str,
    font: str,
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

def _get_styles(lang: str) -> dict[str, ParagraphStyle]:
    _BASE, _BOLD, _MONO = _get_font_names(lang)
    return {
        "title":    _s("title",    font=_BOLD, size=18, color=_DARK, sb=0, sa=1 * mm),
        "subtitle": _s("subtitle", font=_BASE, size=9,  color=_DIM, sa=0),
        "mlbl":     _s("mlbl",     font=_BASE, size=7.5,color=_FAINT),
        "mval":     _s("mval",     font=_BOLD, size=8,  color=_MID),
        "section":  _s("section",  font=_BOLD, size=7.5,color=_DIM, sb=4 * mm, sa=2 * mm),
        "label":    _s("label",    font=_BASE, size=8.5,color=_DIM),
        "value":    _s("value",    font=_BOLD, size=8.5,color=_DARK),
        "valr":     _s("valr",     font=_BOLD, size=8.5,color=_DARK, align=TA_RIGHT),
        "netlbl":   _s("netlbl",   font=_BOLD, size=11, color=_ACCENT),
        "netval":   _s("netval",   font=_BOLD, size=13, color=_ACCENT, align=TA_RIGHT),
        "th":       _s("th",       font=_BOLD, size=7.5,color=_MID),
        "thr":      _s("thr",      font=_BOLD, size=7.5,color=_MID, align=TA_RIGHT),
        "td":       _s("td",       font=_BASE, size=7.5,color=_MID),
        "tdm":      _s("tdm",      font=_MONO, size=6.5,color=_MID),
        "tdr":      _s("tdr",      font=_BASE, size=7.5,color=_MID,  align=TA_RIGHT),
        "note":     _s("note",     font=_BASE, size=7,  color=_FAINT, sb=1 * mm),
        "footer":   _s("footer",   font=_BASE, size=6.5,color=_FAINT, align=TA_CENTER),
        "ta":       _s("ta",       font=_BOLD, size=7.5,color=colors.HexColor("#059669")),
        "tb":       _s("tb",       font=_BOLD, size=7.5,color=colors.HexColor("#D97706")),
        "tc":       _s("tc",       font=_BOLD, size=7.5,color=colors.HexColor("#DC2626")),
        "genmeta":  _s("genmeta",  font=_BASE, size=7.5, color=_FAINT),
    }

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


def _tier_style(tier: str, styles: dict[str, ParagraphStyle]) -> ParagraphStyle:
    t = (tier or "").upper()
    return {
        "A": styles["ta"],
        "B": styles["tb"],
    }.get(t, styles["tc"])


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
    lang: str = "en",
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
    """
    styles = _get_styles(lang)

    def _t(k: str) -> str:
        return translate_key("owner_statement", k, lang)

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
        title=f"{_t('title')} — {property_id} — {month}",
        author=pname,
        subject=_t("subtitle"),
    )

    story: list = []

    # -----------------------------------------------------------------------
    # 1. Header
    # -----------------------------------------------------------------------
    story.append(_p(_t("title"), styles["title"]))
    story.append(_p(_t("subtitle"), styles["subtitle"]))
    story.append(Spacer(1, 4 * mm))

    # Metadata grid — 3 columns: Property | Period | Reference
    meta_data = [[
        [_p(_t("property"), styles["mlbl"]), _p(property_id, styles["mval"])],
        [_p(_t("period"), styles["mlbl"]),   _p(month, styles["mval"])],
        [_p(_t("statement_ref"), styles["mlbl"]), _p(stmt_id, styles["mval"])],
    ]]
    # Flatten to single-row table with sub-tables in each cell
    meta_row = []
    for cell_items in meta_data[0]:
        sub = Table([[_p(cell_items[0].text, styles["mlbl"])], [_p(cell_items[1].text, styles["mval"])]])
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
        f"{_t('generated')}: {generated_at}   ·   {_t('currency')}: {currency}",
        styles["genmeta"],
    ))
    story.append(Spacer(1, 4 * mm))
    story.append(_rule())

    # -----------------------------------------------------------------------
    # 2. Summary block
    # -----------------------------------------------------------------------
    story.append(_p(_t("financial_summary"), styles["section"]))

    def _sum_row(label: str, value: Optional[str]) -> list:
        return [_p(label, styles["label"]), _p(_fmt(value, currency), styles["valr"])]

    summary_data = [
        _sum_row(_t("gross_revenue"), summary.get("gross_total")),
        _sum_row(_t("ota_commission"), summary.get("ota_commission_total")),
        _sum_row(_t("net_to_property"), summary.get("net_to_property_total")),
        _sum_row(f"{_t('management_fee')}  ({summary.get('management_fee_pct', '0.00')}%)",
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
        _p(_t("owner_net_total"), styles["netlbl"]),
        _p(_fmt(summary.get("owner_net_total"), currency), styles["netval"]),
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
        f"{_t('tier_explanation')} <b>{_t('tier')} {tier}</b>."
    )
    if excluded:
        tier_note += f"  {excluded} {_t('excluded_note')}"
    story.append(_p(tier_note, styles["note"]))

    story.append(Spacer(1, 3 * mm))
    story.append(_rule())

    # -----------------------------------------------------------------------
    # 3. Line items table
    # -----------------------------------------------------------------------
    booking_count = len(line_items)
    booking_lbl = _t("booking") if booking_count == 1 else _t("bookings")
    story.append(_p(
        f"{_t('booking_details')}  —  {booking_count} {booking_lbl}",
        styles["section"],
    ))

    # Columns: Booking ID | Channel | Check-in | Check-out | Nights | Gross | Net | Tier
    # Total usable width ≈ 174mm
    COL_W = [42 * mm, 20 * mm, 17 * mm, 17 * mm, 12 * mm, 22 * mm, 22 * mm, 14 * mm]
    HEADERS = [
        _p(_t("booking_id"), styles["th"]),
        _p(_t("channel"), styles["th"]),
        _p(_t("check_in"), styles["th"]),
        _p(_t("check_out"), styles["th"]),
        _p(_t("nights"), styles["thr"]),
        _p(_t("gross"), styles["thr"]),
        _p(_t("net"), styles["thr"]),
        _p(_t("tier"), styles["th"]),
    ]

    table_data = [HEADERS]
    for item in line_items:
        cur = item.get("currency") or currency
        ci = item.get("check_in") or "—"
        co = item.get("check_out") or "—"
        row = [
            _p(item.get("booking_id") or "—", styles["tdm"]),
            _p(item.get("provider") or "—", styles["td"]),
            _p(ci, styles["td"]),
            _p(co, styles["td"]),
            _p(_nights(item.get("check_in"), item.get("check_out")), styles["tdr"]),
            _p(_fmt(item.get("gross"), cur), styles["tdr"]),
            _p(_fmt(item.get("net_to_property"), cur), styles["tdr"]),
            _p(_tier_label(item.get("epistemic_tier", "")), _tier_style(item.get("epistemic_tier", ""), styles)),
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
        f"{pname}   ·   {_t('ref')}: {stmt_id}   ·   {_t('generated')}: {generated_at}   ·   {_t('footer_confidential')}",
        styles["footer"],
    ))

    doc.build(story)
    return buf.getvalue()
