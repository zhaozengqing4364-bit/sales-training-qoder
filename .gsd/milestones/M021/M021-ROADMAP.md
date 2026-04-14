# M021: AI control plane / prompt / evaluation kernel 统一

## Vision
把当前分散在 StepFun realtime handler、legacy evaluation/report、PromptTemplateService、persona policy、voice instruction、knowledge-answer 双轨路径上的 AI 控制平面和评估事实线统一起来：先确认 live authority，再让 prompt compilation、评分内核、质量/成本事件和知识问答都读同一套 truth line。

## Slice Overview
| ID | Slice | Risk | Depends | Done | After this |
|----|-------|------|---------|------|------------|
| S01 | S01 | high | — | ✅ | After this: 项目中每条 AI/runtime/prompt/score/report 路径都有 live/compat/shadow/retire 标签，后续统一工作不会再基于误判开刀。 |
| S02 | S02 | high | — | ✅ | After this: prompt template、voice instruction、persona policy、runtime guardrail 不再各走各路，至少有一条 compiled prompt contract 真正驱动 live/legacy 路径。 |
| S03 | S03 | high | — | ⬜ | After this: realtime、report、history、admin、replay 至少共享一套 canonical sales/presentation evaluation kernel，旧读者通过 compatibility readers 过渡。 |
| S04 | AI quality/cost/failure events 与 knowledge path 收口 | medium | S02, S03 | ⬜ | After this: AI 失败、降级、成本、知识问答路径会以显式质量事件落盘/出现在诊断面，默认分数和默认文案不再掩盖问题。 |
