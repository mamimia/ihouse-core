"""
Phase 541 — Frontend Component Smoke Tests
=============================================

Uses vitest + @testing-library/react pattern.
Run: npx vitest run __tests__/
"""
import pytest
from unittest.mock import patch, MagicMock


# --- Phase 541: Verify frontend component structure ---
# These test that the key TSX files exist and are well-formed.
# We can't run vitest here, so we do structural validation.


class TestFrontendStructure:
    """Verify that critical frontend files exist and have expected content."""

    @staticmethod
    def _read_file(path: str) -> str:
        import os
        full_path = os.path.join(os.path.dirname(__file__), "..", "ihouse-ui", path)
        with open(full_path) as f:
            return f.read()

    def test_admin_nav_exists(self):
        """Phase 525 — AdminNav component exists."""
        content = self._read_file("components/AdminNav.tsx")
        assert "AdminNav" in content
        assert "Operations" in content
        assert "Financial" in content
        assert "Integration" in content
        assert "System" in content

    def test_sidebar_has_active_highlighting(self):
        """Phase 526 — Sidebar uses usePathname for active state."""
        content = self._read_file("components/Sidebar.tsx")
        assert "usePathname" in content
        assert "isActive" in content

    def test_not_found_page_exists(self):
        """Phase 540 — Custom 404 page exists."""
        content = self._read_file("app/not-found.tsx")
        assert "Page Not Found" in content
        assert "/dashboard" in content

    def test_error_page_exists(self):
        """Phase 540 — Global error page exists."""
        content = self._read_file("app/error.tsx")
        assert "Something went wrong" in content
        assert "reset" in content

    def test_health_dashboard_exists(self):
        """Phase 527 — System Health dashboard exists."""
        content = self._read_file("app/(app)/admin/health/page.tsx")
        assert "SystemHealthPage" in content or "System" in content

    def test_settings_page_exists(self):
        """Phase 528 — Settings page exists."""
        content = self._read_file("app/(app)/settings/page.tsx")
        assert "Settings" in content

    def test_audit_trail_exists(self):
        """Phase 539 — Audit trail page exists."""
        content = self._read_file("app/(app)/admin/audit/page.tsx")
        assert "Audit" in content

    def test_guest_messaging_exists(self):
        """Phase 534 — Guest messaging hub exists."""
        content = self._read_file("app/(app)/guests/messages/page.tsx")
        assert "Messages" in content

    def test_checkin_dashboard_exists(self):
        """Phase 531 — Check-in readiness dashboard exists."""
        content = self._read_file("app/(app)/ops/checkin/page.tsx")
        assert "check-in" in content.lower()

    def test_checkout_page_exists(self):
        """Phase 532 — Check-out page exists."""
        content = self._read_file("app/(app)/ops/checkout/page.tsx")
        assert "check-out" in content.lower() or "checkout" in content.lower()
