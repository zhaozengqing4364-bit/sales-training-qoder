# Gate 0C Independent Trellis Check

日期：2026-07-10

模式：独立 agent，只读复核

## 首轮 Finding

### P2：streak 用例混用 runner-local now 与固定 UTC 事件时间

Dashboard greeting 已改为本地日期构造器，但 streak fixture 的 `start_time` /
`report_generated_at` 仍使用临近午夜的固定 UTC 字符串。生产按本地自然日/周计算，
`TZ=America/Los_Angeles` 下记录会跨日，复现为期待 `2/3`、实际计数漂移。

## 修复

- fake now、session start 和 report time 全部由同一 runner-local 2026-04 日历构造；
- API-shaped timestamp 只在构造完成后调用 `.toISOString()`；
- `.trellis/spec/frontend/quality-guidelines.md` 同步固化该合同。

## 最终复核

Findings：P0/P1/P2/P3 全部清零。

验证：

- `TZ=UTC`：Dashboard 24/24 passed；
- `TZ=Asia/Shanghai`：Dashboard 24/24 passed；
- `TZ=America/Los_Angeles`：Dashboard 24/24 passed；
- 聚焦 affected pages：3 files / 50 passed；
- 最终全量：209 files、1327 passed、6 skipped，352.93 秒 / 5:54.32 wall，exit 0；
- TypeScript、改动文件 ESLint、全量 ESLint（0 errors）、architecture guard、diff-check：通过；
- 无新增 skip/only/exclude，无生产合同回退；
- 用户 Readiness 文档保持独立、未暂存。

结论：Gate 0C 可提交并归档。
