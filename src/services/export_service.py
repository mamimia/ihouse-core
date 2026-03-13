"""
Phase 535 — CSV Export Service
================================

Generates CSV content for various data types:
  - Bookings list
  - Financial facts
  - Guest feedback
  - Audit log

Pure functions returning CSV strings. No file I/O.
Router provides download responses.
"""
from __future__ import annotations

import csv
import io
from typing import Any


def bookings_to_csv(bookings: list[dict]) -> str:
    """Convert a list of booking dicts to CSV string."""
    if not bookings:
        return "booking_id,property_id,check_in,check_out,status,source,guest_name\n"

    output = io.StringIO()
    fields = ["booking_id", "property_id", "check_in_date", "check_out_date",
              "status", "source", "guest_name"]
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for b in bookings:
        writer.writerow(b)
    return output.getvalue()


def financial_facts_to_csv(facts: list[dict]) -> str:
    """Convert financial facts to CSV string."""
    if not facts:
        return "booking_id,property_id,gross_revenue,ota_commission,net_to_property,management_fee,currency\n"

    output = io.StringIO()
    fields = ["booking_id", "property_id", "gross_revenue", "ota_commission",
              "net_to_property", "management_fee", "currency", "extraction_date"]
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for f in facts:
        writer.writerow(f)
    return output.getvalue()


def guest_feedback_to_csv(feedback: list[dict]) -> str:
    """Convert guest feedback to CSV string."""
    if not feedback:
        return "feedback_id,property_id,guest_name,rating,comment,created_at\n"

    output = io.StringIO()
    fields = ["feedback_id", "property_id", "guest_name", "rating",
              "comment", "created_at"]
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for f in feedback:
        writer.writerow(f)
    return output.getvalue()


def audit_log_to_csv(entries: list[dict]) -> str:
    """Convert audit log entries to CSV string."""
    if not entries:
        return "id,timestamp,user_id,action,entity_type,entity_id,details\n"

    output = io.StringIO()
    fields = ["id", "timestamp", "user_id", "action", "entity_type",
              "entity_id", "details"]
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for e in entries:
        writer.writerow(e)
    return output.getvalue()


def export_data(db: Any, export_type: str, filters: dict | None = None) -> str:
    """
    Fetch data from DB and return CSV string.

    Args:
        db: Supabase client
        export_type: one of 'bookings', 'financials', 'feedback', 'audit'
        filters: optional dict with property_id, date_from, date_to

    Returns:
        CSV string
    """
    filters = filters or {}

    if export_type == "bookings":
        query = db.table("booking_state").select("*")
        if filters.get("property_id"):
            query = query.eq("property_id", filters["property_id"])
        res = query.limit(5000).execute()
        return bookings_to_csv(res.data or [])

    elif export_type == "financials":
        query = db.table("booking_financial_facts").select("*")
        if filters.get("property_id"):
            query = query.eq("property_id", filters["property_id"])
        res = query.limit(5000).execute()
        return financial_facts_to_csv(res.data or [])

    elif export_type == "feedback":
        query = db.table("guest_feedback").select("*")
        if filters.get("property_id"):
            query = query.eq("property_id", filters["property_id"])
        res = query.limit(5000).execute()
        return guest_feedback_to_csv(res.data or [])

    elif export_type == "audit":
        query = db.table("admin_audit_log").select("*")
        res = query.order("timestamp", desc=True).limit(5000).execute()
        return audit_log_to_csv(res.data or [])

    else:
        return f"Unknown export type: {export_type}\n"
