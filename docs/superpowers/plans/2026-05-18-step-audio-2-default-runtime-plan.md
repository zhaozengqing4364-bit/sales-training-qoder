# Step Audio 2 Default Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 确保销售训练 Realtime 主链最终默认使用 StepFun `step-audio-2`，即使数据库里已有默认 `voice_runtime_profiles` 也不会被历史 `step-audio-r1.1` 默认值覆盖。

**Architecture:** 保持现有架构不变：浏览器仍连接本项目后端 WebSocket，后端 `StepFunRealtimeHandler` 继续连接 `wss://api.stepfun.com/v1/realtime?model=<model>`。本次只修正数据库迁移链与测试，让 DB 默认 runtime profile、SQL server default、env fallback 三处都对齐 `step-audio-2`。

**Tech Stack:** Python 3.11、FastAPI、SQLAlchemy 2.0 async、Alembic、pytest、StepFun Realtime WebSocket。

---

## File Structure

- Create: `backend/alembic/versions/20260518_0900_067_stepfun_default_model_audio2.py`
  - 只负责把历史默认 realtime profile 从 `step-audio-r1.1` 修正回 `step-audio-2`，并把 `voice_runtime_profiles.model_name` 的 `server_default` 改回 `step-audio-2`。
- Modify: `backend/tests/unit/test_voice_runtime_policy_service.py`
  - 增加一个回归测试，证明当数据库默认 profile 是 `step-audio-2` 时，`resolve_effective_policy()` 最终选择 `step-audio-2`，并且不会依赖 `STEPFUN_REALTIME_MODEL` 环境变量。
- Modify: `backend/.env.example`
  - 清理模型候选注释，把 `step-audio-2` 明确为默认推荐，避免 `step-audio-r1.1` 继续误导部署配置。
- Optional docs consistency check: `CLAUDE.md`
  - 当前已写 `STEPFUN_REALTIME_MODEL=step-audio-2`，无需修改，执行时只需确认不引入差异。

---

### Task 1: Add Alembic migration to restore Step Audio 2 default

**Files:**
- Create: `backend/alembic/versions/20260518_0900_067_stepfun_default_model_audio2.py`
- Reference: `backend/alembic/versions/20260317_2200_019_stepfun_default_model_r11.py`

- [ ] **Step 1: Write the migration file**

Create `backend/alembic/versions/20260518_0900_067_stepfun_default_model_audio2.py` with exactly this content:

```python
"""Restore default StepFun realtime model to step-audio-2

Revision ID: 20260518_0900_067
Revises: 20260516_1200_066
Create Date: 2026-05-18 09:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260518_0900_067"
down_revision: str | None = "20260516_1200_066"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE_NAME = "voice_runtime_profiles"
_COLUMN_NAME = "model_name"
_OLD_MODEL = "step-audio-r1.1"
_NEW_MODEL = "step-audio-2"


def _set_server_default(model_name: str) -> None:
    with op.batch_alter_table(_TABLE_NAME) as batch_op:
        batch_op.alter_column(
            _COLUMN_NAME,
            existing_type=sa.String(length=100),
            existing_nullable=False,
            server_default=model_name,
        )


def upgrade() -> None:
    _set_server_default(_NEW_MODEL)

    op.execute(
        sa.text(
            """
            UPDATE voice_runtime_profiles
            SET model_name = :new_model
            WHERE is_default = true
              AND voice_mode = 'stepfun_realtime'
              AND model_name = :old_model
            """
        ).bindparams(new_model=_NEW_MODEL, old_model=_OLD_MODEL)
    )


def downgrade() -> None:
    _set_server_default(_OLD_MODEL)

    op.execute(
        sa.text(
            """
            UPDATE voice_runtime_profiles
            SET model_name = :old_model
            WHERE is_default = true
              AND voice_mode = 'stepfun_realtime'
              AND model_name = :new_model
            """
        ).bindparams(new_model=_NEW_MODEL, old_model=_OLD_MODEL)
    )
```

- [ ] **Step 2: Verify Alembic revision chain is linear**

Run from repo root:

```bash
backend/venv/bin/python -m alembic -c backend/alembic.ini heads
```

Expected: one current head, `20260518_0900_067` after the migration file is present. If the local environment uses `backend/.venv` instead of `backend/venv`, run:

```bash
backend/.venv/bin/python -m alembic -c backend/alembic.ini heads
```

- [ ] **Step 3: Verify migration upgrades cleanly**

Run from repo root:

```bash
backend/venv/bin/python -m alembic -c backend/alembic.ini upgrade head
```

Expected: exit code `0`. The default `voice_runtime_profiles.model_name` server default is `step-audio-2`, and any default `stepfun_realtime` profile still on `step-audio-r1.1` is updated to `step-audio-2`.

---

### Task 2: Add effective-policy regression test

**Files:**
- Modify: `backend/tests/unit/test_voice_runtime_policy_service.py`

- [ ] **Step 1: Add the regression test**

Append this test after `test_env_fallback_policy_defaults_to_latest_realtime_model` in `backend/tests/unit/test_voice_runtime_policy_service.py`:

```python
@pytest.mark.asyncio
async def test_resolve_effective_policy_uses_step_audio_2_default_profile(
    test_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.delenv("STEPFUN_REALTIME_MODEL", raising=False)
    profile = VoiceRuntimeProfile(
        id=str(uuid.uuid4()),
        name="系统默认 Realtime",
        is_default=True,
        is_active=True,
        voice_mode="stepfun_realtime",
        model_name="step-audio-2",
        voice_name="qingchunshaonv",
        temperature=0.7,
        input_audio_format="pcm16",
        output_audio_format="pcm16",
        output_sample_rate=24000,
        turn_detection=None,
        tool_policy={},
    )
    test_db.add(profile)
    await test_db.commit()

    service = VoiceRuntimePolicyService(test_db)
    effective = await service.resolve_effective_policy()

    assert effective["source"]["runtime_profile"] == "system_default"
    assert effective["model_name"] == "step-audio-2"
    assert effective["voice_mode"] == "stepfun_realtime"
    assert effective["input_audio_format"] == "pcm16"
    assert effective["output_audio_format"] == "pcm16"
    assert effective["output_sample_rate"] == 24000
```

- [ ] **Step 2: Run the focused test**

Run from `backend/`:

```bash
python -m pytest tests/unit/test_voice_runtime_policy_service.py::test_resolve_effective_policy_uses_step_audio_2_default_profile -q
```

Expected: `1 passed`. This test is expected to pass once the test code is syntactically correct because service defaults already support `step-audio-2`; its purpose is to lock the intended DB-default behavior.

- [ ] **Step 3: Run existing default-model tests**

Run from `backend/`:

```bash
python -m pytest tests/unit/test_stepfun_realtime_handler.py::test_stepfun_realtime_handler_defaults_to_latest_realtime_model tests/unit/test_voice_runtime_policy_service.py::test_env_fallback_policy_defaults_to_latest_realtime_model tests/unit/test_voice_runtime_policy_service.py::test_resolve_effective_policy_uses_step_audio_2_default_profile -q
```

Expected: all selected tests pass.

---

### Task 3: Align environment example comments

**Files:**
- Modify: `backend/.env.example:63-66`

- [ ] **Step 1: Update the model comment**

Change this line in `backend/.env.example`:

```dotenv
STEPFUN_REALTIME_MODEL=step-audio-2  # step-audio-2 | step-audio-r1.1 | step-audio-2-mini | step-1o-audio
```

to:

```dotenv
STEPFUN_REALTIME_MODEL=step-audio-2  # 默认推荐 step-audio-2；可按需切换 step-audio-2-mini | step-1o-audio
```

- [ ] **Step 2: Verify no recommended default still points to step-audio-r1.1**

Run from repo root:

```bash
python - <<'PY'
from pathlib import Path
paths = [
    Path('backend/.env.example'),
    Path('CLAUDE.md'),
    Path('backend/src/sales_bot/services/voice_runtime_policy.py'),
    Path('backend/src/sales_bot/websocket/stepfun_realtime_handler.py'),
]
for path in paths:
    text = path.read_text(encoding='utf-8')
    if 'STEPFUN_REALTIME_MODEL=step-audio-r1.1' in text or '"step-audio-r1.1"' in text and path.name != '20260317_2200_019_stepfun_default_model_r11.py':
        raise SystemExit(f'unexpected r1.1 default in {path}')
print('StepFun default docs/code check passed')
PY
```

Expected: prints `StepFun default docs/code check passed`.

---

### Task 4: Final verification gate

**Files:**
- Verify only; no additional file changes expected.

- [ ] **Step 1: Run Python diagnostics for modified source/test files**

Run language diagnostics on:

```text
backend/alembic/versions/20260518_0900_067_stepfun_default_model_audio2.py
backend/tests/unit/test_voice_runtime_policy_service.py
```

Expected: zero errors.

- [ ] **Step 2: Run backend focused tests**

Run from `backend/`:

```bash
python -m pytest tests/unit/test_voice_runtime_policy_service.py tests/unit/test_stepfun_realtime_handler.py::test_stepfun_realtime_handler_defaults_to_latest_realtime_model -q
```

Expected: all selected tests pass.

- [ ] **Step 3: Run Alembic head check**

Run from repo root:

```bash
backend/venv/bin/python -m alembic -c backend/alembic.ini heads
```

Expected: one head, `20260518_0900_067`.

- [ ] **Step 4: Inspect final diff**

Run from repo root:

```bash
git diff -- backend/alembic/versions/20260518_0900_067_stepfun_default_model_audio2.py backend/tests/unit/test_voice_runtime_policy_service.py backend/.env.example docs/superpowers/plans/2026-05-18-step-audio-2-default-runtime-plan.md
```

Expected: diff only contains the migration, the regression test, the env comment cleanup, and this plan. Do not commit unless the user explicitly asks.

---

## Self-Review

- **Spec coverage:** The plan covers the identified root cause: DB default profile/server default can override env fallback. Task 1 fixes DB migration state; Task 2 locks effective policy behavior; Task 3 removes misleading example config; Task 4 verifies tests and migration head.
- **Placeholder scan:** No unfinished placeholders or underspecified implementation steps remain. Each code-changing step includes exact code or exact replacement text.
- **Type consistency:** The test uses existing `VoiceRuntimeProfile`, `VoiceRuntimePolicyService`, `AsyncSession`, `pytest`, and `uuid` symbols already present in `backend/tests/unit/test_voice_runtime_policy_service.py`; the migration follows the current Alembic typing style from revision `20260516_1200_066`.
- **Scope control:** No frontend protocol, WebSocket event shape, audio codec, or StepFun handler rewrite is included because the current connection already matches `wss://api.stepfun.com/v1/realtime?model=step-audio-2`.
