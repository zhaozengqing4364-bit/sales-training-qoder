# 设计产物审计：首发 baseline 与全数据面 reset

## 结论

PRD 方向可实施，但在编码前修正了 6 个会导致伪安全或长期返工的问题：

1. 配置恢复原先排在管理员 bootstrap 前，无法稳定重映射配置审计人；已调整为系统 seed → 管理员 → 配置恢复。
2. “测试后续 revision”容易把伪 migration 留进活动路径；已限定为隔离临时目录中的演进性测试。
3. “后台角色”与“学员数据范围”容易混为一谈；已明确只有平台管理员全局，训练经理按显式 Team，其他后台角色默认 fail closed。
4. Redis 通用缓存没有仓库级统一 namespace，直接 `flushdb()` 可能误删共享 key；已拆分项目独占 DB 与共享 DB 两种模式。
5. 本地存储存在多套 PPT/Chroma 默认路径；已要求解析后的显式 allowlist 与符号链接逃逸检查。
6. 当前配置的 PostgreSQL 连接认证失败；真实 apply 在取得可验证连接和目标指纹前硬阻塞，隔离实现与测试可继续。

## 证据与状态

| 主题 | 仓库证据 | 审计状态 |
|---|---|---|
| 旧 migration 空库不可用 | root revision 假设基础表存在，隔离升级失败 | 已证实问题 |
| runtime schema repair | `common.db.session.init_db()` 执行 `create_all()` 和 `_ensure_*` | 待实现移除 |
| metadata 注册 | Alembic 通过散落 import 注册外部模型，测试另有一套 import | 待统一根入口 |
| 用户 department | ORM、API、页面、训练查询仍有引用 | 待跨层移除 |
| Team policy | 已有显式关系与 fail-closed policy，但只识别单一训练经理角色 | 待收敛角色合同 |
| 登录 fallback | 无 hash 用户仍可读共享密码/用户映射 env | 待停用读取，配置值保留 |
| Redis | session key 默认 `ws:session_state:`；通用 cache key 任意且支持 `flushdb()` | 必须专用 cleaner |
| Chroma | `./data/chromadb` 与 `./data/chroma` 两个配置入口 | 必须去重盘点 |
| 本地 PPT | `./data/presentations`、`./data/ppts`、`/data/uploads` 等并存 | 必须 allowlist |
| COS/OSS key | `audio/`、`sales-trainer/audio/`、`sales-trainer/materials/`、`newcomer-assignments/` | 可形成 prefix 白名单 |
| Team 就地处理 | 已有 `/admin/teams` WIP 页面和服务 | 复用，不另造页面 |

## 一致性检查

- PRD、技术设计和验收均以 Alembic 为唯一 schema authority。
- “保留配置”不等于保留业务历史：只恢复注册白名单，且使用逻辑键/依赖拓扑。
- “清完整项目数据面”不等于清共享服务：每个 cleaner 都必须携带 scope 和独立 verify。
- “配置值不移除”与“登录不再读取共享密码”并不冲突：env/Secret 原样保留，认证代码停止把它作为凭证权威。
- 用户 department 完全移除；内容 department 标签保留并通过权限隔离测试证明不影响范围。

## 未解决但不阻塞编码的未知项

- 实际开发 PostgreSQL 的有效凭证和最终目标指纹。
- Redis 当前 DB 是否项目独占；未证明前按 shared DB 处理。
- COS 是否还存在代码未覆盖的历史 prefix；apply 前必须通过对象清单审阅确认。
- 哪些系统字典为“启动必需”需要通过空库 smoke 反推，不能把现有业务数据误当 seed。

这些未知项均被设计成 apply 前门禁，不要求现在猜测。
