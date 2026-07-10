# Gate 0B 平台/API 失败分类

## 范围与方法

只读诊断以下两个失败，未修改生产代码、测试代码或 Git 历史：

1. `tests/unit/test_secret_hygiene_scan.py::test_secret_scan_default_paths_cover_runtime_evidence_and_skip_report`
2. `tests/contract/test_ppt_upload.py::TestPPTUploadContract::test_add_forbidden_word`

先通过 CodeGraph 读取 scanner、route、DTO、ORM、认证依赖和调用/影响链，再用聚焦 pytest 复现。相关规范包括：

- `.trellis/spec/backend/platform-contract-truth.md`
- `.trellis/spec/backend/quality-guidelines.md`
- `backend/AGENTS.md`
- `backend/src/admin/AGENTS.md`
- `backend/tests/AGENTS.md`
- `docs/api-contract/README.md`
- `backend/src/admin/api/security_inventory.py`

## 结论总览

| 失败 | 分类 | 根因 | 生产代码是否需要改 |
|---|---|---|---|
| secret default paths | 测试 fixture / 断言漂移 | 测试依赖被 `.gitignore` 排除、未纳入仓库的工作站 evidence 文件 | 否；改成 `tmp_path` 确定性合同测试 |
| forbidden word POST | 生产 API 序列化 bug，测试本身另有弱 fixture | 路由声明 `-> Any` 且没有显式 `response_model`，FastAPI/Pydantic 无法序列化 SQLAlchemy ORM 对象；写入已 commit 后才报 500 | 是；返回稳定 DTO 并显式声明 response model |

---

## 1. Secret hygiene 默认路径失败

### 可复现信号

命令：

```bash
cd backend
PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest -p no:cacheprovider \
  tests/unit/test_secret_hygiene_scan.py::test_secret_scan_default_paths_cover_runtime_evidence_and_skip_report \
  -vv -s --no-cov
```

结果：稳定失败。`module.DEFAULT_PATHS` 确实包含 `.sisyphus/evidence`，但 `iter_files()` 的结果中没有：

- `newcomer-ai-coach-real-provider-gate.json`
- `newcomer-real-provider-gate.json`

当前 `.sisyphus/evidence` 只有本工作站其他运行生成的截图、trace 和报告资产。

### CodeGraph / 仓库证据

- `scripts/check_secret_hygiene.py:19-26`：`DEFAULT_PATHS` 包含 `evidence` 与 `.sisyphus/evidence`。
- `scripts/check_secret_hygiene.py:179-200`：`iter_files()` 对存在的目录递归枚举普通文件，并通过 `is_excluded_report_path()` 排除生成的 secret scan JSON。
- `scripts/check_secret_hygiene.py:208-240`：`scan_paths()` 和 `main()` 都复用同一个 `iter_files()`；没有第二套默认路径逻辑。
- `backend/tests/unit/test_secret_hygiene_scan.py:103-112`：失败测试直接读取真实 `REPO_ROOT/.sisyphus/evidence`，并断言两个具体文件名必须存在。
- `.gitignore:181`：整个 `.sisyphus/` 被忽略。
- `git ls-files .sisyphus/evidence`：无输出；两个断言文件从未成为仓库 fixture。
- 该测试由提交 `e0607eb6` 加入时，把 scanner 默认路径合同和当时工作站恰好存在的 runtime evidence 混在了一个断言里。
- 相邻测试 `test_secret_scan_skips_generated_report_names_to_prevent_recursive_pollution` 已经用 `tmp_path` 正确验证 report-name 排除规则。

### 排名假设与证伪

1. **工作站 evidence 缺失导致测试环境耦合**：预测为默认路径断言通过、具体文件名断言失败；实际完全一致。
2. **scanner 移除了 `.sisyphus/evidence`**：预测 `DEFAULT_PATHS` 断言先失败；实际未发生，证伪。
3. **report 排除规则误删所有 runtime JSON**：预测目录内其他普通 JSON 也不会被枚举；当前 `.last-run.json` 被枚举，且排除规则只命中 secret report marker，证伪。

### 根因判定

这是**测试 fixture / 断言漂移**，不是 production scanner bug。

必须区分两个合同：

1. **默认扫描路径合同**：`.sisyphus/evidence` 必须属于 `DEFAULT_PATHS`，以覆盖本地/验收流程产生的运行证据，即使这些文件不提交到 Git。
2. **某次运行的 evidence 是否存在**：这是工作站瞬时状态，不是单元测试可依赖的仓库事实。

生产 `iter_files()` 对当前文件系统扫描是目标行为；把它改成只枚举 `git ls-files` 会漏掉最需要 secret hygiene 保护的未提交 runtime evidence。

### 最小确定性修复

只改失败测试，不改 scanner：

1. 在 `tmp_path/.sisyphus/evidence/` 创建：
   - 一个普通 runtime evidence，例如 `newcomer-real-provider-gate.json`；
   - 一个生成报告，例如 `secret-scan-report.json`。
2. 调用 `module.iter_files(tmp_path, module.DEFAULT_PATHS)`，而不是读取 `REPO_ROOT` 或把 `(".sisyphus/evidence",)` 再写一遍。
3. 断言普通 evidence 被纳入、secret scan report 被排除。
4. 保留独立断言 `".sisyphus/evidence" in module.DEFAULT_PATHS`，使默认路径退化能给出直接错误。

这样同时证明“默认路径会到达 runtime evidence”与“报告不会递归污染扫描”，且结果不受开发机、CI 或上一轮验收是否生成文件影响。

### 影响面

- 仅 `backend/tests/unit/test_secret_hygiene_scan.py`。
- 不改变扫描范围、secret pattern、脱敏、release gate 或 report 格式。
- `iter_files` 的 CodeGraph impact 仅为 `scan_paths()` 与 `main()`；本修复无需触碰该链。

### 不可采用方案

- 不得把两个缺失 JSON 提交成空壳 fixture 来维持工作站文件名断言。
- 不得从 `DEFAULT_PATHS` 删除 `.sisyphus/evidence`。
- 不得让 `iter_files()` 只扫描 Git tracked files。
- 不得在 CI 前临时生成两个同名文件。
- 不得 skip/xfail 或把缺失文件视为测试通过条件。

### 聚焦验证

```bash
cd backend
.venv/bin/python -m pytest -c pyproject.toml \
  tests/unit/test_secret_hygiene_scan.py -q --no-cov
```

---

## 2. PPT forbidden word POST 500

### 可复现信号

命令：

```bash
cd backend
PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest -p no:cacheprovider \
  tests/contract/test_ppt_upload.py::TestPPTUploadContract::test_add_forbidden_word \
  -vv -s --no-cov
```

结果：稳定返回 500。完整栈的准确失败位置是：

```text
fastapi.routing.serialize_response
  -> fastapi._compat.v2.serialize_json
  -> pydantic.TypeAdapter.dump_json
  -> PydanticSerializationError:
     Unable to serialize unknown type: <class 'common.db.models.ForbiddenWord'>
```

运行整个相邻 contract 文件结果为 `5 passed, 1 failed`，唯一失败就是该 POST。

### 请求到失败的实际链路

```text
POST /api/v1/admin/presentations/{presentation_id}/forbidden-words
  -> router_registry.register_routers
     mount guard: get_current_admin_user_for_app_routes
  -> admin.api.admin.create_forbidden_word
     endpoint guard: get_current_admin_user
  -> local admin.api.admin.ForbiddenWordCreate
  -> common.db.models.ForbiddenWord
  -> AsyncSession.add / commit / refresh
  -> return SQLAlchemy ForbiddenWord instance
  -> FastAPI response serialization outside handler
  -> PydanticSerializationError
  -> generic middleware 500
```

该路径没有 application service；route 目前同时承担 DTO 归一化、ORM 构造和事务编排。

### 准确的类型 / response model 事实

- `backend/src/admin/api/admin.py:93-97`：请求 DTO 是 route-local `ForbiddenWordCreate`，兼容 `word` 或 `phrase`，并接受 `pattern_type`。
- `backend/src/admin/api/admin.py:554-590`：decorator 只有 `status_code=201`，没有 `response_model`；函数返回注解为 `Any`，实际返回 ORM `ForbiddenWord`。
- runtime route inventory 显示：
  - `response_model = typing.Any`
  - `response_field = ModelField(annotation=Any, mode='serialization')`
  - `endpoint_return = typing.Any`
- runtime/committed OpenAPI 的 201 response 只有一个无类型的 title，没有可消费字段 schema。
- `backend/src/common/db/models.py:872-887`：ORM 字段为字符串 UUID、`phrase`、`suggested_alternative`、`is_regex`。
- `backend/src/common/db/schemas.py:239-253`：已经存在稳定外部 DTO `ForbiddenWordResponse`，启用 `ConfigDict(from_attributes=True)`，字段覆盖 `phrase/suggested_alternative/page_id/word_id/presentation_id/is_regex`。
- 实测 `ForbiddenWordResponse.model_validate(orm)` 能把 ORM 的字符串 UUID 正确输出为 JSON 字符串 UUID；无需创建新 DTO。

### 排名假设与证伪

1. **`Any` response serializer 无法编码 ORM**：预测 DB handler 已完成，异常出现在 FastAPI `serialize_response`；实际完全一致，确认。
2. **数据库 FK/constraint 失败**：预测异常会在 `commit()` 进入 route 的 `except SQLAlchemyError`，并返回 `[ADMIN_FORBIDDEN_WORD_CREATE_FAILED]`；实际 commit/refresh 已完成，栈不含 SQLAlchemyError，证伪为本次 500 根因。
3. **RBAC 拒绝**：预测返回 401/403 且 handler 不执行；测试 token 角色为 admin，既有权限测试绿色，证伪。
4. **请求 DTO 漂移**：预测 422 或 phrase 为空 400；`word="um"` 被 route-local DTO 正常归一化为 `phrase_value="um"`，证伪。

### 根因判定

这是**生产 API 序列化 bug**。

提交 `e0607eb6` 把函数补成 `-> Any` 后，FastAPI 0.138 为它建立了 Pydantic `TypeAdapter[Any]` response field。该 serializer 不会像旧式 `jsonable_encoder` 路径那样自动理解任意 SQLAlchemy 对象。更重要的是，异常发生在 route 返回以后：`await db.commit()` 已成功，因此客户端看到 500 时写入已经落库，重试可能产生重复 forbidden word。

`except SQLAlchemyError` 不能捕获该错误，因为序列化发生在 handler 外；所以当前 `[ADMIN_FORBIDDEN_WORD_CREATE_FAILED]` 统一错误映射也被绕过。

### 测试 fixture 的独立弱点（不是本次 500 根因）

`backend/tests/conftest.py:176-178` 的 `test_presentation_id` 只是随机 UUID，没有插入 `Presentation`。内存 SQLite 未开启 FK enforcement，所以本测试能写入悬空 `presentation_id`；真实 PostgreSQL 会在 FK 处失败。这不会解释当前已确认的序列化栈，但使 contract 测试同时受数据库差异影响，必须修掉。

### 最小生产修复

优先复用现有 DTO，不创建新 envelope 或新 service：

1. 在 admin route 导入 `common.db.schemas.ForbiddenWordResponse`。
2. decorator 显式声明 `response_model=ForbiddenWordResponse`，保留 `status_code=201`。
3. 把返回注解收紧为 `ForbiddenWordResponse | JSONResponse`（或项目接受的等价准确类型），不要再用 `Any`。
4. 在 commit 前把已 flush/refresh 的 ORM 映射为 `ForbiddenWordResponse.model_validate(forbidden_word)`，commit 成功后返回 DTO。这样 DTO/序列化缺陷不会发生在一次成功写入之后。
5. `SQLAlchemyError` 分支先 `await db.rollback()`，再保持现有 `build_server_error("[ADMIN_FORBIDDEN_WORD_CREATE_FAILED]", ...)` 映射。
6. 不改 `get_current_admin_user_for_app_routes` 或 `get_current_admin_user`；两层 admin guard 都保留。

建议的事务顺序：

```text
add -> flush -> refresh -> model_validate DTO -> commit -> return DTO
SQLAlchemyError -> rollback -> build_server_error
```

仅加 `response_model` 已能消除当前异常，但“先 commit、后由框架第一次验证输出”仍保留成功写入后响应失败窗口；显式 DTO 且在 commit 前构造是更完整、仍然很小的根因修复。

### 最小回归测试

重写当前失败 test 的 Arrange/Assert，而不是扩大允许状态码：

1. 使用 `test_db` 与 `test_user` 创建真实 `Presentation`，其 `uploaded_by_admin_id` 指向 admin fixture。
2. POST 该真实 `presentation_id`。
3. 严格断言 `status_code == 201`。
4. 用 `ForbiddenWordResponse.model_validate(response.json())` 校验外部 DTO，并断言：
   - `phrase == "um"`
   - `presentation_id` 等于已创建 Presentation
   - `page_id is None`
   - `is_regex is False`
   - `word_id` 是有效 UUID
5. 查询 DB，确认恰好一条记录与响应 `word_id` 相同。

权限回归保持/补强：非 admin POST 必须是 403，且数据库无新增。现有证据：

- `backend/src/admin/api/security_inventory.py` 把该 POST 列为 admin-only。
- `tests/integration/test_admin_users_api.py::test_admin_router_modules_require_admin_even_without_main_router_guard` 本次实跑 `6 passed`，证明 admin router 自身 guard 未依赖主 app mount。
- `tests/integration/test_presentation_delete_permissions.py::test_presentation_governance_writes_require_admin` 覆盖相邻非 admin forbidden-word write 403。

### 对重叠 presentation route 的影响

CodeGraph 发现 `presentation_coach.api.presentations.add_forbidden_word` 具有同一形状：`-> Any`、无 response model、commit 后返回同一 ORM。runtime inventory 也显示它的 `response_model=typing.Any`。因此它是同类潜在 500。

最窄修复可以先处理当前失败的 admin route；若 Gate 0B 要声明 forbidden-word create contract 真正闭环，应在同一小切片让两个 POST 都复用 `ForbiddenWordResponse`，并分别保留各自 request DTO、URL 和权限语义。不要借此重构整个 legacy presentation CRUD。

### OpenAPI / 兼容性影响

显式 response model 会把当前无类型的 201 schema 收紧为 `ForbiddenWordResponse`。字段都是 ORM 已有公开字段，是 additive contract clarification，不改变 URL、method、status、认证或请求 body。

必须通过生成器同步 committed OpenAPI，不得手改 YAML：

```bash
cd backend
.venv/bin/python scripts/generate_openapi_contract.py
.venv/bin/python scripts/generate_openapi_contract.py --check
```

### 不可采用方案

- 不得把 500 加入 `assert response.status_code in [...]`。
- 不得删除 201 body 或改成空 `Response` 来躲过序列化。
- 不得用手写 dict 复制 `ForbiddenWordResponse` 字段，形成第二份 DTO。
- 不得移除 `-> Any` 后依赖旧框架的隐式 `jsonable_encoder` 行为。
- 不得放宽 admin 权限或移除 endpoint/mount guard。
- 不得吞掉 `PydanticSerializationError`；那会保留“写成功但客户端收到失败”的重复写风险。
- 不得用随机、未持久化的 presentation UUID 继续证明成功路径。
- 不得手工编辑 committed OpenAPI。

### 聚焦验证

```bash
cd backend

# 精确回归与相邻 contract
.venv/bin/python -m pytest -c pyproject.toml \
  tests/contract/test_ppt_upload.py::TestPPTUploadContract::test_add_forbidden_word \
  -q --no-cov
.venv/bin/python -m pytest -c pyproject.toml \
  tests/contract/test_ppt_upload.py -q --no-cov

# 权限不退化
.venv/bin/python -m pytest -c pyproject.toml \
  tests/integration/test_admin_users_api.py::test_admin_router_modules_require_admin_even_without_main_router_guard \
  tests/integration/test_presentation_delete_permissions.py::test_presentation_governance_writes_require_admin \
  -q --no-cov

# schema 与静态检查
.venv/bin/python scripts/generate_openapi_contract.py --check
.venv/bin/python -m ruff check \
  src/admin/api/admin.py \
  src/presentation_coach/api/presentations.py \
  tests/contract/test_ppt_upload.py \
  tests/unit/test_secret_hygiene_scan.py

# Gate 0B 最终范围
.venv/bin/python -m pytest -c pyproject.toml tests/unit tests/contract -q --no-cov
```

## 最终判定

- Secret 失败：只修测试的环境耦合；scanner 默认路径与 report 排除生产合同保持不变。
- Forbidden-word 失败：修生产输出边界，并把成功测试从“允许多个状态”收紧为真实 DB fixture 上的 201 + DTO + persistence contract。
- 两项都不能通过扩大允许码、跳过、伪造 evidence 或依赖工作站状态来变绿。
