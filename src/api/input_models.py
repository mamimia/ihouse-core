"""
Phase 573 — Pydantic Input Models for Critical Endpoints
=========================================================

Standardized request body models with validation rules.
These models enforce field constraints at the API boundary
before any business logic runs.

Used by routers that accept POST/PUT/PATCH with JSON bodies.
"""
from __future__ import annotations

from datetime import date
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class BookingCreateRequest(BaseModel):
    """Input model for creating / ingesting a booking."""
    booking_id: str = Field(..., min_length=1, max_length=100, description="Unique booking identifier")
    tenant_id: str = Field(..., min_length=1, max_length=50)
    source: str = Field(..., min_length=1, max_length=30, description="OTA source (airbnb, bookingcom, etc.)")
    property_id: str = Field(..., min_length=1, max_length=100)
    check_in: str = Field(..., description="Check-in date YYYY-MM-DD")
    check_out: str = Field(..., description="Check-out date YYYY-MM-DD")
    guest_name: Optional[str] = Field(None, max_length=200)
    reservation_ref: Optional[str] = Field(None, max_length=100)

    @field_validator("check_in", "check_out")
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        try:
            date.fromisoformat(v)
        except ValueError:
            raise ValueError(f"Invalid date format: {v}. Expected YYYY-MM-DD")
        return v


class TaskCreateRequest(BaseModel):
    """Input model for creating a task."""
    tenant_id: str = Field(..., min_length=1, max_length=50)
    property_id: str = Field(..., min_length=1, max_length=100)
    task_kind: str = Field(..., min_length=1, max_length=50, description="Task type (cleaning, inspection, etc.)")
    priority: str = Field("normal", pattern=r"^(critical|high|normal|low)$", description="Task priority")
    assigned_to: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = Field(None, max_length=2000)
    deadline: Optional[str] = Field(None, description="ISO datetime deadline")


class PropertyCreateRequest(BaseModel):
    """Input model for creating a property."""
    tenant_id: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=200, description="Property display name")
    property_type: str = Field("apartment", max_length=50)
    address: Optional[str] = Field(None, max_length=500)
    city: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)
    bedrooms: Optional[int] = Field(None, ge=0, le=50)
    max_guests: Optional[int] = Field(None, ge=1, le=100)


class MaintenanceCreateRequest(BaseModel):
    """Input model for creating a maintenance request."""
    property_id: str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field("", max_length=5000)
    priority: str = Field("medium", pattern=r"^(low|medium|high|urgent)$")


class BookingFlagsRequest(BaseModel):
    """Input model for setting booking flags."""
    is_vip: Optional[bool] = None
    is_disputed: Optional[bool] = None
    needs_review: Optional[bool] = None
    operator_note: Optional[str] = Field(None, max_length=1000)
    flagged_by: Optional[str] = Field(None, max_length=100)
