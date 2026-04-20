---
id: T01
parent: S04
milestone: M019
key_files:
  - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
  - .gsd/KNOWLEDGE.md
  - .codex/loop/state.json
  - .codex/loop/log.md
key_decisions:
  - Recorded `docs/api-contract/*` plus live backend router wiring as the current release-truth authority line, while explicitly treating frontend analytics beacons, Prometheus export helpers, and legacy spec files as disconnected or drifting surfaces until T02 wires or checks them.
duration: 
verification_result: passed
completed_at: 2026-04-13T05:06:28.324Z
blocker_discovered: false
---

# T01: Inventoried the real release truth line and documented which workflow, metrics, frontend beacons, and spec surfaces are live versus disconnected.

**Inventoried the real release truth line and documented which workflow, metrics, frontend beacons, and spec surfaces are live versus disconnected.**

## What Happened

I executed the S04/T01 inventory as a repo-root truth pass instead of broad replanning. I read the current workflow, ErrorBoundary, performance beacon helper, backend metrics helper, backend router wiring, and the doc/spec artifacts that claim release authority. Based on that evidence, I updated `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md` with a new M019/S04 assembled release truth inventory that separates genuinely connected surfaces from file-only or drifting ones. The inventory now records that `.github/workflows/nfr-performance-check.yml` is the only live GitHub Actions truth line today and that it is backend-only; `docs/api-contract/*` is the most truthful contract family because it points at current router modules; `specs/001-ai-practice-system/contracts/openapi.yaml` and `api-spec.md` are legacy/spec surfaces with drift; and both the frontend `/api/v1/analytics/error|performance|custom` beacons plus the backend Prometheus helper are present in code but not actually wired into a live server-side sink. I also appended a non-obvious release-truth gotcha to `.gsd/KNOWLEDGE.md` so future agents do not mistake those relative analytics beacon URLs for a working observability path.

## Verification

I reran the exact task-plan grep gate across workflows, ErrorBoundary, metrics helper, api-spec, checked-in OpenAPI, and docs/api-contract, and it passed. I then ran a focused repo-root grep proof that showed the frontend analytics beacon URLs and backend Prometheus helper code exist, while the repo still lacks matching backend routes, a mounted metrics export, or a Next.js rewrite/route handler for those endpoints. Finally, I ran a grep proof that the new assembled inventory and knowledge entry are now durable, grep-discoverable artifacts alongside the current docs/api-contract truth line and the legacy openapi/api-spec drift examples.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `rg -n "analytics/error|metrics|openapi|api-contract|pip install -e|requirements.txt|package-lock" .github/workflows web/src/components/ErrorBoundary.tsx backend/src/common/monitoring/metrics.py api-spec.md specs/001-ai-practice-system/contracts/openapi.yaml docs/api-contract` | 0 | ✅ pass | 36ms |
| 2 | `rg -n "analytics/error|analytics/performance|analytics/custom|MetricsMiddleware|initialize_metrics\(|get_metrics\(|/metrics|add_middleware\(|next.config" web/src/components/ErrorBoundary.tsx web/src/lib/performance.ts backend/src/common/api/analytics.py backend/src/common/monitoring/metrics.py backend/src/main.py backend/src/common/middleware/auth.py web/next.config.ts` | 0 | ✅ pass | 16ms |
| 3 | `rg -n "/auth/wechat|/practice/sessions|/api/v1/admin/release-verification|/api/v1/support/runtime|POST /api/v1/sessions|POST /api/v1/practice/sessions|M019/S04 assembled release truth inventory|M019/S04 release-truth gotcha" specs/001-ai-practice-system/contracts/openapi.yaml api-spec.md docs/api-contract .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md .gsd/KNOWLEDGE.md` | 0 | ✅ pass | 14ms |

## Deviations

None. I stayed within the task contract and only adapted the inventory to the surrounding repo reality.

## Known Issues

The inventory intentionally leaves several real gaps unresolved for T02: frontend `/api/v1/analytics/error|performance|custom` beacons are still disconnected, `backend/src/common/monitoring/metrics.py` is still helper-only with no live `/metrics` route, and the checked-in `openapi.yaml` / `api-spec.md` still drift from current router authority.

## Files Created/Modified

- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`
- `.gsd/KNOWLEDGE.md`
- `.codex/loop/state.json`
- `.codex/loop/log.md`
