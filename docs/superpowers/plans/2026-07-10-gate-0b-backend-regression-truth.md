# Gate 0B Backend Regression Truth Implementation Plan

日期：2026-07-10  
状态：**Completed（2026-07-10）**  
范围：后端 unit + contract 回归真相、ForbiddenWord 写入响应合同、Sales Trainer
canonical path fixture、Secret hygiene 测试隔离。

## 1. 目标与基线

Gate 0A 完成后，权威命令仍有 15 项失败：

```bash
cd backend
.venv/bin/python -m pytest -c pyproject.toml \
  tests/unit tests/contract -q --no-cov
```

当时结果为 `2613 collected, 2598 passed, 15 failed, 1 skipped, 74 warnings`。
本 Gate 的目标不是批量改断言，而是逐项判断生产缺陷、fixture 漂移或语义漂移，
恢复可用于后续架构迁移的可信反馈环。

## 2. 失败分类

| 分类 | 数量 | 处理原则 |
|---|---:|---|
| Fixture 漂移 | 11 | 迁移到 canonical scenario、active revision、正式发布入口和确定性临时夹具 |
| 断言语义漂移 | 3 | 以已生效的权限、learning-topic 和 journey 合同为权威收紧断言 |
| 生产缺陷 | 1 | 修生产根因并增加 public API、权限、失败事务和 OpenAPI 回归 |

生产缺陷是两个同形 ForbiddenWord POST 的 ORM 响应：路由已成功 commit，随后
FastAPI/Pydantic 才尝试序列化 `Any` 类型的 SQLAlchemy 对象并返回 500，客户端重试时
存在重复写入风险。

逐项根因和调用链证据保存在归档 Trellis task 的 `research/`：

- `sales-trainer-failure-classification.md`
- `platform-api-failure-classification.md`

## 3. 实施切片

### 3.1 ForbiddenWord 写入响应

- [x] `admin` 与 `presentation_coach` 两个 POST 复用
  `ForbiddenWordResponse`；
- [x] decorator 显式声明 `response_model`；
- [x] 事务顺序改为
  `add -> flush -> refresh -> DTO validate -> commit -> return DTO`；
- [x] `SQLAlchemyError` 先 rollback，再返回各模块稳定错误码；
- [x] runtime generator 更新 committed OpenAPI。

回归覆盖：

- 两个 POST 的严格 201、公共 DTO 与唯一持久行；
- 两个 POST 强制数据库失败后的 500、稳定错误码与 0 持久行；
- 两个 POST 的 non-admin 403 与 0 持久行；
- runtime `/openapi.json` 的两个 201 都引用
  `#/components/schemas/ForbiddenWordResponse`。

### 3.2 Sales Trainer fixture 真相

- [x] Audio/path/record fixture 使用 canonical `scenario_key`、purpose、prompt、material、
  active path revision 和 lineage；
- [x] platform admin learner-entry 按当前验收合同断言，仍保持用户进度隔离；
- [x] learning-topic evidence 不再错误推进 required-path stage；
- [x] QuizService 测试先创建 published learning content 和 exam paper，再通过
  `SalesTrainerPathConfigService.save_config/publish_config` 正式发布 active path；
- [x] unlock 算法测试迁到 `build_path_payload` 正确 projection seam，不再伪造两个
  `article_exam` required modules。

### 3.3 Secret hygiene fixture

- [x] 使用 `tmp_path/.sisyphus/evidence` 创建普通 runtime evidence 和生成报告；
- [x] 直接使用 scanner 的 `DEFAULT_PATHS`；
- [x] 证明 runtime evidence 被扫描、secret report 被排除；
- [x] 不再依赖 gitignored 工作站文件是否存在。

## 4. 独立复核与规范沉淀

独立 Trellis Check 首轮发现两个 P1：ForbiddenWord 缺失败/权限分支回归，以及
Quiz fixture 绕过正式发布校验。两项均以 Red → Green 修复，复核后 P1 清零。

`.trellis/spec/backend/error-handling.md` 已增加七段式
“ORM-backed write responses” 可执行合同，固化 commit 前 DTO 验证、rollback、权限、
持久化和 OpenAPI 断言。

非阻塞覆盖建议：增加一条“持久化完成进度 → `SalesTrainerPathService` → 下一关解锁”
的单体跨层测试。现有 projection、正式发布、Quiz gate、audio submission 和 Journey
visibility 已分别覆盖当前合同；该增强进入 Gate 1B 关键状态机 branch coverage 设计。

## 5. 验证证据

最终权威结果：

```text
backend unit + contract: 2617 passed, 1 skipped, 74 warnings in 379.50s
affected integrations: 41 passed, 2 warnings in 23.84s
focused review fixes: 15 passed, 1 warning
Ruff + format: pass (10 changed Python files)
architecture dependency guard: pass
runtime OpenAPI parity: pass
Trellis context validation: pass
git diff --check: pass
```

精确 mypy 仍只暴露既有 `src/common/ai/config_manager.py:279` 的
`float(str | None)`；它不来自本 Gate 修改。Gate 1B 负责统一 runner 与静态门禁事实，
不得用忽略规则掩盖该错误。

## 6. 兼容性、风险与回滚

- 风险等级：P1；无 migration、无生产数据操作、无真实 Provider 调用。
- REST URL、method、201 status、认证和请求 payload 保持兼容；响应从无类型 schema
  收紧为既有公共 DTO，是合同澄清。
- 权限继续由两个 route 的 admin dependency 与主 router mount 共同执行。
- Sales Trainer 生产发布、scenario、active revision、对象级访问和 lineage 校验没有放松。
- 回滚按两个独立工作提交执行：
  - `63a878db`：ForbiddenWord 生产修复、合同/权限测试与 OpenAPI；
  - `0c418048`：Sales Trainer 与 Secret fixture 迁移。

## 7. Trellis 证据

- 实施任务：`.trellis/tasks/07-10-modular-monolith-2-gate-0b`
- 完成后归档：`.trellis/tasks/archive/2026-07/07-10-modular-monolith-2-gate-0b`
- 任务内包含 PRD、两份逐项根因研究、implement/check context 和完整 verification log。

