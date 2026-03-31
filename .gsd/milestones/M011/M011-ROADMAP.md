# M011: 

## Vision
把当前 patch 化的知识问答链升级成数据库驱动、可配置、可审计、可调试的后端系统能力；用 Haystack 作为 retrieval/reranking/evaluation 执行底座，同时保留项目自有的控制面、answerability 逻辑与 learner-facing contracts。

## Slice Overview
| ID | Slice | Risk | Depends | Done | After this |
|----|-------|------|---------|------|------------|
| S01 | 引擎 seam 与数据库控制面骨架 | high | — | ⬜ | 可以在代码里实例化新的 KnowledgeAnswerEngine，并从数据库读取一套 active query/ranking/answerability 配置。 |
| S02 | Query understanding、planner 与 Haystack 检索执行 | high | S01 | ⬜ | 给定“请介绍一下世袭科技”这类 query，引擎能输出实体解析、intent、retrieval plan、执行查询列表和排序结果。 |
| S03 | Coverage answerability、answer assembly 与 compatibility seam | medium | S02 | ⬜ | 一次真实问答后，可以从 replay/report/runtime diagnostics 追到同一条 audit run，并看到 answerability/citations。 |
| S04 | 评测、debug API 与 rollout | medium | S03 | ⬜ | 可以查询最近一次知识问答 run 的完整执行轨迹，并通过 eval cases 验证产品介绍类 query 行为。 |
