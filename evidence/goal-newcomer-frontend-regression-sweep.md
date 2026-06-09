# Newcomer Training Path Frontend Regression Sweep

## Scope

This evidence records frontend typecheck and Vitest coverage for the newcomer
training path / sales trainer surfaces. It does not replace browser acceptance
for the full publish-governance goal.

## Verification

- `cd web && npx vitest run 'src/app/admin/sales-trainer/paths/page.test.tsx' 'src/lib/sales-trainer/config-center.test.ts' 'src/lib/sales-trainer/admin-display.test.ts'`
  - Result: 3 files passed, 18 tests passed.
- `cd web && npx vitest run 'src/app/admin/sales-trainer/paths/page-audio-bindings.test.tsx' 'src/app/admin/sales-trainer/paths/page-business-bindings.test.tsx' 'src/lib/sales-trainer/config-center-audio-bindings.test.ts'`
  - Result: 3 files passed, 3 tests passed.
- `cd web && npx tsc --noEmit`
  - Result: passed.
- `cd web && find src/app/admin/sales-trainer src/components/admin/sales-trainer src/lib/sales-trainer -name '*.test.ts' -o -name '*.test.tsx' | sort > /tmp/sales-trainer-admin-tests.txt && wc -l /tmp/sales-trainer-admin-tests.txt && xargs npx vitest run < /tmp/sales-trainer-admin-tests.txt`
  - Result: 34 test files passed, 84 tests passed.
- `cd web && find src/app/'(dashboard)'/sales-trainer src/components/sales-trainer src/lib/api src/lib/sales-trainer -name '*.test.ts' -o -name '*.test.tsx' | sort > /tmp/sales-trainer-learner-tests.txt && wc -l /tmp/sales-trainer-learner-tests.txt && xargs npx vitest run < /tmp/sales-trainer-learner-tests.txt`
  - Result: 32 test files passed, 158 tests passed.
- `cd web && npm test`
  - Result: 171 test files passed; 1006 tests passed; 6 skipped.

## Command Correction

`cd web && npm test -- --runInBand` failed because Vitest does not support the
Jest `--runInBand` option. The real project command `cd web && npm test` was
then run and passed.

## File Size Notes

The following existing frontend files remain over the 250 pure-LOC ceiling and
must be split before future behavior edits that add lines:

- `web/src/components/admin/sales-trainer/question-form.tsx`
- `web/src/components/admin/sales-trainer/unit-form.test.tsx`
- `web/src/app/(dashboard)/sales-trainer/page.test.tsx`
- `web/src/app/admin/sales-trainer/score-results/page.tsx`
- `web/src/lib/sales-trainer/config-center.test.ts`
- `web/src/lib/sales-trainer/config-center.ts`
- `web/src/app/(dashboard)/sales-trainer/audio/result/[submissionId]/page.tsx`
- `web/src/app/(dashboard)/sales-trainer/audio/[unitId]/page.tsx`
- `web/src/app/admin/sales-trainer/units/page.tsx`
- `web/src/app/admin/sales-trainer/papers/page.tsx`
