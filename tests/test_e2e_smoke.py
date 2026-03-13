"""Phase 422 — E2E Smoke Test Suite.

Validates critical frontend page routes and backend endpoints are reachable.
"""

import pytest
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class TestFrontendPageRoutes:
    """Validates all expected page.tsx files exist."""

    EXPECTED_PAGES = [
        "(app)/dashboard/page.tsx",
        "(app)/bookings/page.tsx",
        "(app)/financial/page.tsx",
        "(app)/tasks/page.tsx",
        "(app)/worker/page.tsx",
        "(app)/owner/page.tsx",
        "(app)/admin/properties/page.tsx",
        "(app)/admin/properties/[propertyId]/page.tsx",
        "(app)/admin/page.tsx",
        "(public)/login/page.tsx",
        "(public)/page.tsx",
    ]

    def test_critical_pages_exist(self):
        """All critical page.tsx files exist."""
        ui_app = ROOT / "ihouse-ui" / "app"
        for page_path in self.EXPECTED_PAGES:
            full_path = ui_app / page_path
            assert full_path.exists(), f"Missing critical page: {page_path}"

    def test_no_empty_pages(self):
        """All page.tsx files have content > 100 bytes."""
        ui_app = ROOT / "ihouse-ui" / "app"
        for page_path in self.EXPECTED_PAGES:
            full_path = ui_app / page_path
            if full_path.exists():
                assert full_path.stat().st_size > 100, f"Empty page: {page_path}"


class TestBackendEndpointRoutes:
    """Validates critical backend routes are registered."""

    def test_main_app_imports(self):
        """main.py can be imported."""
        src = ROOT / "src"
        sys.path.insert(0, str(src))
        os.environ.setdefault("IHOUSE_ENV", "test")
        os.environ.setdefault("SUPABASE_URL", "http://test.supabase.co")
        os.environ.setdefault("SUPABASE_KEY", "test-key")
        os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-srv-key")
        from main import app
        assert app is not None

    def test_critical_routes_exist(self):
        """Core routes are registered in the app."""
        src = ROOT / "src"
        sys.path.insert(0, str(src))
        os.environ.setdefault("IHOUSE_ENV", "test")
        os.environ.setdefault("SUPABASE_URL", "http://test.supabase.co")
        os.environ.setdefault("SUPABASE_KEY", "test-key")
        os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-srv-key")
        from main import app
        routes = {r.path for r in app.routes if hasattr(r, "path")}
        critical = ["/health", "/docs", "/openapi.json"]
        for route in critical:
            assert route in routes, f"Missing critical route: {route}"

    def test_api_router_files_exist(self):
        """Key API router files exist."""
        api_dir = ROOT / "src" / "api"
        key_routers = [
            "bookings_router.py",
            "property_admin_router.py",
            "auth_router.py",
        ]
        for router in key_routers:
            assert (api_dir / router).exists(), f"Missing router: {router}"
