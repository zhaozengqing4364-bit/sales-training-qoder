---
estimated_steps: 1
estimated_files: 4
skills_used: []
---

# T01: 抽出 shared drill-in href builder

Inventory the current `focusBucket` / `focusIssueFamily` / `focusNote` URL builders in manager-lite and users list, then create `web/src/lib/admin/drill-in.ts` exporting the shared bucket type, default-note resolution, and href builder. Migrate launcher code to call the helper while preserving the exact query-string shape used today.

## Inputs

- `web/src/components/admin/manager-lite-panel.tsx`
- `web/src/app/admin/users/page.tsx`
- `web/src/components/admin/manager-lite-panel.test.tsx`

## Expected Output

- ``web/src/lib/admin/drill-in.ts` with shared drill-in builders`
- `Manager-lite and users list launch current user-detail URLs through the shared helper`

## Verification

cd web && pnpm dlx npm@11.6.1 test -- --run 'src/components/admin/manager-lite-panel.test.tsx'
