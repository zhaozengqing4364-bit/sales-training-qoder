# Effectiveness / Rubric 契约

> 状态: ⚠️ authority contract 已定义（M022/S01/T01），runtime/read-side 全面接线由 T02 完成
>
> 代码 authority: `backend/src/common/effectiveness/methodology.py`
>
> 相关 runtime surfaces: `backend/src/agent/capabilities/realtime_scoring.py`, `backend/src/common/conversation/session_evidence.py`, `backend/src/admin/api/interventions.py`

## 目标

把销售训练从“只有 `dimension_scores`、`main_issue`、`next_goal` 的通用规则层”推进到**方法论 aware 的 rubric contract**，但不在第一轮破坏现有外部 score schema。

第一轮 contract 的原则：

- **additive, not replacement**：继续保留 `logic_score / accuracy_score / completeness_score / overall_score` 与现有 `dimension_scores`。
- **canonical-first**：方法论语义以 `canonical_evaluation_kernel.dimensions[]` 为主锚点，不另造第二套 truth source。
- **report/read-side compatible**：报告、history、admin 继续沿用 `effectiveness_snapshot.main_issue`、`effectiveness_snapshot.next_goal`、`claim_truth`。
- **stage-aware but boundary-honest**：当前 `sales_stage` 仍是 `opening / discovery / presentation / objection / closing`；首轮把 qualification 显式并入 `opening + discovery`，不假装已经有独立 qualification stage。

## Contract 标识

```json
{
  "contract_id": "sales_methodology_rubric_v1",
  "scenario_type": "sales",
  "canonical_kernel_version": "evaluation_kernel_v1"
}
```

## 首轮 rubric 维度

| rubric_id | 方法论概念 | 主要 sales_stage | canonical dimension | 低分缺口映射 | 下一轮目标映射 |
|---|---|---|---|---|---|
| `discovery_qualification` | 先确认现状、目标、优先级和决策线索，再讲方案 | `opening`, `discovery` | `customer_benefit_connection`, `value_expression` | `main_issue.issue_type = value_translation_gap` | `next_goal.goal_type = value_to_benefit_translation` |
| `value_story` | 持续把产品能力翻译成客户收益，而不是功能堆砌 | `discovery`, `presentation` | `value_expression` | `value_translation_gap` | `value_to_benefit_translation` |
| `evidence_proof` | 价值主张必须有案例、数据、ROI 或 benchmark 支撑 | `presentation`, `objection`, `closing` | `evidence_usage` | `evidence_gap` | `evidence_backing` |
| `objection_reframe` | 顾虑出现后先承接再重构，用收益和证据回应 | `objection`, `closing` | `objection_handling`, `evidence_usage` | `objection_handling_gap` | `objection_reframe` |
| `next_step_commitment` | 每轮结束都要形成动作、时间点和责任人 | `closing` | `next_step_commitment` | `next_step_gap` | `next_step_commitment` |

### Qualification boundary（首轮边界）

当前 shipped `sales_stage` 还没有单独的 `qualification` stage，所以第一轮 contract 明确规定：

- qualification 信号仍沿 `opening` / `discovery` surface 读取；
- 相关证据表现为客户现状、目标、预算、负责人、优先级等探查语言；
- 如果后续 `sales_stage` 拆出独立 `qualification`，该变更必须同步更新 code contract、本文件、以及 report/read-side proof。

## 对用户与管理面如何解释

### Learner-facing（报告页 / 练习页）

报告页面向学员时，应该把本轮销售对话解释为五个固定 rubric 视角，而不是只说“总分高/低”：

- `discovery / qualification`：有没有先问清现状、目标、优先级、决策线索；
- `value`：有没有把产品能力翻译成客户收益，而不是只讲功能；
- `evidence`：价值主张有没有案例、数据、ROI、benchmark 支撑；
- `objection`：客户顾虑出现后，是否先承接再重构；
- `next-step`：有没有收束成动作、时间点、责任人。

对 learner 的 copy 要保持两条原则：

1. 把 `main_issue` 解释成“这次最主要的 rubric 缺口”；
2. 把 `next_goal` 解释成“下一轮最优先补强的方法论动作”。

但 learner-facing copy 不能暗示首轮已经覆盖完整销售方法论，也不能说系统已经有独立 `qualification` rubric / stage。

### Manager-facing（history / admin / coaching）

manager 读侧当前也消费同一条 read-side truth line，因此管理面说明必须遵守：

- 先看 `canonical_evaluation_kernel.dimensions[]` 定位命中/缺口来自哪类 evidence；
- 再用 `effectiveness_snapshot.main_issue`、`next_goal`、`claim_truth` 解释 coaching 重点；
- `healthy / watch / coach` 只表示当前证据校准状态，不表示系统已经提供完整的方法论认证或团队级 benchmark。

换句话说：manager 面拿到的是**基于 canonical evidence 的方法论解释层**，不是第二套 manager-only 评分器。

## 可观察证据定位

### Realtime

| surface | primary reader | evidence path |
|---|---|---|
| `realtime` | `sales_realtime_score_snapshot_v1` | `canonical_evaluation_kernel.dimensions[]` |
| `realtime` | `sales_realtime_score_snapshot_v1` | `compatibility_readers.sales_realtime_score_snapshot_v1.dimension_scores` |
| `realtime` | runtime feedback payload | `dimensions[]` |

### Report / Replay / Read-side

| surface | primary reader | evidence path |
|---|---|---|
| `report` | `session_evidence_projection_v1` | `canonical_evaluation_kernel.dimensions[]` |
| `report` | `session_evidence_projection_v1` | `effectiveness_snapshot.main_issue` |
| `report` | `session_evidence_projection_v1` | `effectiveness_snapshot.next_goal` |
| `report` | `session_evidence_projection_v1` | `effectiveness_snapshot.claim_truth` |
| `history` | `session_evidence_projection_v1` | `feedback_summary`, `effectiveness_snapshot.main_issue`, `effectiveness_snapshot.next_goal` |
| `admin` | `session_evidence_projection_v1` | `effectiveness_snapshot.main_issue`, `effectiveness_snapshot.next_goal`, `effectiveness_snapshot.claim_truth` |

> Manager coaching 目前不是单独评分器；当前 manager 读侧实际由 `history`、`admin` 和 `/api/v1/admin/interventions/*` 消费这同一条 read-side truth line。

## Compatibility 约束

第一轮不新增新的顶层 score 字段，兼容方式固定为：

- `practice_session_rollup_fields_v1`：保留 `logic_score / accuracy_score / completeness_score / overall_score`
- `sales_realtime_score_snapshot_v1`：保留 `overall_score + dimension_scores`
- `effectiveness_snapshot_v1`：继续返回 `main_issue`、`next_goal`、`claim_truth`
- `comprehensive_sales_report_v1`：仍可读兼容 `dimension_scores`

也就是说：**方法论 contract 解释当前 score schema，但不取代当前 score schema。**

## 校准语义

每个 rubric 维度都只有三种校准状态：

- `healthy`: 分数高于该 rubric 的 `healthy_min`，可以保持当前方法论动作
- `watch`: 低于 `healthy_min` 但高于 `watch_min`，说明证据或话术还不稳定
- `coach`: 低于 `watch_min`，应直接映射到 `main_issue` / `next_goal` 的补救动作

首轮 contract 不把校准结果单独落库；T02 接线时仍应以 canonical evidence + `main_issue` / `next_goal` 的组合来解释校准结论。

## 示例片段

```json
{
  "sales_stage": "objection",
  "canonical_evaluation_kernel": {
    "scenario_type": "sales",
    "dimensions": [
      {"dimension_id": "evidence_usage", "label": "证据使用", "score": 58},
      {"dimension_id": "objection_handling", "label": "异议处理", "score": 54}
    ]
  },
  "compatibility_readers": {
    "sales_realtime_score_snapshot_v1": {
      "overall_score": 68,
      "dimension_scores": {
        "证据使用": 58,
        "异议处理": 54
      }
    }
  },
  "effectiveness_snapshot": {
    "main_issue": {
      "issue_type": "objection_handling_gap"
    },
    "next_goal": {
      "goal_type": "objection_reframe"
    }
  }
}
```

这表示当前会话命中了 `objection_reframe` rubric 的缺口，而不是只剩一个模糊低分。

## 后续规则

- T02 接线时必须直接复用 `backend/src/common/effectiveness/methodology.py` 的 contract，不要在 realtime、report、history、admin 各自复制一份方法论解释。
- 如果后续新增 rubric / stage / manager surface，必须同时更新：
  - `backend/src/common/effectiveness/methodology.py`
  - 本文件
  - focused tests
  - `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`
