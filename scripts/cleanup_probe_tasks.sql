-- Proof/Staging Hygiene Enforcement Script (Phase 1030)
-- 
-- Rule (INV-1007): All synthetic/proof tasks MUST use task_id prefix 'ZTEST-' 
-- (or legacy 'proof-'), property_id = a dedicated 'KPG-ZTEST', and booking_id 
-- prefix 'ZTEST-'. Real property IDs and booking IDs MUST NOT be used in proof 
-- fixtures to prevent operational pollution on staging.
--
-- Run this script to clean up synthetic tasks.

DELETE FROM tasks 
WHERE task_id LIKE 'ZTEST-%' 
   OR task_id LIKE 'proof-%'
   OR booking_id LIKE 'ZTEST-%'
   OR property_id = 'KPG-ZTEST';
