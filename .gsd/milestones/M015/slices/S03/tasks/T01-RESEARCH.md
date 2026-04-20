# T01 Learner fallback + lightweight UX baseline matrix

## Scope rule
- Learner-core dashboard routes come from `Sidebar.navItems` plus learner auth/practice flows: `/`, `/training`, `/leaderboard`, `/history`, `/profile`, `/agents/[agentId]`, `/practice/**`, `/login`, `/forgot-password`, `/reset-password`.
- `/support/runtime` remains role-gated support/admin surface, so it is not counted as a learner-shell fallback gap for S03.

## Current fallback inventory

| Route family | Current error.tsx | Current loading.tsx | Status | Notes |
|---|---|---:|---|---|
| `(dashboard)` root | ✅ `web/src/app/(dashboard)/error.tsx` | ❌ | partial | Root error exists; no shared dashboard loading shell yet. |
| `/history` | inherits dashboard error | ✅ `web/src/app/(dashboard)/history/loading.tsx` | partial | Existing loading shell now has status semantics. |
| `/` home | inherits dashboard error | ❌ | gap | Client-heavy dashboard page has no route loading shell. |
| `/training` | inherits dashboard error | ❌ | gap | Category page has async category fetch only. |
| `/training/sales` | inherits dashboard error | ❌ | gap | Client-heavy list; no route loading shell. |
| `/training/presentation` | inherits dashboard error | ❌ | gap | Client-heavy list; no route loading shell. |
| `/leaderboard` | inherits dashboard error | ❌ | gap | Client-heavy leaderboard; no route loading shell. |
| `/profile` | inherits dashboard error | ❌ | gap | Client-heavy profile; no route loading shell. |
| `/agents/[agentId]` | inherits dashboard error | ❌ | gap | Client-heavy persona/PPT selection; no route loading shell. |
| `/practice/[sessionId]` | ✅ `web/src/app/(user)/practice/[sessionId]/error.tsx` | ❌ | partial | Live practice has route error but no route loading file. |
| `/practice/[sessionId]/report` | ✅ | ✅ | covered | Existing shells now include loading status semantics. |
| `/practice/[sessionId]/replay` | ✅ | ✅ | covered | Existing shells now include loading status semantics. |
| `/login` | ❌ | ❌ | gap | No route shell; page-level auth form only. |
| `/forgot-password` | ❌ | ❌ | gap | No route shell; page-level form only. |
| `/reset-password` | ❌ | Suspense fallback only | partial | No route shell; inline Suspense fallback only. |

## Low-risk fixes shipped in T01
- Added explicit `role="status"` / `aria-live="polite"` / `aria-busy="true"` semantics to the existing learner loading shells:
  - `web/src/app/(dashboard)/history/loading.tsx`
  - `web/src/app/(user)/practice/[sessionId]/report/loading.tsx`
  - `web/src/app/(user)/practice/[sessionId]/replay/loading.tsx`
- Added explicit login-field labels plus auth error alert semantics:
  - `web/src/app/(auth)/login/page.tsx`
  - `web/src/app/(auth)/forgot-password/page.tsx`
  - `web/src/app/(auth)/reset-password/page.tsx`
- Upgraded reset-password Suspense fallback to a real loading status surface.

## Baseline risk matrix

| Area | Finding | Disposition |
|---|---|---|
| fallback coverage | Most learner-core dashboard/auth routes still rely on parent error boundary or page-local loading state only. | **T02 target**: add missing route-level `error.tsx` / `loading.tsx` where core learner journeys still white-screen or pop. |
| a11y | Existing loading shells had no screen-reader status; login lacked explicit field labels; auth errors were not announced as alerts. | **Fixed in T01** for existing shells/forms listed above. |
| responsive | Dashboard home remains dense on narrower widths (`grid-cols-3`, `grid-cols-2`, stats/version dialog/header clusters), but still has breakpoint handling and is not a route-shell blocker. | **Deferred baseline**: keep scope out of T01; only fix if a fallback shell change in T02 touches the same surface. |
| timezone | History/report/replay learner surfaces format timestamps with browser-local `toLocaleString("zh-CN")` / `new Date(...)` and do not label timezone basis. | **Deferred baseline**: record only in T01; deciding user-local vs org-fixed timezone is product semantics, not a safe shell tweak. |

## Guidance for T02/T03
1. Prioritize missing learner-core route shells over cosmetic responsive work.
2. Reuse `LearnerRouteErrorState` for practice/report/replay-style error surfaces wherever possible.
3. Keep timezone work to documentation/baseline unless a route shell visibly lies about time context.
4. Keep `/support/runtime` out of learner fallback closure proof.
