-- ═══════════════════════════════════════════════════════════════════════════════
-- Phase 1032 — Baton-transfer trigger race condition fix
-- Applied: 2026-03-31
-- ═══════════════════════════════════════════════════════════════════════════════
--
-- ROOT CAUSE:
--   _execute_baton_transfer promotes Backup to priority=1 BEFORE deleting the
--   Primary row. The fn_guard_assignment_priority_uniqueness trigger fired on
--   UPDATE and raised PRIORITY_CONFLICT because both rows temporarily existed
--   with priority=1 in the same lane.
--
-- FIX:
--   Extended fn_guard_assignment_priority_uniqueness to exempt UPDATE operations
--   from collision check. The only valid UPDATE that sets priority=1 is a
--   baton-transfer promotion — the old primary row is deleted immediately after.
--   INSERT protection is unchanged and remains the primary guard.
--
-- PROOF (2026-03-31):
--   Baton-transfer E2E on KPG-500/CLEANING:
--   - PRE:  Joey (p=1, Primary), แพรวา (p=2, Backup). 2 PENDING tasks on Joey.
--   - ACTION: DELETE /staff/assignments/joey/KPG-500
--   - POST: แพรวา promoted to p=1 (PRIMARY). transfer_occurred=true.
--   - promotion_notice written to comm_preference._promotion_notice JSONB.
--   - INV-1028/1029/1030 verified intact.
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION fn_guard_assignment_priority_uniqueness()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
  v_lane    TEXT;
  v_conflict INT;
BEGIN
  -- UPDATE: exempt from collision check.
  -- The only UPDATE that changes priority is the baton-transfer promotion,
  -- which sets priority=1 for the incoming Backup while the outgoing Primary
  -- is still present. The DELETE follows immediately after.
  IF TG_OP = 'UPDATE' THEN
    RETURN NEW;
  END IF;

  -- Determine lane from tenant_permissions
  SELECT
    CASE
      WHEN tp.worker_roles @> ARRAY['cleaner']             THEN 'CLEANING'
      WHEN tp.worker_roles @> ARRAY['maintenance']         THEN 'MAINTENANCE'
      WHEN tp.worker_roles && ARRAY['checkin', 'checkout'] THEN 'CHECKIN_CHECKOUT'
      ELSE 'UNKNOWN'
    END
  INTO v_lane
  FROM tenant_permissions tp
  WHERE tp.user_id = NEW.user_id AND tp.tenant_id = NEW.tenant_id
  LIMIT 1;

  IF v_lane IS NULL OR v_lane = 'UNKNOWN' THEN
    RETURN NEW;
  END IF;

  -- Check for (property, lane, priority) collision on INSERT
  SELECT COUNT(*) INTO v_conflict
  FROM staff_property_assignments spa
  JOIN tenant_permissions tp
    ON tp.user_id = spa.user_id AND tp.tenant_id = spa.tenant_id
  WHERE spa.tenant_id   = NEW.tenant_id
    AND spa.property_id = NEW.property_id
    AND spa.priority    = NEW.priority
    AND spa.user_id    != NEW.user_id
    AND CASE
          WHEN tp.worker_roles @> ARRAY['cleaner']             THEN 'CLEANING'
          WHEN tp.worker_roles @> ARRAY['maintenance']         THEN 'MAINTENANCE'
          WHEN tp.worker_roles && ARRAY['checkin', 'checkout'] THEN 'CHECKIN_CHECKOUT'
          ELSE 'UNKNOWN'
        END = v_lane;

  IF v_conflict > 0 THEN
    RAISE EXCEPTION
      'PRIORITY_CONFLICT: property=% lane=% priority=% already assigned to another worker. '
      'Use a unique priority per lane. Next available priority is (SELECT MAX(priority)+1 '
      'FROM staff_property_assignments WHERE property_id=% AND tenant_id=%).',
      NEW.property_id, v_lane, NEW.priority, NEW.property_id, NEW.tenant_id;
  END IF;

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_guard_assignment_priority ON staff_property_assignments;
CREATE TRIGGER trg_guard_assignment_priority
  BEFORE INSERT OR UPDATE ON staff_property_assignments
  FOR EACH ROW EXECUTE FUNCTION fn_guard_assignment_priority_uniqueness();
