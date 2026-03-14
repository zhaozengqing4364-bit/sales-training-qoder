# Communication Training 80/20 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a lightweight closed-loop communication training system that delivers practical 80% effectiveness for role-based customer conversations.

**Architecture:** Keep existing session lifecycle and WebSocket pipeline, add a minimal effectiveness snapshot at session end, add single action-card realtime feedback per turn, and expose only four trustworthy core metrics. Extend report and admin surfaces without introducing a new heavy workflow engine.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy, Alembic, Next.js 16, TypeScript, WebSocket

---

### Task 1: Add Effectiveness Snapshot Persistence

**Files:**
- Create: `backend/alembic/versions/20260221_2000_016_add_effectiveness_snapshot.py`
- Modify: `backend/src/common/db/models.py`
- Modify: `backend/src/common/db/schemas.py`
- Test: `backend/tests/unit/common/test_effectiveness_snapshot_schema.py`

**Step 1: Write the failing test**

```python
from common.db.schemas import PracticeSessionResponse


def test_practice_session_response_accepts_effectiveness_snapshot():
    payload = {
        "session_id": "s1",
        "scenario_id": "sc1",
        "status": "completed",
        "effectiveness_snapshot": {
            "pass_flags": {
                "pass_3min_flow": True,
                "pass_5turn_defense": False,
                "pass_4step_structure": True,
            },
            "version": "rule_v1",
            "evaluable": True,
        },
    }
    obj = PracticeSessionResponse.model_validate(payload)
    assert obj.effectiveness_snapshot["version"] == "rule_v1"
```

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/unit/common/test_effectiveness_snapshot_schema.py::test_practice_session_response_accepts_effectiveness_snapshot -v`
Expected: FAIL with schema field missing.

**Step 3: Write minimal implementation**

```python
# in PracticeSession SQLAlchemy model
effectiveness_snapshot = Column(JSON, nullable=True)

# in PracticeSessionResponse Pydantic schema
effectiveness_snapshot: dict | None = None
```

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/unit/common/test_effectiveness_snapshot_schema.py::test_practice_session_response_accepts_effectiveness_snapshot -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/alembic/versions/20260221_2000_016_add_effectiveness_snapshot.py \
  backend/src/common/db/models.py backend/src/common/db/schemas.py \
  backend/tests/unit/common/test_effectiveness_snapshot_schema.py
git commit -m "feat: persist effectiveness snapshot on practice sessions"
```

### Task 2: Implement Effectiveness Rule Evaluator

**Files:**
- Create: `backend/src/common/effectiveness/evaluator.py`
- Create: `backend/src/common/effectiveness/schemas.py`
- Test: `backend/tests/unit/common/test_effectiveness_evaluator.py`

**Step 1: Write the failing test**

```python
from common.effectiveness.evaluator import evaluate_session


def test_pass_when_main_capability_and_two_flags_true():
    result = evaluate_session(
        main_capability_passed=True,
        metrics={
            "continuous_speech_seconds": 200,
            "offtopic_turn_count": 1,
            "offtopic_max_streak": 1,
            "structure_coverage": 0.75,
        },
    )
    assert result["overall_result"] == "pass"
```

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/unit/common/test_effectiveness_evaluator.py::test_pass_when_main_capability_and_two_flags_true -v`
Expected: FAIL with module/function missing.

**Step 3: Write minimal implementation**

```python
def evaluate_session(main_capability_passed: bool, metrics: dict) -> dict:
    pass_3min_flow = metrics.get("continuous_speech_seconds", 0) >= 180
    pass_5turn_defense = (
        metrics.get("offtopic_turn_count", 99) <= 1
        and metrics.get("offtopic_max_streak", 99) < 2
    )
    pass_4step_structure = metrics.get("structure_coverage", 0) >= 0.75

    pass_flags = {
        "pass_3min_flow": pass_3min_flow,
        "pass_5turn_defense": pass_5turn_defense,
        "pass_4step_structure": pass_4step_structure,
    }
    passed_count = sum(1 for v in pass_flags.values() if v)

    if not main_capability_passed:
        overall = "fail"
    elif passed_count == 3:
        overall = "strong_pass"
    elif passed_count >= 2:
        overall = "pass"
    else:
        overall = "fail"

    return {
        "pass_flags": pass_flags,
        "main_capability_passed": main_capability_passed,
        "overall_result": overall,
        "version": "rule_v1",
        "evaluable": True,
    }
```

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/unit/common/test_effectiveness_evaluator.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/common/effectiveness/evaluator.py backend/src/common/effectiveness/schemas.py \
  backend/tests/unit/common/test_effectiveness_evaluator.py
git commit -m "feat: add rule-v1 effectiveness evaluator"
```

### Task 3: Save Snapshot at Session End in Practice Flow

**Files:**
- Modify: `backend/src/common/api/practice.py`
- Modify: `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
- Test: `backend/tests/integration/test_session_flow.py`

**Step 1: Write the failing test**

```python
async def test_end_session_persists_effectiveness_snapshot(client, session_factory):
    session = await session_factory(status="in_progress")
    resp = await client.post(f"/api/v1/practice/sessions/{session.session_id}/lifecycle", json={"action": "end"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "effectiveness_snapshot" in data
```

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/integration/test_session_flow.py::test_end_session_persists_effectiveness_snapshot -v`
Expected: FAIL with missing field or null snapshot.

**Step 3: Write minimal implementation**

```python
# on lifecycle end
snapshot = evaluate_session(
    main_capability_passed=calculated_main_capability_passed,
    metrics=derived_metrics,
)
session.effectiveness_snapshot = snapshot
```

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/integration/test_session_flow.py::test_end_session_persists_effectiveness_snapshot -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/common/api/practice.py backend/src/sales_bot/websocket/stepfun_realtime_handler.py \
  backend/tests/integration/test_session_flow.py
git commit -m "feat: persist effectiveness snapshot during session end"
```

### Task 4: Emit Single ActionCard per Turn via WebSocket

**Files:**
- Modify: `backend/src/sales_bot/websocket/components/capability_processor.py`
- Modify: `backend/src/sales_bot/websocket/components/stepfun_message_helpers.py`
- Modify: `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
- Test: `backend/tests/unit/test_stepfun_realtime_handler.py`

**Step 1: Write the failing test**

```python
async def test_emits_action_card_message_for_turn(handler):
    await handler._emit_action_card(
        issue="需求问题过泛",
        replacement="请问您当前最想优先解决的一个问题是什么？",
        next_turn_rule="下一轮先问1个具体业务问题再给建议",
    )
    sent = handler.websocket.send_json.call_args_list
    assert any(call.args[0]["type"] == "action_card" for call in sent)
```

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/unit/test_stepfun_realtime_handler.py::test_emits_action_card_message_for_turn -v`
Expected: FAIL with method/message missing.

**Step 3: Write minimal implementation**

```python
await self._send_json({
    "type": "action_card",
    "data": {
        "issue": issue,
        "replacement": replacement,
        "next_turn_rule": next_turn_rule,
    },
})
```

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/unit/test_stepfun_realtime_handler.py::test_emits_action_card_message_for_turn -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/sales_bot/websocket/components/capability_processor.py \
  backend/src/sales_bot/websocket/components/stepfun_message_helpers.py \
  backend/src/sales_bot/websocket/stepfun_realtime_handler.py \
  backend/tests/unit/test_stepfun_realtime_handler.py
git commit -m "feat: emit single action-card websocket feedback"
```

### Task 5: Handle ActionCard in Frontend WebSocket State

**Files:**
- Modify: `web/src/hooks/websocket/types.ts`
- Modify: `web/src/hooks/websocket/message-handlers.ts`
- Test: `web/src/hooks/websocket/message-handlers.test.ts`

**Step 1: Write the failing test**

```typescript
it("stores latest action card when action_card arrives", () => {
  const message = {
    type: "action_card",
    data: {
      issue: "跑题",
      replacement: "先确认客户当前最关心的结果",
      next_turn_rule: "下一轮先复述需求再回答",
    },
  }

  handleWebSocketMessage(makeEvent(message), deps)
  expect(getState().actionCard?.issue).toBe("跑题")
})
```

**Step 2: Run test to verify it fails**

Run: `pnpm test web/src/hooks/websocket/message-handlers.test.ts -t "stores latest action card"`
Expected: FAIL because `action_card` not recognized.

**Step 3: Write minimal implementation**

```typescript
// types.ts
export interface ActionCard {
  issue: string
  replacement: string
  next_turn_rule: string
}

// PracticeState
actionCard: ActionCard | null

// message-handlers.ts
case "action_card": {
  const data = message.data as ActionCard
  setState((prev) => ({ ...prev, actionCard: data }))
  break
}
```

**Step 4: Run test to verify it passes**

Run: `pnpm test web/src/hooks/websocket/message-handlers.test.ts -t "stores latest action card"`
Expected: PASS

**Step 5: Commit**

```bash
git add web/src/hooks/websocket/types.ts web/src/hooks/websocket/message-handlers.ts \
  web/src/hooks/websocket/message-handlers.test.ts
git commit -m "feat: support action-card state in websocket frontend"
```

### Task 6: Render ActionCard in Practice Right Panel

**Files:**
- Modify: `web/src/components/practice/RightPanelContent.tsx`
- Modify: `web/src/app/(user)/practice/[sessionId]/page.tsx`
- Test: `web/src/components/practice/__tests__/RightPanelContent.test.tsx`

**Step 1: Write the failing test**

```tsx
it("renders single action card with issue replacement and rule", () => {
  render(
    <RightPanelContent
      scenarioType="sales"
      actionCard={{
        issue: "问题过泛",
        replacement: "您最希望本季度先改善哪项指标？",
        next_turn_rule: "下一轮先提1个具体问题",
      }}
      // ...other required props
    />
  )

  expect(screen.getByText("问题过泛")).toBeInTheDocument()
  expect(screen.getByText("您最希望本季度先改善哪项指标？")).toBeInTheDocument()
})
```

**Step 2: Run test to verify it fails**

Run: `pnpm test web/src/components/practice/__tests__/RightPanelContent.test.tsx -t "renders single action card"`
Expected: FAIL with prop/UI missing.

**Step 3: Write minimal implementation**

```tsx
{actionCard && (
  <div>
    <h3>本轮唯一动作</h3>
    <p>{actionCard.issue}</p>
    <p>{actionCard.replacement}</p>
    <p>{actionCard.next_turn_rule}</p>
  </div>
)}
```

**Step 4: Run test to verify it passes**

Run: `pnpm test web/src/components/practice/__tests__/RightPanelContent.test.tsx -t "renders single action card"`
Expected: PASS

**Step 5: Commit**

```bash
git add web/src/components/practice/RightPanelContent.tsx \
  web/src/app/(user)/practice/[sessionId]/page.tsx \
  web/src/components/practice/__tests__/RightPanelContent.test.tsx
git commit -m "feat: show single action-card in practice panel"
```

### Task 7: Extend Report API and Report Page for Retry Loop

**Files:**
- Modify: `backend/src/common/api/practice.py`
- Modify: `web/src/lib/api/types.ts`
- Modify: `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
- Test: `backend/tests/integration/test_session_flow.py`
- Test: `web/src/app/(user)/practice/[sessionId]/__tests__/report.page.test.tsx`

**Step 1: Write the failing test**

```python
async def test_report_contains_next_goal_and_retry_entry(client, completed_session):
    resp = await client.get(f"/api/v1/practice/sessions/{completed_session.session_id}/report")
    data = resp.json()["data"]
    assert "next_goal" in data
    assert "retry_entry" in data
```

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/integration/test_session_flow.py::test_report_contains_next_goal_and_retry_entry -v`
Expected: FAIL with missing fields.

**Step 3: Write minimal implementation**

```python
return {
    ...existing_report,
    "pass_flags": snapshot.get("pass_flags", {}),
    "next_goal": snapshot.get("next_goal"),
    "retry_entry": {
        "scenario_type": session.scenario_type,
        "agent_id": session.agent_id,
        "persona_id": session.persona_id,
    },
}
```

```tsx
<Button onClick={handleRetryFromReport}>按目标再练一轮</Button>
```

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/integration/test_session_flow.py::test_report_contains_next_goal_and_retry_entry -v`
Expected: PASS

Run: `pnpm test web/src/app/(user)/practice/[sessionId]/__tests__/report.page.test.tsx -t "retry"`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/common/api/practice.py web/src/lib/api/types.ts \
  web/src/app/(user)/practice/[sessionId]/report/page.tsx \
  backend/tests/integration/test_session_flow.py \
  web/src/app/(user)/practice/[sessionId]/__tests__/report.page.test.tsx
git commit -m "feat: add report next-goal and one-click retry loop"
```

### Task 8: Replace Placeholder Metrics with Four Core Metrics

**Files:**
- Modify: `backend/src/common/analytics/analytics_service.py`
- Modify: `backend/src/common/api/analytics.py`
- Modify: `backend/src/common/api/dashboard.py`
- Test: `backend/tests/unit/common/test_analytics_service_core_metrics.py`

**Step 1: Write the failing test**

```python
async def test_dashboard_returns_four_core_effectiveness_metrics(db_session):
    result = await analytics_service.get_dashboard_stats(db_session, scenario_type="sales", days=30)
    stats = result.value
    assert hasattr(stats, "pass_rate_3min_flow")
    assert hasattr(stats, "pass_rate_5turn_defense")
    assert hasattr(stats, "pass_rate_4step_structure")
    assert hasattr(stats, "next_day_retry_rate")
```

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/unit/common/test_analytics_service_core_metrics.py::test_dashboard_returns_four_core_effectiveness_metrics -v`
Expected: FAIL with missing fields.

**Step 3: Write minimal implementation**

```python
# compute from PracticeSession.effectiveness_snapshot only
pass_rate_3min_flow = ...
pass_rate_5turn_defense = ...
pass_rate_4step_structure = ...
next_day_retry_rate = ...
```

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/unit/common/test_analytics_service_core_metrics.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/common/analytics/analytics_service.py backend/src/common/api/analytics.py \
  backend/src/common/api/dashboard.py backend/tests/unit/common/test_analytics_service_core_metrics.py
git commit -m "feat: expose four core effectiveness metrics from real snapshots"
```

### Task 9: Add Manager Lite Intervention Endpoints

**Files:**
- Create: `backend/src/admin/api/interventions.py`
- Modify: `backend/src/main.py`
- Test: `backend/tests/integration/test_admin_interventions_api.py`

**Step 1: Write the failing test**

```python
async def test_admin_can_fetch_manager_lite_lists(admin_client):
    resp = await admin_client.get("/api/v1/admin/interventions/lists")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "not_passed" in data
    assert "inactive_streak" in data
    assert "improving" in data
```

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/integration/test_admin_interventions_api.py::test_admin_can_fetch_manager_lite_lists -v`
Expected: FAIL with route not found.

**Step 3: Write minimal implementation**

```python
@router.get("/admin/interventions/lists")
async def get_lists(...):
    return success_response({
        "not_passed": [...],
        "inactive_streak": [...],
        "improving": [...],
    })

@router.post("/admin/interventions/remind")
async def remind(...):
    # phase-1: persist reminder log only
    return success_response({"sent": True})
```

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/integration/test_admin_interventions_api.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/admin/api/interventions.py backend/src/main.py \
  backend/tests/integration/test_admin_interventions_api.py
git commit -m "feat: add manager-lite intervention endpoints"
```

### Task 10: Add Minimal Manager Lite Frontend Panel

**Files:**
- Create: `web/src/components/admin/manager-lite-panel.tsx`
- Modify: `web/src/app/admin/analytics/page.tsx`
- Modify: `web/src/lib/api/client.ts`
- Modify: `web/src/lib/api/types.ts`
- Test: `web/src/components/admin/__tests__/manager-lite-panel.test.tsx`

**Step 1: Write the failing test**

```tsx
it("renders three manager-lite lists", async () => {
  render(<ManagerLitePanel data={mockData} onRemind={vi.fn()} />)
  expect(screen.getByText("未达标名单")).toBeInTheDocument()
  expect(screen.getByText("连续未练名单")).toBeInTheDocument()
  expect(screen.getByText("达标上升名单")).toBeInTheDocument()
})
```

**Step 2: Run test to verify it fails**

Run: `pnpm test web/src/components/admin/__tests__/manager-lite-panel.test.tsx -t "renders three manager-lite lists"`
Expected: FAIL with component missing.

**Step 3: Write minimal implementation**

```tsx
export function ManagerLitePanel({ data, onRemind }: Props) {
  return (
    <div>
      <section>未达标名单</section>
      <section>连续未练名单</section>
      <section>达标上升名单</section>
      <button onClick={() => onRemind(data.not_passed[0]?.user_id)}>一键提醒</button>
    </div>
  )
}
```

**Step 4: Run test to verify it passes**

Run: `pnpm test web/src/components/admin/__tests__/manager-lite-panel.test.tsx -v`
Expected: PASS

**Step 5: Commit**

```bash
git add web/src/components/admin/manager-lite-panel.tsx web/src/app/admin/analytics/page.tsx \
  web/src/lib/api/client.ts web/src/lib/api/types.ts \
  web/src/components/admin/__tests__/manager-lite-panel.test.tsx
git commit -m "feat: add manager-lite panel with one-click reminder"
```

### Task 11: Contract/Regression Safety Pass

**Files:**
- Modify: `docs/api-contract/websocket.md`
- Modify: `docs/api-contract/sessions.md`
- Modify: `docs/api-contract/analytics.md`
- Test: `backend/tests/integration/test_voice_runtime_api_contract.py`

**Step 1: Write the failing test**

```python
async def test_action_card_contract_shape(ws_client):
    msg = await ws_client.recv_json()
    if msg["type"] == "action_card":
        assert set(msg["data"].keys()) == {"issue", "replacement", "next_turn_rule"}
```

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/integration/test_voice_runtime_api_contract.py::test_action_card_contract_shape -v`
Expected: FAIL if contract undocumented or shape mismatch.

**Step 3: Write minimal implementation**

```md
# add action_card message contract and report new fields
```

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/integration/test_voice_runtime_api_contract.py::test_action_card_contract_shape -v`
Expected: PASS

**Step 5: Commit**

```bash
git add docs/api-contract/websocket.md docs/api-contract/sessions.md docs/api-contract/analytics.md \
  backend/tests/integration/test_voice_runtime_api_contract.py
git commit -m "docs: update contracts for action-card and effectiveness metrics"
```

## Implementation Guardrails

- Use `@superpowers/systematic-debugging` if realtime behavior diverges from expected state transitions.
- Keep single source of truth for pass/fail in `effectiveness_snapshot`.
- Reject non-evaluable sessions from core metric denominator.
- Keep ActionCard strictly one-per-turn.

## Verification Checklist

- Backend unit tests for evaluator and metric calculator pass.
- Integration tests confirm snapshot persistence and report expansion.
- Frontend tests confirm ActionCard rendering and report retry CTA behavior.
- API contracts include new message type and response fields.
- No placeholder/estimated values remain in core metrics endpoints.
