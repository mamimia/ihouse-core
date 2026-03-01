/**
 * Phase 11 – Single Source of Truth
 *
 * Deterministically generates the Python-facing kind_registry.json from Core.
 * No IO besides writing the target file.
 */

import { writeFileSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
// ESM-safe import for ts-node: use .js extension (ts-node maps it to the .ts source)
import { EVENT_KINDS } from "./kinds.js";

type KindRegistry = Record<string, string>;

/**
 * Current routing policy:
 * Kind maps to the skill folder name (Python runner expects this).
 *
 * This is intentionally explicit to avoid hidden drift.
 * Later phases can migrate skills inward while preserving the mapping contract.
 */
const KIND_TO_SKILL: KindRegistry = {
  STATE_TRANSITION: "state-transition-guard",
  BOOKING_CONFLICT: "booking-conflict-resolver",
  TASK_COMPLETION: "task-completion-validator",
  SLA_ESCALATION: "sla-escalation-engine",
};

function assertCompleteMapping() {
  const kinds = EVENT_KINDS as readonly string[];

  for (const k of kinds) {
    if (!(k in KIND_TO_SKILL)) {
      throw new Error(`Missing mapping for kind: ${k}`);
    }
    if (typeof KIND_TO_SKILL[k] !== "string" || KIND_TO_SKILL[k].length === 0) {
      throw new Error(`Invalid skill mapping for kind: ${k}`);
    }
  }

  for (const k of Object.keys(KIND_TO_SKILL)) {
    if (!kinds.includes(k)) {
      throw new Error(`Mapping contains unknown kind not in Core list: ${k}`);
    }
  }
}

export function generateKindRegistryJson(targetPath: string) {
  assertCompleteMapping();

  const outPath = resolve(targetPath);
  mkdirSync(dirname(outPath), { recursive: true });

  const json = JSON.stringify(KIND_TO_SKILL, null, 2) + "\n";
  writeFileSync(outPath, json, { encoding: "utf-8" });
}

// Run as CLI
generateKindRegistryJson(".agent/system/kind_registry.json");
