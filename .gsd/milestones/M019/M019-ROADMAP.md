# M019: Authority seams 与 release gate 收口

## Vision
把当前“单体部署下的模块化单体”从超大编排文件和隐式运行时修补，收口成可验证的 authority seams：数据库只通过迁移演进，practice backend 与 frontend orchestration 有明确应用层边界，release gate 覆盖真实 web/backend/doc-contract 路径，后续 runtime/AI/product 化工作不再继续堆进 mega files。

## Slice Overview
| ID | Slice | Risk | Depends | Done | After this |
|----|-------|------|---------|------|------------|
| S01 | S01 | high | — | ✅ | After this: 数据库演进、bootstrap、兼容补齐的 authority map 会落到真实迁移/脚本/测试入口，非开发环境不再靠隐式 schema 修补蒙混过关。 |
| S02 | S02 | high | — | ✅ | After this: `practice.py` 不再独自承载会话创建、生命周期、报告、音频审计、runtime descriptor 编排，后续任务可以沿应用层 seam 精准改动。 |
| S03 | S03 | high | — | ⬜ | After this: `client.ts` 按 domain 拆包、`use-practice-websocket.ts` 保留 transport/orchestration outward contract，前端大文件不再是唯一事实源。 |
| S04 | Release gate / metrics / doc-contract truth line 收口 | medium | S01, S02, S03 | ⬜ | After this: GitHub Actions、metrics、前端错误上报和 docs/spec contract 至少有一条真实、可检查的 release truth line，而不是只存在零散文件。 |
