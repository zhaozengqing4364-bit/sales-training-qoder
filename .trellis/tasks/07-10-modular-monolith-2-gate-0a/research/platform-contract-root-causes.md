# Gate 0A 平台合同根因证据

日期：2026-07-10

## 1. FastAPI route inventory

反馈环：

```bash
cd backend
.venv/bin/python -m pytest -c pyproject.toml \
  tests/unit/common/test_route_integrity.py \
  tests/unit/test_app_factory.py::test_create_app_registers_startup_http_and_websocket_surfaces \
  -q --no-cov
```

事实：`app.router.routes` 现在包含 `_IncludedRouter`；对象没有直接 `path/methods/routes`，
但提供 `effective_route_contexts()`，其 context 具有完整 prefix 后的 `path`、`methods`
和 `original_route`。HTTP runtime schema 和 `app.url_path_for()` 均证明业务路由真实存在。

结论：4 个 route presence/order 失败是框架结构型测试漂移，不是生产路由丢失。正确
修复是测试层 adapter；不得删除关键路由断言。

## 2. OpenAPI parity

反馈环：

```bash
cd backend
.venv/bin/python -m pytest -c pyproject.toml \
  tests/unit/common/test_route_integrity.py::test_committed_openapi_contract_matches_runtime_paths \
  -q --no-cov
```

事实：committed schema 330 paths，runtime schema 491 paths；161 个 runtime-only，0 个
committed-only。两者 top-level keys、info、components 类型一致，没有额外手写 servers
或 tags 需要保留。

结论：这是实际生成合同漂移。正确修复是 runtime schema 生成器 + `--check`；不得只把
161 个 path 名手工追加或把 parity 测试移出门禁。

## 3. Contributor registry test isolation

反馈环：

```bash
cd backend
.venv/bin/python -m pytest -c pyproject.toml \
  tests/contract/test_sales_trainer_phase2_contract.py \
  tests/contract/test_sessions.py \
  -q --no-cov
```

事实：前一测试文件 teardown 调用 `clear_practice_session_contributors()`，后一文件复用
module-level app，未重新运行 composition root，导致
`[RUNTIME_POLICY_RESOLVER_NOT_REGISTERED]`。`create_app()` 本身会通过
`register_routers()` 调用 `register_domain_contributors()`；连续重复调用 bootstrap 未
报错。当前 `tests/conftest.py` 维护了一份不完整的手工 contributor 清单。

结论：根因是全局 registry 的跨测试污染和测试 composition drift。正确修复是每个测试
前后恢复生产 bootstrap；不得让 common 在 port 缺失时 fallback 到具体 sales 实现。

## 4. Realtime test fixtures

### 4.1 Reconnect auth

生产 Handler 在 token 无效时 `close(4401, "unauthorized")` 并立即返回。Reconnect
集成测试仍传 `test-token` 且没有 patch `verify_token`，因此永远等不到 `connected`。
同类 Presentation 测试已采用 monkeypatch 身份 payload。

结论：生产 fail-fast auth 正确，测试夹具落后。只 patch 测试 module 的 `verify_token`，
保持 token transport 和 owner ID 一致。

### 4.2 Transcript capture

生产路径用后台 task 调用 capture sink，以保证 response event 不被持久化阻塞。测试在
`_handle_upstream_event()` 返回后立即检查 `captured`，事件循环可能尚未调度 sink。

结论：以 `sink_started` Event 建立条件等待，并保持 `release_sink` 未设置来证明主链
没有等待 sink 完成。禁止 `asyncio.sleep()` 碰运气。

## 5. 已知非 Gate 0A 失败

后端全量 unit+contract 当前另有 Sales Trainer audio scenario/topic/quiz/permission/
lineage、PPT forbidden word、secret scan 失败；前端另有 dashboard 时间和
business-skills topic-governance fixture 失败。这些问题需要独立领域语义诊断，不应混入
平台合同修复。
