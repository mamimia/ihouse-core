"""
Phases 729–745 — Wave 8+9 Tests
==================================

729: Contract — visibility toggle CRUD
730: Contract — filtered owner summary
731: Contract — owner auth (placeholder)
732: Contract — specialist CRUD
733: Contract — filtered maintenance tasks
734: Contract — external worker push
735: E2E — owner + maintenance flow
736+: i18n tests
"""
from __future__ import annotations

import json
import sys
import os
import asyncio
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


# ======================================================================
# Phase 729: Contract — visibility toggle CRUD
# ======================================================================

class TestPhase729_VisibilityToggle(unittest.TestCase):

    def test_set_visibility(self):
        from api.owner_portal_v2_router import set_owner_visibility
        mock_db = MagicMock()
        mock_db.table.return_value.upsert.return_value.execute.return_value = MagicMock(data=[])
        resp = asyncio.run(set_owner_visibility(
            "O1", "P1", {"visible_fields": {"bookings": True}}, tenant_id="t1", client=mock_db))
        self.assertEqual(resp.status_code, 200)

    def test_invalid_field_rejected(self):
        from api.owner_portal_v2_router import set_owner_visibility
        resp = asyncio.run(set_owner_visibility(
            "O1", "P1", {"visible_fields": {"bad_field": True}}, tenant_id="t1"))
        self.assertEqual(resp.status_code, 400)

    def test_get_default_visibility(self):
        from api.owner_portal_v2_router import get_owner_visibility
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
        resp = asyncio.run(get_owner_visibility("O1", "P1", tenant_id="t1", client=mock_db))
        body = json.loads(resp.body)
        self.assertTrue(body["visible_fields"]["bookings"])
        self.assertFalse(body["visible_fields"]["maintenance_reports"])


# ======================================================================
# Phase 730: Contract — filtered owner summary
# ======================================================================

class TestPhase730_FilteredSummary(unittest.TestCase):

    def test_summary_with_defaults(self):
        from api.owner_portal_v2_router import owner_property_summary
        mock_db = MagicMock()
        # All calls return empty
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
        mock_db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
        mock_db.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        resp = asyncio.run(owner_property_summary("O1", "P1", tenant_id="t1", client=mock_db))
        self.assertEqual(resp.status_code, 200)


# ======================================================================
# Phase 732: Contract — specialist CRUD
# ======================================================================

class TestPhase732_SpecialtyCRUD(unittest.TestCase):

    def test_create_specialty(self):
        from api.owner_portal_v2_router import create_specialty
        mock_db = MagicMock()
        mock_db.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[{"id": "s1", "name": "Plumbing", "specialty_key": "plumbing"}])
        resp = asyncio.run(create_specialty(
            {"name": "Plumbing", "specialty_key": "plumbing"}, tenant_id="t1", client=mock_db))
        self.assertEqual(resp.status_code, 201)

    def test_missing_name(self):
        from api.owner_portal_v2_router import create_specialty
        resp = asyncio.run(create_specialty({"specialty_key": "x"}, tenant_id="t1"))
        self.assertEqual(resp.status_code, 400)

    def test_update_specialty(self):
        from api.owner_portal_v2_router import update_specialty
        mock_db = MagicMock()
        mock_db.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": "s1", "name": "Updated"}])
        resp = asyncio.run(update_specialty("s1", {"name": "Updated"}, tenant_id="t1", client=mock_db))
        self.assertEqual(resp.status_code, 200)

    def test_deactivate_specialty(self):
        from api.owner_portal_v2_router import deactivate_specialty
        mock_db = MagicMock()
        mock_db.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        resp = asyncio.run(deactivate_specialty("s1", tenant_id="t1", client=mock_db))
        body = json.loads(resp.body)
        self.assertFalse(body["active"])


# ======================================================================
# Phase 734: Contract — external worker push
# ======================================================================

class TestPhase734_ExternalPush(unittest.TestCase):

    def test_push_to_external(self):
        from api.owner_portal_v2_router import push_task_to_external
        mock_db = MagicMock()
        call_idx = {"i": 0}
        def table_side(name):
            chain = MagicMock()
            call_idx["i"] += 1
            if call_idx["i"] == 1:
                chain.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
                    data=[{"id": "T1", "task_kind": "MAINTENANCE", "property_id": "P1"}])
            else:
                chain.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
                chain.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
                chain.insert.return_value.execute.return_value = MagicMock(data=[])
                chain.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
            return chain
        mock_db.table = table_side
        resp = asyncio.run(push_task_to_external("T1", {"worker_id": "EXT-1"}, tenant_id="t1", client=mock_db))
        self.assertEqual(resp.status_code, 200)
        body = json.loads(resp.body)
        self.assertTrue(body["notification_sent"])

    def test_missing_worker_id(self):
        from api.owner_portal_v2_router import push_task_to_external
        resp = asyncio.run(push_task_to_external("T1", {}, tenant_id="t1"))
        self.assertEqual(resp.status_code, 400)

    def test_task_not_found(self):
        from api.owner_portal_v2_router import push_task_to_external
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
        resp = asyncio.run(push_task_to_external("NONEXIST", {"worker_id": "W1"}, tenant_id="t1", client=mock_db))
        self.assertEqual(resp.status_code, 404)


# ======================================================================
# Phase 728/735: Maintenance mode toggle
# ======================================================================

class TestPhase728_MaintenanceMode(unittest.TestCase):

    def test_set_mode(self):
        from api.owner_portal_v2_router import set_maintenance_mode
        mock_db = MagicMock()
        mock_db.table.return_value.upsert.return_value.execute.return_value = MagicMock(data=[])
        resp = asyncio.run(set_maintenance_mode({"mode": "specialists"}, tenant_id="t1", client=mock_db))
        body = json.loads(resp.body)
        self.assertEqual(body["maintenance_mode"], "specialists")

    def test_invalid_mode(self):
        from api.owner_portal_v2_router import set_maintenance_mode
        resp = asyncio.run(set_maintenance_mode({"mode": "invalid"}, tenant_id="t1"))
        self.assertEqual(resp.status_code, 400)

    def test_get_mode_default(self):
        from api.owner_portal_v2_router import get_maintenance_mode
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
        resp = asyncio.run(get_maintenance_mode(tenant_id="t1", client=mock_db))
        body = json.loads(resp.body)
        self.assertEqual(body["maintenance_mode"], "single")


# ======================================================================
# Phase 736: i18n API
# ======================================================================

class TestPhase736_I18nAPI(unittest.TestCase):

    def test_get_full_pack_en(self):
        from api.i18n_router import get_language_pack_api
        resp = asyncio.run(get_language_pack_api("en"))
        self.assertEqual(resp.status_code, 200)
        body = json.loads(resp.body)
        self.assertIn("pack", body)
        self.assertIn("guest_form", body["pack"])

    def test_get_full_pack_th(self):
        from api.i18n_router import get_language_pack_api
        resp = asyncio.run(get_language_pack_api("th"))
        body = json.loads(resp.body)
        self.assertEqual(body["language"], "th")
        self.assertNotEqual(body["pack"]["guest_form"]["title"], "Guest Registration")

    def test_get_category_cleaning(self):
        from api.i18n_router import get_category_pack_api
        resp = asyncio.run(get_category_pack_api("en", "cleaning"))
        body = json.loads(resp.body)
        self.assertEqual(body["category"], "cleaning")
        self.assertEqual(body["pack"]["change_sheets"], "Change sheets")

    def test_unsupported_language(self):
        from api.i18n_router import get_language_pack_api
        resp = asyncio.run(get_language_pack_api("xx"))
        self.assertEqual(resp.status_code, 400)

    def test_unknown_category(self):
        from api.i18n_router import get_category_pack_api
        resp = asyncio.run(get_category_pack_api("en", "nonexistent"))
        self.assertEqual(resp.status_code, 404)


# ======================================================================
# Phase 741: Auto-translate
# ======================================================================

class TestPhase741_AutoTranslate(unittest.TestCase):

    def test_translate_passthrough(self):
        from api.i18n_router import auto_translate
        resp = asyncio.run(auto_translate(
            {"text": "สวัสดี", "source_lang": "th", "target_lang": "en"},
            tenant_id="t1"))
        self.assertEqual(resp.status_code, 200)
        body = json.loads(resp.body)
        self.assertIn("translated", body)

    def test_translate_no_text(self):
        from api.i18n_router import auto_translate
        resp = asyncio.run(auto_translate({"text": ""}, tenant_id="t1"))
        self.assertEqual(resp.status_code, 400)


# ======================================================================
# Phase 742: Worker language preference
# ======================================================================

class TestPhase742_WorkerLangPref(unittest.TestCase):

    def test_set_language(self):
        from api.i18n_router import set_worker_language
        mock_db = MagicMock()
        mock_db.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        resp = asyncio.run(set_worker_language("W1", {"language": "th"}, tenant_id="t1", client=mock_db))
        body = json.loads(resp.body)
        self.assertEqual(body["language_preference"], "th")

    def test_invalid_language(self):
        from api.i18n_router import set_worker_language
        resp = asyncio.run(set_worker_language("W1", {"language": "xx"}, tenant_id="t1"))
        self.assertEqual(resp.status_code, 400)

    def test_get_language_default(self):
        from api.i18n_router import get_worker_language
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
        resp = asyncio.run(get_worker_language("W1", tenant_id="t1", client=mock_db))
        body = json.loads(resp.body)
        self.assertEqual(body["language_preference"], "en")


# ======================================================================
# Phase 743: i18n completeness
# ======================================================================

class TestPhase743_I18nCompleteness(unittest.TestCase):

    def test_all_keys_in_all_languages(self):
        from i18n.i18n_catalog import check_completeness
        missing = check_completeness()
        for lang, keys in missing.items():
            self.assertEqual(len(keys), 0, f"Missing translations for {lang}: {keys}")

    def test_supported_languages(self):
        from i18n.i18n_catalog import SUPPORTED_LANGUAGES
        self.assertIn("en", SUPPORTED_LANGUAGES)
        self.assertIn("th", SUPPORTED_LANGUAGES)
        self.assertIn("he", SUPPORTED_LANGUAGES)

    def test_all_categories_present(self):
        from i18n.i18n_catalog import get_all_categories
        cats = get_all_categories()
        self.assertIn("guest_form", cats)
        self.assertIn("cleaning", cats)
        self.assertIn("problem_report", cats)
        self.assertIn("guest_portal", cats)
        self.assertIn("worker", cats)
        self.assertIn("common", cats)


# ======================================================================
# Phase 744: Contract — form, checklist, portal in TH
# ======================================================================

class TestPhase744_ThaiTranslations(unittest.TestCase):

    def test_guest_form_in_thai(self):
        from i18n.i18n_catalog import get_category_pack
        pack = get_category_pack("guest_form", "th")
        self.assertEqual(pack["title"], "ลงทะเบียนแขก")
        self.assertEqual(pack["submit"], "ส่ง")

    def test_cleaning_in_thai(self):
        from i18n.i18n_catalog import get_category_pack
        pack = get_category_pack("cleaning", "th")
        self.assertEqual(pack["change_sheets"], "เปลี่ยนผ้าปูที่นอน")

    def test_portal_in_thai(self):
        from i18n.i18n_catalog import get_category_pack
        pack = get_category_pack("guest_portal", "th")
        self.assertEqual(pack["welcome"], "ยินดีต้อนรับ")

    def test_hebrew_translations(self):
        from i18n.i18n_catalog import get_category_pack
        pack = get_category_pack("guest_form", "he")
        self.assertEqual(pack["title"], "רישום אורח")


if __name__ == "__main__":
    unittest.main()
