# Gate 6 Trellis Check

日期：2026-07-12 UTC

## 结论

Blocking finding：**0**。

检查范围为 Gate 5 closure `13cdfd6a` 之后的 44 个 Gate 6 文件；用户未提交的 readiness plan 排除。
实现与 PRD、七段式 Trellis spec、依赖政策和 authority docs 一致。随后执行的唯一 clean-start
canonical gate 自然输出 `Critical quality gate passed`。

## Spec compliance

| 合同 | 证据 | 结果 |
|---|---|---|
| Selection 是闭集数据 | dataclass 精确四字段；四个 enum key；无 handler module/attribute locator | Pass |
| Root factory ownership | Sales-local map 与 Presentation app-root map 互斥且穷尽；unknown/cross-root key fail closed | Pass |
| Dependency direction | Presentation 域无 Sales import；domain 无 app-root back-import；实际图 51 边 | Pass |
| Roleplay owner | Common forwarding file 与 importer 均为 0；Curriculum 直接使用 `roleplay` | Pass |
| Compatibility deletion test | 222 model / 262 frontend importers及 flag/cache 实际构造证据形成 retain 决策 | Pass |
| Policy lifecycle | 只删除实际消失的 Presentation-to-Sales target；Common-to-Roleplay 活跃源保留 | Pass |
| Wire/state/write compatibility | Golden、snapshot、reconnect、Grounding/evidence、single-writer 聚焦矩阵 | Pass |

## Cross-layer data flow

```text
TrainingRuntimeDescriptor
  -> ScenarioTrainingPlugin.select_runtime_handler
  -> frozen ScenarioRuntimeHandlerSelection(factory_key)
  -> delivery/application-root read-only factory map
  -> exactly one handler
  -> existing auth / RuntimeGate / WebSocket / persistence flow
```

- plugin boundary 不传递 callable、class、kwargs 或 import locator；validation 在构造前完成。
- Presentation behavior → neutral adapter port → root-composed transport；domain 不读取 root internals。
- 错误以稳定 `unknown_runtime_handler_factory_key` 在 construction boundary fail closed，不产生部分对象。
- 本切片不改变 API DTO、数据库、前端或事务边界；OpenAPI parity 无变化。

## Reuse and consistency

- 查重后将两域真正共享的 transcription duplicate window 收敛到
  `training_runtime.realtime.constants`；没有复制业务规则。
- 两个 factory map 保持各自 delivery ownership；共享一个全局 map 会导致 Sales 反向依赖 app root，
  因而未作错误 DRY 抽象。
- 删除未使用的 root factory wrapper，Presentation route 保持唯一 admission/resolution 入口。
- 同类 runtime diagnostics 继续输出稳定值但不执行字符串；未新增 global barrel、service locator、
  dependency exception、依赖或 schema。

## Verification

| 检查 | 结果 |
|---|---|
| Ruff full backend | Pass |
| full mypy | `Success: no issues found in 677 source files` |
| architecture dependency guard | `dependency policy satisfied` |
| OpenAPI parity | committed contract current |
| TypeScript | `tsc --noEmit` pass |
| ESLint | exit 0；82 个既有 warning、0 error，Gate 6 未改前端且未新增 warning |
| Gate 6 focused matrix | `161 passed` |
| Gate 6 + architecture contracts | `28 passed` |
| JSON / JSONL / diff whitespace | Pass |
| Brooks architecture audit | 100/100；Critical/Warning/Suggestion = 0 |

## Coverage and residual risk

- CodeGraph 最新索引对核心 runtime 变更选出 227 个测试文件，因此最终仍必须执行 full backend、
  Vitest、selected integration/E2E、Playwright 和 changed coverage，不能用聚焦矩阵代替 canonical。
- `StepFunRuntimeAdapterPort` 是 retained compatibility seam，仍暴露现有 cooperative-MRO 状态合同；
  Golden 和真实 adapter tests 对其提供 characterization protection。完全去除 transport inheritance 需要
  独立消费者/发布证据，不在 Gate 6 伪装完成。
- 82 个 ESLint warnings 属既有全仓 warning baseline，不在无前端改动的 Gate 6 顺手修复；canonical
  对其当前政策是 0 error。该事实不构成 Gate 6 blocking finding。

## Final canonical

backend `3322 passed, 1 skipped`；Vitest 213 files / `1345 passed, 6 skipped`；Playwright
generic/smoke/newcomer/presentation/sales `3/9/11/2/1 passed`；selected backend `598 passed,
21 skipped`；changed coverage 7326/8048（91.03%），violations 为空。最终 blocking finding 保持 0。
