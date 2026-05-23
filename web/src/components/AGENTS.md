# Components — `web/src/components/`

Shared React UI. Prefer Server Components in `app/`; client widgets live here.

## Domain Map

| Path | Use when |
|------|----------|
| `ui/` | Primitives only — buttons, glass surfaces, toast, confirm, tables |
| `layout/` | Dashboard/admin shells and sidebars |
| `providers/` | App-wide client providers |
| `practice/` | Live/replay practice UX |
| `admin/` | Admin consoles (especially `knowledge-answer/`) |
| `analytics/`, `exam/`, `training/`, `highlights/`, `learner/`, `dashboard/`, `audio/` | Feature-specific widgets |

## Hard Rules

- No `alert/confirm/prompt` — `ui/confirm-dialog`, `ui/toast`, `ui/status-indicator`
- No raw `console.*` — `@/lib/debug`
- No API calls that bypass `@/lib/api/client` from presentational `ui/` files
- Match Modern Soft UI: glass sidebars, `rounded-2xl` cards, slate text tokens

## Where to Look

- Feedback patterns: `ui/confirm-dialog.tsx`, `ui/status-indicator.tsx`
- Nav truth (admin): `layout/admin-sidebar.tsx`
- Practice panel: `practice/RightPanelContent.tsx`
