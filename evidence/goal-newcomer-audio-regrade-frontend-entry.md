# 新人训练路径录音历史重评前端入口证据

时间：2026-06-04T03:46:24Z

## 目标切片

把后端 `audio_submission` 历史重评能力接到管理端录音详情页：

- 管理员在录音详情页能看到“重新评分历史记录”入口。
- 点击“预览重评影响”调用 audio submission regrade preview endpoint。
- 填写原因后点击“确认重评”调用 audio submission regrade run endpoint。
- 页面文案明确“只追加重评记录，不覆盖原始录音评分和转写快照”。
- `retry-scoring` 继续作为失败任务重试，不被混同为历史重评。

## 红测

命令：

```bash
cd web && npx vitest run src/lib/api/client-domains.test.ts --pool=threads --maxWorkers=1
```

首次结果：失败，`adminSalesTrainer.previewAudioSubmissionRegrade is not a function`。

## 实现

新增 / 修改：

- `web/src/components/admin/sales-trainer/audio-submission-regrade-panel.tsx`
- `web/src/app/admin/sales-trainer/audio-submissions/[submissionId]/page.tsx`
- `web/src/app/admin/sales-trainer/audio-submissions/[submissionId]/page.test.tsx`
- `web/src/lib/api/client-domains.ts`
- `web/src/lib/api/client-domains.test.ts`
- `web/src/lib/api/types.ts`

## 验证

API domain factory：

```bash
cd web && npx vitest run src/lib/api/client-domains.test.ts --pool=threads --maxWorkers=1
```

结果：6 tests passed。

录音详情页 + API facade + quiz regrade 防回归：

```bash
cd web && npx vitest run src/lib/api/sales-trainer.test.ts 'src/app/admin/sales-trainer/quiz-attempts/[attemptId]/page.test.tsx' 'src/app/admin/sales-trainer/audio-submissions/[submissionId]/page.test.tsx' src/lib/api/client-domains.test.ts --pool=threads --maxWorkers=1
```

结果：4 files passed，23 tests passed。

类型检查：

```bash
cd web && npx tsc --noEmit
```

结果：通过，无错误输出。

## LOC 约束

纯 LOC：

- `web/src/components/admin/sales-trainer/audio-submission-regrade-panel.tsx`: 168
- `web/src/app/admin/sales-trainer/audio-submissions/[submissionId]/page.tsx`: 196
- `web/src/app/admin/sales-trainer/audio-submissions/[submissionId]/page.test.tsx`: 190
- `web/src/lib/api/client-domains.test.ts`: 129

## 剩余范围

本切片补齐管理端录音重评入口和 facade 方法。浏览器验收中“旧 prompt 可解释、新 prompt 生效”的真实页面证据仍需继续补。
