# 实施记录

## Deviations

- Trellis 配置默认允许 sub-agent，但用户明确要求本任务不派出子代理；本任务由当前 agent 单独实施与复核。
- 工作区在任务开始前已有大量未提交改动，包括账号、Team、批量开户和新人训练链路；所有改动按用户资产处理，禁止重置或覆盖，逐文件合并。
- 任务初期真实 reset 目标没有显式 `DATABASE_URL`，只读 `inspect` 按设计以 `[RESET_DATABASE_URL_MISSING]` fail closed。取得用户授权后，在不删除任何已有 endpoint、密钥、模型名或 API key 的前提下补齐 development 目标和 reset scope，再执行真实数据面 `apply`。

## Decisions during implementation

- 将 Alembic 活动历史收敛为单一首发 baseline `20260715_0000_001`；98 个旧物理 revision 文件（主编号到 `095`，包含历史分支/merge/同号变体）只读归档，不允许新库执行旧链，也不支持旧开发库原地升级。
- `common.db.models` 保持兼容导入门面，实际 ORM 定义按职责拆入 `common.db.model_registry`；Alembic 与测试从同一权威注册表加载，避免重复模型身份。
- 应用启动只校验数据库处于精确 Alembic head，空库、旧 head、未来 head 或分叉均 fail closed；彻底移除启动修复、`create_all()` 建库和绕过 Alembic 的旧 reset/repair 脚本。
- reset 采用 manifest 驱动的阶段状态机：先配置快照，再清外部数据面和 PostgreSQL，随后 Alembic、最小系统 seed、临时管理员、配置恢复、独立验证。已完成阶段在同一授权 manifest 重试时跳过。
- Redis 默认只允许显式 prefix；只有显式声明项目独占 DB 才允许 DB 级清理。COS 配置存在时必须提供非空项目 prefix，永不使用 bucket 级清理。
- 配置快照保持逻辑键、原 ciphertext、内容校验和与 encryption-key 指纹；环境中的 endpoint、模型名、API key、密钥和连接配置不读取到报告、不删除、不改写。
- 用户组织/数据范围以 Team 关系和集中式 policy 为唯一权威，删除 `User.department`；内容对象“适用部门”仅保留为分类标签。
- 首发账号只接受受管密码哈希。共享密码环境变量原样保留，但认证路径不再读取；临时管理员必须首次改密。
- 修复首次改密接口的真实 Bearer 契约：在浏览器 cookie 缺失时，`Authorization: Bearer` 现在能被路由显式注入并传给统一身份解析器。
- `REDIS_URL` 与 `SESSION_STATE_REDIS_URL` 原先分别使用 `127.0.0.1` 和 `localhost` 指向同一个物理 Redis DB，盘点会产生两个逻辑 scope；将二者规范为相同 endpoint 后只保留一个共享 DB/prefix cleaner，避免重复执行和审计歧义。
- 独立验证器必须覆盖管理员凭证生命周期：reset 刚完成时接受 `temporary`；首次改密后接受带 `password_changed_at` 的 `active`；其余状态继续 fail closed。
- 真实启动留证发现 `scripts/dev-up.sh` 的摘要会回显带 userinfo 的 `DATABASE_URL`/`REDIS_URL`；新增统一 URL userinfo 脱敏并补回归测试，现有控制日志已用脱敏摘要覆盖。
- 远程浏览器登录超时不是密码、PostgreSQL 或认证服务问题：浏览器与前端 `3445` 存在真实连接，但原配置要求浏览器直连后端 `3444`，后端没有收到该远程登录连接，前端在 8 秒后按请求超时退出。浏览器 HTTP 改为同源 `3445/api/v1`，由 Next.js rewrite 转发至内部 `127.0.0.1:3444/api/v1`；服务端会话校验单独使用 `SERVER_API_URL`，避免自代理并保证职责清晰。
- 同源 API 切换后，管理首页原有健康检查会从 API 根路径推导 `/health`；为保持该契约，额外将前端 `/health` 同源转发至后端健康端点。配置、模型名、API key、数据库/Redis/COS 连接信息均未删除或改写。
- 同一远程端口问题也会影响核心训练 WebSocket，因此没有停在“登录能用”：`NEXT_PUBLIC_WS_URL` 同步切换到前端同源入口，运行时按当前页面主机、端口和协议解析，`/ws/*` 的 WebSocket upgrade 复用 Next.js rewrite 转发到内部后端。
- “团队与成员”实测确认数据库和接口不是当前卡顿源：空业务库下三条首屏 API 均约 17–27ms，无长任务或控制台错误；主要等待来自侧栏全局关闭预取后，点击才串行发生 RSC、页面 chunk 和客户端数据请求。仅给该高频入口启用 Next 路由预取，并关闭落地页“返回用户管理”的无意反向预取，避免恢复侧栏全量预取风暴。
- Browser plugin 当前不可用；性能复现与修复后验收使用仓库 Playwright 依赖和真实 production Chromium。缺失的 Chromium 动态库仅解包到用户缓存，未改系统包或项目依赖。

## Verification ledger

- 隔离 PostgreSQL（临时端口 `55432`）完成空库 `upgrade -> downgrade base -> upgrade`；`alembic heads` 单 head，`alembic current` 为 `20260715_0000_001`，`alembic check` 无差异。
- 在隔离复制的 Alembic 目录生成临时 `20260715_0000_002`，完成 baseline 到后续 revision 的升级、降回 baseline、再次升级；临时 revision 未进入仓库活动历史。
- 隔离 Redis DB 14、Chroma 和本地 fixture 目录连续完成两次 `inspect -> dry-run -> apply -> verify`。每次盘点识别 102 张 PostgreSQL 表（101 张业务表加 Alembic 表）、2 个 Redis key 和 fixture 文件；两次最终 `schema_head`、配置 fingerprint、管理员数量和业务表空状态一致。
- 第二次 apply 在管理员输入校验阶段故意形成中途失败；保留相同 manifest/快照/令牌修正输入后从失败阶段继续，未重复已完成清理，最终独立验证通过。阶段重试代码另补单测，完成态会清除旧 `failed_at/error_code`，避免审计状态自相矛盾。
- 两次 reset 后均只存在一个指定临时管理员，业务表为空；模型、RAG、全局语音、Prompt、已发布业务规则和评分规则各恢复 1 条，配置指纹与快照一致。隔离范围内 Redis、Chroma、本地目录为空。
- 隔离 HTTP 启动日志确认精确 Alembic head、`ddl_executed=false`、恢复后的模型配置可加载、健康检查 ready。
- 临时管理员登录返回 `requires_password_change=true`；清除 cookie 后使用 Bearer 完成首次改密，旧密码随后 401，新密码登录成功且 `requires_password_change=false`、凭证版本递增。
- 对已恢复配置再次连续执行两次最小 system seed，两次均为 `created=0, existing=36`，配置 fingerprint 前后不变，证明 seed 不重复且不覆盖用户配置。
- 后端全量 Ruff 通过；Mypy 对 670 个 source files 通过。首发关键 integration 共 89 passed；reset 阶段恢复与 encryption-key/tamper 安全新增 7 个聚焦测试通过。
- 后端全量 unit + contract 自然退出 0：3126 passed、1 skipped、76 warnings，coverage 68.71%，用时 755.83s；该全量进程启动后新增的 reset 增量测试另行 7/7 通过。
- 前端全量 Vitest 为 192 files passed、1157 passed、6 skipped；`tsc --noEmit`、ESLint（0 error，80 个既有 warning）和 Next.js production build 均通过，构建完成 89 个静态页面数据生成单元。
- development 真实目标执行前已停止 3444/3445 写入进程，并在仓库外 `0700` 控制目录生成 mode `0600` 的 PostgreSQL custom dump；备份大小 1,942,916 bytes，SHA-256 为 `c7cbbb1acf5112c33aca1df0b932bbba85c705085ae3fcf86dade3c05bba9533`，`pg_restore --list` 可读。
- 真实 dry-run 目标为 PostgreSQL `sales_training@127.0.0.1:5432`、Redis DB 0 的四个明确前缀、两个 Chroma 路径、11 个本地 allowlist 路径和三个 COS prefix；plan checksum 为 `6ebc5bb99c34b39f0c5ab0a2f6dfc7802fb8bc20709e7d02ed2b6a87854b9a30`，target fingerprint 为 `d073a7a8498152534b7289f330104b8ed208c039483e73faea9a15c88f5ccd64`。
- 真实 apply 自然退出 0：删除 COS `sales-trainer/audio/` 下 15 个对象；清空 1 个 Chroma root 和 4 个存在数据的本地 root；Redis 四个项目 prefix 原本均为 0 key，未调用 `FLUSHDB/FLUSHALL`；PostgreSQL 107 张旧表被重建为首发 baseline。
- COS 首次真实盘点暴露 SDK 方法名错误：当前 qcloud COS SDK 提供 `list_objects` 而不是 `get_bucket`。修正后真实 list/delete/verify 均通过，并补充聚焦单测。
- 配置快照共 7 个 section；恢复 2 个 model config、0 个 RAG profile、1 个全局 voice profile、2 个 Prompt、1 个已发布业务规则和 1 个评分规则。最终配置 fingerprint 为 `26e1d55393d92f544698cef13d57922d0e2c7b23df95283ff38ec3510c793e94`，与快照一致。
- 唯一管理员 `admin@qoder.ai` 先以一次性凭证登录并返回 `requires_password_change=true`，随后真实完成首次改密；旧密码 401，新密码登录 200 且 `requires_password_change=false`。最终凭证只保存在仓库外 mode `0600` 文件中。
- 两个恢复后的 LLM 配置 `deepseek-v4-flash` 与 `deepseek-v4-pro` 均完成真实 Provider smoke，分别约 870ms 和 946ms；结果证据不包含 endpoint、ciphertext 或 API key。
- 最终独立 verify 在首次改密后再次通过：Alembic head `20260715_0000_001`、管理员 1、业务表为空、Redis/Chroma/local/COS 全部 clean。后端 `/health` ready 且 database ok，前端返回 HTTP 200；真实库 `alembic check` 为 `No new upgrade operations detected`。
- 最终可用性 smoke：正式管理员登录 200、`requires_password_change=false`、role=`admin`；管理员模型配置 API 返回 2 条恢复配置，Team API 返回 200 且初始团队数为 0，符合“无演示业务数据”的首发基线。
- 最终增量复核：launch-reset/COS/auth 69 passed，dev-up 6 passed，secret hygiene 10 passed；Ruff 通过，Mypy 670 个 source files 通过，`bash -n scripts/dev-up.sh` 与 `git diff --check` 通过。此前同一任务的全量后端 unit+contract、关键 integration、前端 Vitest/tsc/ESLint/build 结果继续有效。
- 登录超时回归先红后绿：Next rewrite、服务端会话内部 URL 和 dev-up 默认代理测试在修复前分别失败，修复后前端聚焦 46 passed、dev-up 7 passed，`tsc --noEmit`、聚焦 ESLint、shell 语法和 Next.js 生产构建通过。
- 真实 Chromium 从 `http://186.241.123.157:3445/login` 完成账号密码登录，`POST /api/v1/auth/login` 200，进入首页后刷新仍保持会话，再进入 `/admin`；`/health` 200 且页面显示“后端在线”。最终轮次 HTTP 4xx/5xx、控制台 warning/error 和非导航网络失败均为 0；`app_session`/`app_csrf` 均绑定前端主机。
- 公网入口最终以 `scripts/app-up.sh` 的 Next.js production runtime 运行。真实浏览器通过 `ws://186.241.123.157:3445/ws/sales` 完成 WebSocket upgrade；故意传入非法 session 后由后端语义化关闭 `4400 / INVALID_SESSION_ID`，而不是代理层 `1006`，证明同源 WebSocket 转发已贯通。最终聚焦前端 55 passed，受影响的 practice/exam WebSocket 链路另 111 passed。
- 团队页性能基线：公网 production 本机回环视角 3 次侧栏点击到可用为 210–260ms；模拟 500Kbps、300ms RTT、4x CPU 时为 1,528ms。三条业务请求并行，无 N+1；聚焦性能契约先得到 2 个预期失败（高频入口未预取、反向链接意外预取），实现后 11/11 通过。
