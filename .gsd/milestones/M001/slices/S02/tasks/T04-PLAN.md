---
estimated_steps: 4
estimated_files: 7
---

# T04: 收口报告/回放/历史页面的统一消费面

**Slice:** S02 — 训练证据落库与报告事实源统一
**Milestone:** M001

## Description

后端统一之后，前端还需要停止“把多个接口拼成一个事实”。这个任务只做消费面收口：report/replay/history 页面信任统一 evidence contract，把 comprehensive report 降为增强内容，把本地补分和跨接口拼接降到最小。完成后，用户在三个页面看到的是同一条事实线，而不是看起来接近的三份数据。

## Steps

1. 更新 `web/src/lib/api/types.ts` 中与 report / replay / history 相关的类型，表达统一 evidence 字段（overall score、evaluable、not_evaluable_reason、stage summary、evidence completeness 等）。
2. 调整 report、replay、history 三个页面的取数与展示逻辑：优先消费统一 evidence contract，保留 comprehensive report 作为增强内容，但不再拿它当唯一真相或在客户端重算 overall。
3. 为三个页面新增 focused tests，覆盖统一 overall score 展示、不可评估提示、无高光/无综合报告时的稳定退化，以及 replay/history 不再从多接口拼接冲突分数。
4. 运行 focused vitest，确保前端消费面已经和后端统一边界对齐。

## Must-Haves

- [ ] 报告页、回放页、历史页不再各自本地重算 overall score，也不再通过多接口回退拼接出另一套事实。
- [ ] comprehensive report 仍可作为增强视图存在，但缺失它时页面依旧能基于统一 evidence contract 给出稳定结果和明确降级提示。

## Verification

- `cd web && npm test -- --run src/app/(user)/practice/[sessionId]/report/page.test.tsx src/app/(user)/practice/[sessionId]/replay/page.test.tsx src/app/(dashboard)/history/page.test.tsx`
- 额外断言：三页对同一 session 展示的 overall score / 不可评估提示与后端统一 contract 一致。

## Observability Impact

- Signals added/changed: 页面调试日志与错误态要能区分“统一 evidence contract 获取失败”“enhanced/comprehensive 内容缺失但基础 evidence 可用”。
- How a future agent inspects this: 看 page-level tests 与页面错误/降级 UI，即可判断是 API contract 变了，还是页面又开始自行拼接事实。
- Failure state exposed: 综合报告缺失、highlights 缺失、无证据 session 三种情况的 UI 表达必须彼此区分，不能都塌成一个泛化报错。

## Inputs

- `web/src/app/(user)/practice/[sessionId]/report/page.tsx` / `web/src/app/(user)/practice/[sessionId]/replay/page.tsx` / `web/src/app/(dashboard)/history/page.tsx` — 当前仍存在多接口并行拉取与客户端补分逻辑。
- `web/src/lib/api/types.ts` — 前端统一 contract 的第一落点。
- T02 / T03 提供的统一 evidence API shape — 页面只能消费这一条事实线，不能再自行创造第四条。

## Expected Output

- `web/src/lib/api/types.ts` — 明确表达统一 report/replay/history evidence contract。
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx` / `web/src/app/(user)/practice/[sessionId]/replay/page.tsx` / `web/src/app/(dashboard)/history/page.tsx` — 页面改为信任统一 evidence source。
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx` / `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx` / `web/src/app/(dashboard)/history/page.test.tsx` — 前端统一消费面的回归保护。
