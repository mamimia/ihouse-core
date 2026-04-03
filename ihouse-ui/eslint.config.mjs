import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
  // Phase 973 audit fix (Marco/08 + Talia/07): Enforce staffApi isolation.
  // staffApi.ts is the worker-surface API client. It reads from sessionStorage
  // (tab-scoped Act As tokens) and must NEVER be imported by admin pages which
  // use localStorage-backed lib/api.ts. Mixing the two caused a silent 401
  // regression in the 2026-03-26 staging incident.
  {
    files: ["**/*.ts", "**/*.tsx"],
    // Target non-ops files only; ops/* pages are the intended consumers.
    ignores: ["app/(app)/ops/**", "app/(app)/worker/**"],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          paths: [
            {
              name: "@/lib/staffApi",
              message:
                "staffApi must only be imported from /ops/* or /worker/* surfaces. Use lib/api.ts for admin pages. See 2026-03-26 staging incident.",
            },
          ],
          patterns: [
            {
              group: ["**/lib/staffApi", "../**/staffApi", "../../**/staffApi"],
              message:
                "staffApi must only be imported from /ops/* or /worker/* surfaces. Use lib/api.ts for admin pages.",
            },
          ],
        },
      ],
    },
  },
]);

export default eslintConfig;

