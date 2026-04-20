---
estimated_steps: 3
estimated_files: 5
skills_used: []
---

# T01: 盘点 live/compat/shadow AI 路径

- 沿 `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`、`evaluation/services/*`、`prompt_templates/*`、`common/ai/*`、knowledge-answer 路径盘点 live/compat/shadow responsibilities。
- 对每条路径记录：入口、调用者、输出消费者、是否当前真实在线。
- 把 inventory 写入 architecture scan 和 milestone context。

## Inputs

- `stepfun handler`
- `evaluation services`
- `prompt templates`
- `knowledge-answer paths`

## Expected Output

- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`
- `.gsd/milestones/M021/M021-CONTEXT.md`

## Verification

rg -n "PromptTemplateService|generate_report|evaluate\(|stepfun|knowledge_answer|voice_instruction|compiled" backend/src/sales_bot backend/src/evaluation backend/src/prompt_templates backend/src/common backend/src/presentation_coach
