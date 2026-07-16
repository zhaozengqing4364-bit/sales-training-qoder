# Alembic 空库基线研究

## 研究问题

在项目尚未发布、所有历史数据都可清除时，应如何让当前数据库从完全空白状态可靠初始化，同时保留后续 Alembic 演进能力？

## 官方约定

1. Alembic 官方允许两种新库构建思路：完整执行 revision 链，或由完整 SQLAlchemy metadata 执行 `create_all()` 后再 `stamp head`。官方还明确说明，当旧 revision 已不再对应任何现存环境时，可以裁剪旧 migration，并把最早保留 revision 的 `down_revision` 设为 `None`。
2. `stamp` 只修改 Alembic version table，不执行 migration，因此只能在 schema 已经与目标 revision 严格一致时使用。
3. autogenerate 只是候选生成器，必须人工复核；表/列重命名、部分约束、特殊类型和 server default 等不能仅依靠自动检测。
4. `alembic check` 可以用于 CI 检测 ORM metadata 与已应用 migration 是否仍有待生成的差异，但它继承 autogenerate 的能力边界。

官方资料：

* [Alembic Cookbook — Building an Up to Date Database from Scratch](https://alembic.sqlalchemy.org/en/latest/cookbook.html#building-an-up-to-date-database-from-scratch)
* [Alembic — Auto Generating Migrations](https://alembic.sqlalchemy.org/en/latest/autogenerate.html)
* [Alembic Commands — stamp / upgrade](https://alembic.sqlalchemy.org/en/latest/api/commands.html)

## 当前仓库事实

* 当前 revision 图只有一个 head：`20260714_1600_095`。
* 第一条 revision `001` 的 `down_revision=None`，但它直接外键引用 `users`，并对 `practice_sessions` 执行 `add_column`；这两张基础表没有由任何 Alembic revision 创建。
* 在隔离的空 SQLite 数据库上实跑 `alembic upgrade head`，第一条 migration 以 `no such table: practice_sessions` 失败。这证明当前 revision 链不具备空库启动能力。
* `backend/reset_db.py` 直接 `Base.metadata.drop_all/create_all`，没有环境白名单、dry-run、目标指纹、Alembic stamp 或外部存储清理。
* 在隔离数据库上实跑该脚本也失败：只导入 `common.db.models.Base` 时 metadata 缺少 `practice_templates`，无法解析 `practice_sessions.practice_template_id` 外键。
* 即使修复 metadata 导入，单独 `create_all()` 而不 stamp 也会让下一次 `alembic upgrade head` 从 `001` 重放并与现有表冲突。
* 数据边界不止 PostgreSQL：还包括 Redis session/cache、Chroma `./data/chromadb`、文档 `./data/documents`、音频 `./data/audio`、演示文稿目录、销售训练材料/音频/作业目录，以及可选 COS 对象。
* `bootstrap_auth_admin.py` 只创建用户基本字段，不创建受管密码哈希；新空库若继续使用它，会重新依赖共享密码兼容路径。

## 可行方案

### 方案 A：建立新的首发 Alembic baseline（推荐）

* 将当前旧 revision 链归档为历史证据，不再作为新环境执行链。
* 修复完整 metadata 注册，生成并人工复核一个从空 PostgreSQL 创建全部当前 schema 的 baseline revision。
* 新 baseline 的 `down_revision=None`，后续所有 migration 从它继续。
* 单独提供 bootstrap/seed 命令创建最小管理员、显式团队和首发训练资产。

优点：Alembic 继续是唯一 schema authority；空库行为可直接测试；无需维持从未发布的历史兼容路径；最符合当前“可以全部清空”的条件。

缺点：需要认真复核约束、索引、PostgreSQL 类型、server default 和 metadata 完整性；旧开发库不能原地升级，必须全部重建。

### 方案 B：补齐旧 revision 链

* 在 `001` 前新增 legacy foundation revision，创建 users、practice_sessions 等全部前置表。
* 修复后续 95 个 revision 在空 PostgreSQL 上的顺序、分支、数据回填和 dialect 假设。

优点：保留完整演进历史。

缺点：没有已发布环境需要这段升级历史；验证成本最高，且会继续保留过渡 schema 和历史数据兼容逻辑。当前条件下收益很低。

### 方案 C：`create_all()` + `stamp head`

* 使用完整 metadata 一次性建表，然后 `alembic stamp head`。
* 后续 migration 仍从当前 head 继续。

优点：官方支持，执行速度快。

缺点：仓库当前 metadata 注册已经被实测证明不完整；容易让 ORM metadata 成为隐含的第二套 schema authority；无法从 migration 文件独立审查完整首发结构。若选用，必须先建立 metadata 完整性和 schema parity 测试。

## 结论

由于系统尚未发布、旧数据可全部舍弃，而当前 migration 链又已经被实测证明不能从空库运行，方案 A 的总风险和总工时最低。清库不应只理解为删除 PostgreSQL 表，而应建立一个带环境护栏的“reset → baseline upgrade → bootstrap → verify”控制面；外部存储是否一起清除应由显式 scope 决定。
