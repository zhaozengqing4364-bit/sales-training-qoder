# Quality Guidelines

> Code standards, testing, and forbidden patterns for the backend.

---

## Overview

Quality gates: **pytest** (with coverage floor), **ruff**, **mypy**. Tests mirror the domain layout under `backend/tests/`. Contract tests keep `docs/api-contract/` aligned.

Reference: `backend/pyproject.toml`, `backend/tests/AGENTS.md`, `backend/AGENTS.md`.

---

## Test Structure

```
backend/tests/
├── unit/           # Fast, isolated, fake external boundaries
├── integration/    # DB + service layer; real PostgreSQL when semantics require it
├── contract/       # API shape vs docs/api-contract/
├── performance/    # Latency / concurrency NFRs
├── e2e/
└── conftest.py     # test_db, async_client, auth_headers
```

### Naming

Preferred: `test_should_<behavior>_when_<condition>` (`tests/AGENTS.md`).

Also accepted: `test_<unit>_<behavior>` — e.g. `tests/unit/test_realtime_audio_flow.py`.

### Async tests

```python
@pytest.mark.asyncio
async def test_should_commit_when_valid():
    ...
```

Fixtures: `pytest_asyncio.fixture` in `tests/conftest.py`.

### Markers

- `@pytest.mark.integration`
- `@pytest.mark.contract`
- `@pytest.mark.performance`

Examples: `tests/integration/test_sales_flow.py`, `tests/contract/test_admin_governance_contract.py`.

### Unit test style

- Fake/stub dependencies — no real StepFun, DashScope, or PostgreSQL in unit tests.
- Parametrize edge cases — see `tests/unit/test_session_control_adapter.py`.

### Durable Task and governed AI test boundary

- Lease recovery, `SKIP LOCKED`, fencing, concurrent idempotency, Outbox effect-once, budget/rate windows, migration and query plans require isolated real PostgreSQL. SQLite or mocked sessions cannot prove these contracts.
- Fake only true external boundaries: Provider, ASR, object storage, clock and controlled sleeper. Deterministic fakes must implement the same public Port and must never be selected implicitly by a production composition root.
- A Task/AI platform slice runs focused unit/contract, its PostgreSQL suites, migration roundtrip, Mypy, Ruff, route/OpenAPI checks and shell syntax. The full repository gate remains the final rollout slice unless a shared change cannot be validated locally.
- Fault tests include crash before/after external response, stale owner/lease, late result, schema-invalid output, budget/rate rejection, missing registry/transport, database commit failure, SIGTERM drain and duplicate delivery.

---

## Lint and Format

From `backend/pyproject.toml`:

| Tool | Settings |
|------|----------|
| **ruff** | line-length 88, `select = E,F,I,N,W,UP`, `src = ["src"]` |
| **black** | line-length 88, py311 |
| **mypy** | `disallow_untyped_defs = true`, `mypy_path = "src"` |

Commands:

```bash
cd backend && ruff check src/
cd backend && ruff format src/
cd backend && mypy src/
```

---

## Coverage

Default pytest addopts include `--cov=src --cov-fail-under=48`. Run full suite before large merges:

```bash
cd backend && pytest
cd backend && pytest tests/unit/
```

主门禁不维护 unit/contract 固定文件清单：始终自动发现 `tests/unit tests/contract` 并开启 branch
coverage。`scripts/select_quality_tests.py` 只选择 integration/backend E2E/Playwright；选择权威为
`docs/architecture/quality-test-selection-policy.yaml`，CodeGraph 只能加测，非法证据必须扩大。

selected integration/E2E 必须用 `--cov-append --cov-branch` 合并 unit+contract 的 fresh coverage
data，最终 `backend-coverage.json` 生成后才运行 `scripts/check_changed_coverage.py`。禁止用只含
unit/contract 的报告判断 changed-line。changed executable line 至少 80%，关键文件 branch ratio
不得低于 `docs/architecture/changed-coverage-policy.yaml` 的 adoption floor。

本地 smoke/release gate 每次启动 Next dev 前必须删除生成目录 `web/.next/dev`。`NEXT_PUBLIC_*`
是编译期输入，复用旧 Turbopack state 或读取面向其他主机的 `.env.local` 会把错误 API/WS 地址
带入本地验收，并可能让缓存持续膨胀直至 ENOSPC。`scripts/dev-smoke-up.sh` 必须显式注入
loopback `NEXT_PUBLIC_API_URL` / `NEXT_PUBLIC_WS_URL`（只允许由 `SMOKE_FRONTEND_*` 覆盖），只清理
dev 生成物，不修改 `.env.local`、源码或 production build；`test_dev_up_script.py` 保护该顺序和
端点隔离。

在非 root Linux 环境中，release gate 可使用已准备的
`.sisyphus/playwright-libs/root/usr/lib/x86_64-linux-gnu` 浏览器动态库目录。所有 Playwright 调用
必须经过 `run_playwright`，由它在目录存在时只为浏览器进程注入 `LD_LIBRARY_PATH`；目录不存在
时保持系统 Playwright 行为，不下载依赖、不跳过用例。

临时 adoption anchor 在 selection/coverage policy 中必须完全一致，具有 owner、reason、
retire_when 和 expires_on；guard 对漂移或过期 fail closed。

## Scenario: Policy-Governed Quality Selection And Changed Coverage

### 1. Scope / Trigger

- Trigger: 修改测试 runner、CI、coverage 配置、slow-test fixture/support file、生产路径或两份
  architecture quality policy。
- Scope: `scripts/critical-quality-gate.sh`、`scripts/select_quality_tests.py`、
  `scripts/check_changed_coverage.py`、release workflow 及其版本化 YAML policy。

### 2. Signatures

```bash
python3 scripts/select_quality_tests.py \
  --mode pr --base <base-sha> --head <head-sha> \
  --output .sisyphus/evidence/quality-test-selection.json
python3 scripts/select_quality_tests.py \
  --output .sisyphus/evidence/quality-test-selection.json \
  --emit-family playwright
python3 scripts/check_changed_coverage.py \
  --backend-report .sisyphus/evidence/backend-coverage.json \
  --frontend-report web/coverage/coverage-final.json \
  --selector-manifest .sisyphus/evidence/quality-test-selection.json
```

### 3. Contracts

- unit+contract 和 Vitest 是不可缩小底座；selector 只输出
  `backend_integration`、`backend_e2e`、`playwright` runner path 数组。
- deterministic path policy 是权威；健康 CodeGraph 只加测。缺失 CodeGraph 记录 degraded，非法、
  空生产影响或 worktree mismatch 必须 fallback。
- family 目录下的 `.spec.ts`/`test_*.py` 才能进入 runner；route manifest、fixture 和 setup helper
  只能触发 family/global fallback，不能作为命令参数。
- 跨 runner fixture（当前包括 `backend/tests/e2e/fixtures/**`）必须 global fallback；不能依赖某个
  消费者恰好在 critical baseline 中的旁路事实。
- changed coverage 只读取 fresh branch-aware backend JSON 与 Istanbul frontend JSON；普通变更行
  聚合阈值 80%，关键 branch changed source line 100% 且全文件不低于 adoption floor。

### 4. Validation & Error Matrix

| Condition | Required result |
|---|---|
| base/head 不可信、D/R、未知 production path | 对相关族或全部族 fallback，manifest 记录 reason |
| CodeGraph command 成功但 JSON 非法/生产影响为空 | `invalid` + full fallback |
| slow-test support file 变更 | support file 不进 runner；对应 family fallback |
| 跨 runner fixture 变更 | full fallback，所有消费 runner 均被选择 |
| changed production file 不在 coverage report | guard 非零退出 |
| adoption anchor 过期或两份 policy 不一致 | selector/guard 非零退出 |
| changed executable lines < 80% 或关键 branch 回退 | guard 非零退出并生成 violation evidence |

### 5. Good / Base / Bad Cases

- Good: production change 命中 path rule，健康 CodeGraph 再追加测试，manifest 稳定排序且 guard 通过。
- Base: CI 没有 CodeGraph；deterministic baseline/path policy 仍运行，manifest 明确 degraded reason。
- Bad: 把 `.json`/`.base64`/route manifest 直接交给 pytest/Playwright，或让空 CodeGraph 结果缩小集合。

### 6. Tests Required

- Selector unit：可信 base、dirty/staged/untracked、D/R、direct runner、support file、跨 runner fixture、
  malformed/empty graph、稳定排序、路径拒绝和 adoption expiry。
- Coverage unit：backend/frontend schema、80% 边界、missing production file、critical changed branch、
  baseline regression、base N/A/full fallback 和 anchor policy parity。
- Integration/E2E：至少保留持久化跨 session 路径解锁，以及 smoke/newcomer/presentation/sales 本地
  Provider 关键链路。
- Final：完整 `bash scripts/critical-quality-gate.sh` 必须自然 exit 0，artifact 非空且可解析。

### 7. Wrong vs Correct

#### Wrong

```python
# 空结果被当成“无影响”，support file 也作为 runner 参数执行。
selected = codegraph_tests
subprocess.run(f"pytest {' '.join(selected)}", shell=True)
```

#### Correct

```python
# policy/critical 是下界，CodeGraph 只做加法；runner 接收验证后的 argv。
selected = deterministic_tests | validated_codegraph_tests
subprocess.run([python, "-m", "pytest", *validated_runner_paths], check=True)
```

---

## Forbidden Patterns

From `backend/AGENTS.md` and `.kiro/steering/backend-principles.md`:

| Never | Always |
|-------|--------|
| `print()` | `get_logger(__name__)` |
| `session.query(Model)` | `select(Model)` |
| `orm_mode = True` | `ConfigDict(from_attributes=True)` |
| `@app.on_event("startup")` | lifespan in `app_lifespan.py` |
| Sync DB | `AsyncSession` |
| Raw HTTPException 500 to practice clients | `Result` + `error_response` |
| Unit tests hitting real LLM/TTS APIs | mocks / fakes |

---

## Code Review Checklist

- [ ] Types on new public functions (mypy-clean).
- [ ] Errors use `Result` or `error_response`, not bare exceptions to clients.
- [ ] Logs use structlog with trace_id; no secrets logged.
- [ ] DB changes include Alembic migration.
- [ ] API changes update contract tests if applicable.
- [ ] Scenario code stays in its module (`sales_bot` vs `presentation_coach` — no cross-contamination).

---

## Common Mistakes

- Running pytest from repo root instead of `backend/` — loses `pyproject.toml` config.
- Adding integration test dependencies to unit tests — slows CI and flakes on network.
- Changing response shape without updating `tests/contract/` and `docs/api-contract/`.
- Mutating singleton collaborators such as `get_connection_manager().send_json` or `.connect` in a test without restoring them. If a test must replace a singleton method, use `monkeypatch` or add an autouse fixture in the affected suite that restores `ConnectionManager.<method>.__get__(manager, ConnectionManager)` and clears `active_connections` before and after each test.
- For Sales Trainer learner-record workflows, do not gate review or learner-scope write actions with content-management permission. Training managers need to reach the service so explicit Team membership/scope policy can decide; content admins configure assets but should not implicitly review learner dossiers.

---

## Verification Commands

```bash
cd backend && pytest tests/unit/
cd backend && pytest tests/contract/
cd backend && ruff check src/ && mypy src/
```
