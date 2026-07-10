# Gate 0A Platform Contract Truth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 恢复 FastAPI 路由/OpenAPI、domain contributor、Realtime 鉴权与异步采集测试的可信基线，使平台合同失败能够进入主门禁。

**Architecture:** 只修复测试事实和生成式合同，不改变生产 REST/WS、权限、状态机或 Provider 行为。路由盘点通过一个局部兼容函数适配 FastAPI `_IncludedRouter`；domain contributor 继续由生产 composition root 作为唯一注册清单；OpenAPI 从 runtime schema 生成并支持 `--check`。

**Tech Stack:** Python 3.12、FastAPI、PyYAML、pytest/pytest-asyncio、Bash。

## Global Constraints

- 不改变外部 REST/WS event、close code、binary audio shape。
- 不弱化 fail-fast auth、owner/admission、frozen snapshot、KB fail-closed。
- 不用 `xfail`、`skip`、`|| true` 或删除断言掩盖失败。
- 运行 pytest 必须使用 `backend/.venv/bin/python -m pytest -c pyproject.toml`。
- 只修改本计划列出的文件；保留工作区已有用户改动。
- 本计划完成后，后端全量 unit+contract 仍可能保留 Gate 0B 已登记的 Sales Trainer/PPT/secret-scan 失败；不得伪报全量绿色。

---

## File Map

- `backend/tests/integration/test_sales_realtime_reconnect_flow.py`：给 reconnect 集成测试注入合法 token payload。
- `backend/tests/unit/test_stepfun_realtime_handler.py`：显式等待非阻塞 sink 启动，消除调度竞态。
- `backend/tests/conftest.py`：测试进程中复用生产 contributor bootstrap，并在每个测试前后恢复默认注册。
- `backend/tests/unit/common/test_route_integrity.py`：盘点 FastAPI direct routes 和 included route contexts；校验 OpenAPI。
- `backend/tests/unit/test_app_factory.py`：使用同样的 route-context 兼容策略验证 app factory。
- `backend/scripts/generate_openapi_contract.py`：生成/检查 committed OpenAPI。
- `backend/tests/unit/test_generate_openapi_contract.py`：锁定生成器稳定输出和 `--check` 行为。
- `specs/001-ai-practice-system/contracts/openapi.yaml`：由 runtime schema 重新生成。
- `scripts/critical-quality-gate.sh`：把可信合同测试加入主门禁。
- `scripts/README.md`：记录 OpenAPI 生成和检查命令。

### Task 1: 修复 Realtime 测试夹具而不改变生产鉴权和异步语义

**Files:**
- Modify: `backend/tests/integration/test_sales_realtime_reconnect_flow.py:226`
- Modify: `backend/tests/unit/test_stepfun_realtime_handler.py:5343`

**Interfaces:**
- Consumes: `stepfun_realtime_handler.verify_token(token) -> dict[str, Any]`、`transcript_capture_sink(payload) -> Awaitable[None]`。
- Produces: 可重复的 reconnect 和 transcript-capture 行为测试；不产生新生产 Interface。

- [ ] **Step 1: 复现两个已知失败**

Run:

```bash
cd backend
.venv/bin/python -m pytest -c pyproject.toml \
  tests/integration/test_sales_realtime_reconnect_flow.py::test_sales_stepfun_reconnect_restores_turn_continuity_and_cleans_terminal_snapshot \
  tests/unit/test_stepfun_realtime_handler.py::test_handle_upstream_response_audio_transcript_done_dispatches_capture_without_blocking \
  -q --no-cov
```

Expected: 2 failed；reconnect 关闭 4401，capture 在任务调度前读取空列表。

- [ ] **Step 2: 给 reconnect 测试注入与 production payload 一致的身份**

在创建第一个 Handler 前加入：

```python
    monkeypatch.setattr(
        stepfun_module,
        "verify_token",
        lambda _token: {"user_id": str(test_user.user_id)},
    )
```

保留调用中的 `token="test-token"`，它现在只是测试 transport 值；测试不再伪装它是
真实 JWT，也不修改生产 `verify_token` 或 4401 行为。

- [ ] **Step 3: 把异步采集测试改成条件等待**

将测试开头和 sink 改为：

```python
    release_sink = asyncio.Event()
    sink_started = asyncio.Event()
    captured: list[dict[str, Any]] = []

    async def sink(payload: dict[str, Any]) -> None:
        captured.append(payload)
        sink_started.set()
        await release_sink.wait()
```

在 `_handle_upstream_event(...)` 返回后、`assert len(captured) == 1` 前加入：

```python
    await asyncio.wait_for(sink_started.wait(), timeout=1.0)
    assert not release_sink.is_set()
```

这同时证明：事件处理没有等待 sink 完成，且 sink 已真实收到 payload。

- [ ] **Step 4: 运行聚焦测试**

Run: 使用 Step 1 相同命令。
Expected: 2 passed。

- [ ] **Step 5: 提交独立变更包**

```bash
git add backend/tests/integration/test_sales_realtime_reconnect_flow.py \
  backend/tests/unit/test_stepfun_realtime_handler.py
git commit -m "test(realtime): align auth and async capture fixtures"
```

### Task 2: 消除 domain contributor registry 的测试顺序污染

**Files:**
- Modify: `backend/tests/conftest.py:20-75`
- Verify: `backend/tests/unit/test_domain_contributor_bootstrap.py`
- Verify: `backend/tests/contract/test_sales_trainer_phase2_contract.py`
- Verify: `backend/tests/contract/test_sessions.py`

**Interfaces:**
- Consumes: `domain_contributor_bootstrap.register_domain_contributors()`、`register_sales_trainer_asset_revision_lineage_provider()`。
- Produces: 每个测试开始和结束时与 production composition root 一致的默认 contributor 状态。

- [ ] **Step 1: 用顺序相关测试复现 registry 污染**

Run:

```bash
cd backend
.venv/bin/python -m pytest -c pyproject.toml \
  tests/contract/test_sales_trainer_phase2_contract.py \
  tests/contract/test_sessions.py \
  -q --no-cov
```

Expected: `test_sales_trainer_phase2_contract.py` teardown 清空 contributor 后，后续 session
测试出现 `[RUNTIME_POLICY_RESOLVER_NOT_REGISTERED]`。

- [ ] **Step 2: 用生产 bootstrap 替换 conftest 的手工注册清单**

删除 `backend/tests/conftest.py` 中各 domain `register_*_contributor` 的单独 import 和模块
级调用，只保留模型 metadata import、Sales Trainer lineage provider，并加入：

```python
from domain_contributor_bootstrap import register_domain_contributors  # noqa: E402
from sales_trainer.services.asset_revision_lineage_provider import (  # noqa: E402
    register_sales_trainer_asset_revision_lineage_provider,
)


def _register_default_test_contributors() -> None:
    register_domain_contributors()
    register_sales_trainer_asset_revision_lineage_provider()
```

- [ ] **Step 3: 新增自动恢复 fixture**

放在 `test_feature_flags` fixture 前：

```python
@pytest.fixture(autouse=True)
def restore_default_domain_contributors():
    """Keep global contributor registries isolated between tests."""
    _register_default_test_contributors()
    yield
    _register_default_test_contributors()
```

不在 fixture 内清空 registry；production registrar 已验证可重复调用，测试若需要空状态，
必须在自身 Arrange 阶段显式 `clear_*`。

- [ ] **Step 4: 运行顺序复现和 bootstrap 单测**

Run:

```bash
cd backend
.venv/bin/python -m pytest -c pyproject.toml \
  tests/unit/test_domain_contributor_bootstrap.py \
  tests/contract/test_sales_trainer_phase2_contract.py \
  tests/contract/test_sessions.py \
  -q --no-cov
```

Expected: 全部通过；不再出现未注册 runtime policy resolver。

- [ ] **Step 5: 提交独立变更包**

```bash
git add backend/tests/conftest.py
git commit -m "test(backend): isolate domain contributor registries"
```

### Task 3: 让路由完整性测试适配 FastAPI included routers

**Files:**
- Modify: `backend/tests/unit/common/test_route_integrity.py:20-107`
- Modify: `backend/tests/unit/test_app_factory.py:112-152`

**Interfaces:**
- Consumes: direct FastAPI/Starlette route objects，以及当前 FastAPI included route 的 `effective_route_contexts()` 兼容入口。
- Produces: `Iterator[object]` 形式的 effective route inventory，仅存在于测试文件内部。

- [ ] **Step 1: 复现结构型失败**

Run:

```bash
cd backend
.venv/bin/python -m pytest -c pyproject.toml \
  tests/unit/common/test_route_integrity.py \
  tests/unit/test_app_factory.py::test_create_app_registers_startup_http_and_websocket_surfaces \
  tests/unit/test_app_factory.py::test_create_app_does_not_duplicate_method_path_routes \
  -q --no-cov
```

Expected: direct health routes 可见，included HTTP/WS routes 被 `_IncludedRouter` 隐藏。

- [ ] **Step 2: 在两个测试文件各加入局部 compatibility iterator**

在 imports 加入 `from collections.abc import Iterator`，然后定义：

```python
def _effective_routes(app) -> Iterator[object]:
    """Yield direct routes and FastAPI included-router effective contexts."""
    for route in app.router.routes:
        effective_route_contexts = getattr(route, "effective_route_contexts", None)
        if callable(effective_route_contexts):
            yield from effective_route_contexts()
        else:
            yield route
```

不把该 helper 放入生产 `common`；它是框架测试 Adapter。

- [ ] **Step 3: 修改 HTTP 和 WebSocket 盘点**

所有 `_collect_method_path_pairs` / `_method_path_pairs` 循环改为：

```python
    for route in _effective_routes(app):
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
```

WebSocket 盘点改为：

```python
    websocket_paths = {
        str(getattr(route, "path", ""))
        for route in _effective_routes(app)
        if isinstance(getattr(route, "original_route", route), APIWebSocketRoute)
    }
```

`test_route_integrity.py` 需要新增：

```python
from fastapi.routing import APIWebSocketRoute
```

- [ ] **Step 4: 保持静态路由优先级断言**

`prompt_routes` 改为从 `_effective_routes(app)` 读取，继续断言
`by-scenario/{scenario_type}` 位于 `{template_id}` 前。不要删除顺序合同。

- [ ] **Step 5: 运行聚焦测试**

Run:

```bash
cd backend
.venv/bin/python -m pytest -c pyproject.toml \
  tests/unit/common/test_route_integrity.py::test_no_duplicate_http_method_path_routes \
  tests/unit/common/test_route_integrity.py::test_key_business_routers_are_mounted \
  tests/unit/common/test_route_integrity.py::test_lane_11_canonical_route_inventory_is_present \
  tests/unit/common/test_route_integrity.py::test_websocket_routes_support_legacy_and_path_modes \
  tests/unit/common/test_route_integrity.py::test_prompt_templates_static_route_precedes_dynamic_route \
  tests/unit/test_app_factory.py::test_create_app_registers_startup_http_and_websocket_surfaces \
  tests/unit/test_app_factory.py::test_create_app_does_not_duplicate_method_path_routes \
  -q --no-cov
```

Expected: 7 passed。另行运行
`test_committed_openapi_contract_matches_runtime_paths` 仍因 161 个 runtime-only paths
失败，该真实合同漂移由 Task 4 修复。

- [ ] **Step 6: 提交独立变更包**

```bash
git add backend/tests/unit/common/test_route_integrity.py \
  backend/tests/unit/test_app_factory.py
git commit -m "test(api): inspect FastAPI included route contexts"
```

### Task 4: 建立可生成、可检查的 OpenAPI 单一事实源

**Files:**
- Create: `backend/scripts/generate_openapi_contract.py`
- Create: `backend/tests/unit/test_generate_openapi_contract.py`
- Modify: `specs/001-ai-practice-system/contracts/openapi.yaml`
- Modify: `scripts/README.md`

**Interfaces:**
- Produces: `render_openapi_yaml(schema: dict[str, object]) -> str`；`check_contract(path: Path, schema: dict[str, object]) -> bool`；CLI `--check` / `--output`。
- Consumes: `app_factory.create_app().openapi()`。

- [ ] **Step 1: 先写生成器单测**

创建 `backend/tests/unit/test_generate_openapi_contract.py`：

```python
from __future__ import annotations

import yaml

from scripts.generate_openapi_contract import check_contract, render_openapi_yaml


def test_should_render_stable_openapi_yaml() -> None:
    schema = {
        "openapi": "3.1.0",
        "info": {"title": "test", "version": "1"},
        "paths": {"/health": {"get": {"responses": {"200": {"description": "ok"}}}}},
    }

    rendered = render_openapi_yaml(schema)

    assert yaml.safe_load(rendered) == schema
    assert rendered.endswith("\n")


def test_should_detect_semantic_contract_drift(tmp_path) -> None:
    path = tmp_path / "openapi.yaml"
    path.write_text("openapi: 3.1.0\npaths: {}\n", encoding="utf-8")

    assert check_contract(path, {"openapi": "3.1.0", "paths": {}})
    assert not check_contract(
        path,
        {"openapi": "3.1.0", "paths": {"/health": {}}},
    )
```

- [ ] **Step 2: 运行单测确认失败**

Run:

```bash
cd backend
.venv/bin/python -m pytest -c pyproject.toml \
  tests/unit/test_generate_openapi_contract.py -q --no-cov
```

Expected: FAIL with `ModuleNotFoundError: scripts.generate_openapi_contract`。

- [ ] **Step 3: 创建生成器**

创建 `backend/scripts/generate_openapi_contract.py`：

```python
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Sequence

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    REPO_ROOT / "specs" / "001-ai-practice-system" / "contracts" / "openapi.yaml"
)
sys.path.insert(0, str(BACKEND_ROOT / "src"))


def build_runtime_schema() -> dict[str, Any]:
    from app_factory import create_app

    return create_app().openapi()


def render_openapi_yaml(schema: dict[str, object]) -> str:
    rendered = yaml.safe_dump(
        schema,
        allow_unicode=True,
        sort_keys=False,
        width=100,
    )
    return rendered if rendered.endswith("\n") else f"{rendered}\n"


def check_contract(path: Path, schema: dict[str, object]) -> bool:
    if not path.exists():
        return False
    committed = yaml.safe_load(path.read_text(encoding="utf-8"))
    return committed == schema


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate the runtime OpenAPI contract")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    schema = build_runtime_schema()
    output = args.output.resolve()
    if args.check:
        if check_contract(output, schema):
            print(f"OpenAPI contract is current: {output}")
            return 0
        print(f"OpenAPI contract is stale: {output}")
        return 1
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_openapi_yaml(schema), encoding="utf-8")
    print(f"Wrote OpenAPI contract: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: 运行生成器测试**

Run: 使用 Step 2 相同命令。
Expected: 2 passed。

- [ ] **Step 5: 生成 committed contract 并检查幂等**

Run:

```bash
cd backend
.venv/bin/python scripts/generate_openapi_contract.py
.venv/bin/python scripts/generate_openapi_contract.py --check
```

Expected: 第一条写入合同；第二条退出 0 并输出 `OpenAPI contract is current`。

- [ ] **Step 6: 更新脚本文档**

在 `scripts/README.md` 的质量/契约命令区加入：

````markdown
### OpenAPI 合同

```bash
cd backend
.venv/bin/python scripts/generate_openapi_contract.py
.venv/bin/python scripts/generate_openapi_contract.py --check
```

生成命令以 FastAPI runtime schema 为权威更新 committed contract；`--check` 只读并在
语义漂移时返回非零退出码。
````

- [ ] **Step 7: 验证路由和 OpenAPI 合同**

Run:

```bash
cd backend
.venv/bin/python -m pytest -c pyproject.toml \
  tests/unit/test_generate_openapi_contract.py \
  tests/unit/common/test_route_integrity.py \
  -q --no-cov
```

Expected: 全部通过，runtime-only 和 committed-only path 均为 0。

- [ ] **Step 8: 提交生成合同变更包**

```bash
git add backend/scripts/generate_openapi_contract.py \
  backend/tests/unit/test_generate_openapi_contract.py \
  specs/001-ai-practice-system/contracts/openapi.yaml \
  scripts/README.md
git commit -m "test(api): generate and verify runtime OpenAPI contract"
```

### Task 5: 把恢复后的平台合同加入主门禁

**Files:**
- Modify: `scripts/critical-quality-gate.sh:201-258`

**Interfaces:**
- Consumes: `BACKEND_GATE_TARGETS` 和现有 canonical quality gate。
- Produces: 每次主门禁必跑的 route/OpenAPI/reconnect 测试；不新增第二套 gate。

- [ ] **Step 1: 扩展现有后端目标数组**

向 `BACKEND_GATE_TARGETS` 加入：

```bash
  "tests/integration/test_sales_realtime_reconnect_flow.py"
  "tests/unit/common/test_route_integrity.py"
  "tests/unit/test_app_factory.py"
  "tests/unit/test_generate_openapi_contract.py"
```

不要删除当前已列出的 StepFun、session authority 或 E2E 目标。

- [ ] **Step 2: 在启动 smoke stack 前增加只读 OpenAPI check**

在 Backend ruff 后加入：

```bash
log "OpenAPI contract parity"
(
  cd "${ROOT_DIR}/backend"
  "${PYTHON_BIN}" scripts/generate_openapi_contract.py --check
)
```

- [ ] **Step 3: 运行无服务依赖的 Gate 0A 回归集**

Run:

```bash
cd backend
.venv/bin/python scripts/generate_openapi_contract.py --check
.venv/bin/python -m pytest -c pyproject.toml \
  tests/integration/test_sales_realtime_reconnect_flow.py \
  tests/unit/common/test_route_integrity.py \
  tests/unit/test_app_factory.py \
  tests/unit/test_domain_contributor_bootstrap.py \
  tests/unit/test_generate_openapi_contract.py \
  tests/unit/test_stepfun_realtime_handler.py::test_handle_upstream_response_audio_transcript_done_dispatches_capture_without_blocking \
  tests/contract/test_sales_trainer_phase2_contract.py \
  tests/contract/test_sessions.py \
  -q --no-cov
```

Expected: 全部通过。

- [ ] **Step 4: 运行静态检查**

Run:

```bash
cd backend
.venv/bin/python -m ruff check \
  scripts/generate_openapi_contract.py \
  tests/conftest.py \
  tests/integration/test_sales_realtime_reconnect_flow.py \
  tests/unit/common/test_route_integrity.py \
  tests/unit/test_app_factory.py \
  tests/unit/test_generate_openapi_contract.py \
  tests/unit/test_stepfun_realtime_handler.py
```

Expected: exit 0。

- [ ] **Step 5: 重跑全量后端 unit+contract 并记录 Gate 0B 剩余失败**

Run:

```bash
cd backend
.venv/bin/python -m pytest -c pyproject.toml tests/unit tests/contract -q --no-cov
```

Expected: Gate 0A 负责的 route/app-factory/contributor/transcript 失败消失。若仍有失败，
只允许是路线图 Gate 0B 已列出的 Sales Trainer、PPT forbidden word 或 secret scan
簇；出现新的平台合同失败则本 Task 不得完成。

- [ ] **Step 6: 提交门禁变更包**

```bash
git add scripts/critical-quality-gate.sh
git commit -m "ci: enforce platform route and OpenAPI truth"
```

## Self-Review Checklist

- [ ] 计划没有改变生产 auth、permission、lifecycle 或 WS payload。
- [ ] OpenAPI 文件只能由 runtime schema 生成，`--check` 不写文件。
- [ ] Contributor fixture 使用 production bootstrap，没有第二份手工清单。
- [ ] 异步测试证明 non-blocking，而不是通过 sleep 碰运气。
- [ ] Gate 0B 剩余失败被显式报告，没有伪报全量绿色。
