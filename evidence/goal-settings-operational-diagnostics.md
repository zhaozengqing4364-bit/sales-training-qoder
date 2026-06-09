# Goal Slice Evidence: Settings Operational Diagnostics

Timestamp: 2026-06-04T05:11:44Z

Scope:

- The 新人训练路径 settings page now reads the path-level published config source.
- The diagnostics panel shows the current active path revision, working revision state, latest reason, legacy snapshot count, four module binding health, and recent ASR / AI scoring error codes.
- The page links operators to the configuration center, operation logs, audio submissions, and score results.
- The panel uses business-facing names by default; technical keys remain only inside target URLs and diagnostics mechanics.

Changed files:

- `web/src/lib/sales-trainer/operational-diagnostics.ts`
- `web/src/lib/sales-trainer/operational-diagnostics.test.ts`
- `web/src/app/admin/sales-trainer/settings/page.tsx`
- `web/src/app/admin/sales-trainer/settings/page.test.tsx`
- `web/src/app/admin/sales-trainer/settings/operational-diagnostics-panel.tsx`

Red evidence:

```text
cd web && npx vitest run src/lib/sales-trainer/operational-diagnostics.test.ts src/app/admin/sales-trainer/settings/page.test.tsx --pool=threads --maxWorkers=1
```

The model test first failed because `diagnostics.configuration` was `undefined`.
The page test first failed because `getPathConfig` was not called.

Green evidence:

```text
cd web && npx vitest run src/lib/sales-trainer/operational-diagnostics.test.ts src/app/admin/sales-trainer/settings/page.test.tsx src/lib/sales-trainer/config-center.test.ts src/app/admin/sales-trainer/paths/page.test.tsx --pool=threads --maxWorkers=1
cd web && npx tsc --noEmit
```

Results:

- Focused Vitest: 4 files / 14 tests passed.
- Web typecheck: passed.
- Pure LOC check: all touched files remain under 250 pure LOC.

Browser evidence:

- `evidence/goal-settings-operational-diagnostics.png`
- `evidence/goal-settings-diagnostics-browser.json`

Observed browser text includes:

- `路径配置诊断`
- `路径级发布配置`
- `当前生效版本 v3`
- `legacy 快照记录 16 条`
- `第2关：商务技巧`
- `学习文章和考卷已绑定。`
- `缺少材料版本和录音评分标准。`
- `[DEUCATE_TIMEOUT]`
- `[ASR_PROVIDER_FAILED]`

Artifacts:

- `evidence/goal-settings-diagnostics-vitest.txt`
- `evidence/goal-settings-diagnostics-tsc.txt`
- `evidence/goal-settings-diagnostics-loc.txt`
- `evidence/goal-settings-diagnostics-browser.json`
- `evidence/goal-settings-operational-diagnostics.png`

Remaining goal scope:

- This slice improves the operational diagnostics acceptance path but does not complete the whole goal.
- Remaining browser acceptance still includes AI prompt old/new isolation, broader operation-log publish/rollback/binding proof, and final completion audit.
