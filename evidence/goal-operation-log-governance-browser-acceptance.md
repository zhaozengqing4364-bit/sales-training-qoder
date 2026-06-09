# Operation Log Governance Browser Acceptance

## Scope

This evidence closes the operation-log browser acceptance item for the
published-governance revision goal. It verifies that the admin operation log
uses business-facing summaries for publish, rollback, revision publish, binding
and high-risk regrade events, while keeping technical metadata behind the
explicit raw-data toggle.

## Browser Target

- `http://localhost:3445/admin/sales-trainer/operation-logs`

## Runtime Checks

Saved browser text evidence:

- `evidence/goal-operation-log-governance-browser.json`

Required visible text:

- `新人训练路径操作日志`
- `集中追踪发布、回滚、绑定变更、历史重评和学员关键操作`
- `路径配置已发布`
- `路径配置已回滚`
- `新人训练路径配置`
- `考卷修订已发布`
- `历史记录已重评`
- `影响范围：只影响后续学员`
- `写入方式：追加重评结果，不覆盖原始记录`
- `追踪号`

Forbidden default-visible technical text:

- `MVP`
- `sales_trainer`
- `module_key`
- `unit_id`
- `paper_key`
- `path_key`
- `raw JSON`

The saved JSON records all required checks as `true` and
`forbiddenVisible: []`.

The saved JSON also records `pathTargetExcerpt`, proving that path publish and
rollback rows now show the target as `新人训练路径配置` instead of the generic
`业务对象`.

## Screenshot

- `evidence/goal-operation-log-governance-browser.png`

## Automated Verification

- `cd web && npx vitest run src/lib/sales-trainer/operation-log-display.test.ts src/app/admin/sales-trainer/operation-logs/page.test.tsx --pool=threads --maxWorkers=1`
  - Evidence: `evidence/goal-operation-log-governance-vitest.txt`
  - Result: 2 files / 3 tests passed.
- `cd web && npx tsc --noEmit`
  - Evidence: `evidence/goal-operation-log-governance-tsc.txt`
  - Result: passed with no output.

## Notes

- The page description no longer exposes the old `MVP` wording.
- Raw diagnostic payloads remain available only after clicking
  `查看原始数据`, which preserves operator visibility without making
  technical fields the default administrator language.
