import pytest
from datetime import datetime
from services.statement_generator import generate_owner_statement_pdf, _HAS_NOTO

def test_pdf_localization_th():
    summary = {
        "currency": "THB",
        "gross_total": "1000.00",
        "ota_commission_total": "100.00",
        "net_to_property_total": "900.00",
        "management_fee_pct": "10.00",
        "management_fee_amount": "90.00",
        "owner_net_total": "810.00",
        "overall_epistemic_tier": "A",
        "ota_collecting_excluded_from_net": 0,
    }
    line_items = [
        {
            "booking_id": "BK-123",
            "provider": "airbnb",
            "currency": "THB",
            "check_in": "2026-03-01",
            "check_out": "2026-03-05",
            "nights": "4",
            "gross": "1000.00",
            "ota_commission": "100.00",
            "net_to_property": "900.00",
            "epistemic_tier": "A",
            "lifecycle_status": "GUEST_PAID",
        }
    ]
    
    pdf_bytes = generate_owner_statement_pdf(
        property_id="PROP-1",
        month="2026-03",
        tenant_id="tenant-1",
        summary=summary,
        line_items=line_items,
        generated_at=datetime.utcnow().isoformat(),
        platform_name="Test Platform",
        lang="th"
    )
    
    # Just checking it generates a PDF successfully without throwing font errors
    assert pdf_bytes.startswith(b"%PDF-")

def test_pdf_localization_he():
    summary = {
        "currency": "ILS",
        "gross_total": "1000.00",
        "ota_commission_total": "100.00",
        "net_to_property_total": "900.00",
        "management_fee_pct": "10.00",
        "management_fee_amount": "90.00",
        "owner_net_total": "810.00",
        "overall_epistemic_tier": "A",
        "ota_collecting_excluded_from_net": 0,
    }
    line_items = []
    
    pdf_bytes = generate_owner_statement_pdf(
        property_id="PROP-2",
        month="2026-03",
        tenant_id="tenant-1",
        summary=summary,
        line_items=line_items,
        generated_at=datetime.utcnow().isoformat(),
        platform_name="Test Platform",
        lang="he"
    )
    
    assert pdf_bytes.startswith(b"%PDF-")

def test_pdf_localization_uses_notosans():
    # If font files were downloaded correctly, it should be True
    assert _HAS_NOTO is True
