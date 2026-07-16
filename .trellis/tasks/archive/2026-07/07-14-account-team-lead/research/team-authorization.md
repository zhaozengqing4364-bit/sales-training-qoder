# 销售团队建模与组长授权范围

## Comparable patterns

### 1. Microsoft Entra 用户/群组分配

* 应用访问和角色可分配给明确用户或群组，只有被分配主体获得访问。
* 群组成员变化可以统一驱动授权变化，便于审计和撤权。
* 属性过滤可辅助确定同步范围，但正式授权通常以显式分配为主。

来源：

* https://learn.microsoft.com/en-us/entra/identity/enterprise-apps/assign-user-or-group-access-portal
* https://learn.microsoft.com/en-us/entra/identity/app-provisioning/how-provisioning-works

### 2. GitHub Organizations Teams

* Team 是独立资源，成员、维护者和访问权限围绕 Team 建模，而不是依赖用户资料中的部门字符串。
* Team 有独立页面；维护者在团队上下文内管理成员和资源。
* 支持父子团队和权限继承，说明组织层级可以在未来扩展，但 MVP 可先保持单层。

来源：https://docs.github.com/en/organizations/organizing-members-into-teams/about-teams

### 3. Relationship-Based Access Control（OpenFGA 模式）

* 授权表达为主体与资源之间的关系，例如 `user is leader of team`、`learner is member of team`。
* 关系模型比全局角色或单一属性更适合对象级范围控制。
* OpenFGA 是独立授权服务；本项目当前规模不必引入新基础设施，但可在本地数据模型中采用相同关系思想。

来源：https://openfga.dev/docs/fga

## Common conventions

* 全局角色只描述“能做哪类事”，团队成员关系描述“可以对哪些对象做”。
* 团队、成员关系和组长关系必须是可审计的独立记录，包含生效/失效时间。
* 后端对每个学员、任务、审核、证据对象做范围校验；前端导航只改善体验，不承担安全职责。
* 调组和撤销组长权限必须立即影响读取和写入范围；历史训练记录仍保留原始团队快照或审计关联。
* 组长操作应尽量在 Team 页面上下文内完成，平台管理员保留全局治理能力。

## Mapping to this repository

* 当前 `User.department` 是自由文本，适合展示属性，不适合作为唯一授权关系。
* 当前已有 `training_manager`、readiness、training task 和 supervisor 能力，但各自使用不同角色集合。
* `/team` 已经是合适的业务入口，可把现有主管能力按对象级范围组合进来，而不是复制一套业务规则。
* 当前系统为单企业内部应用，没有证据需要外部 FGA 服务；数据库显式关系 + 集中的 policy/service 足够支撑 MVP。

## Feasible approaches

### A. 显式 Team + TeamMembership + TeamLeaderAssignment（推荐）

* Team 是稳定业务对象；成员关系与组长关系分开，支持多组长、代理和生效区间。
* `training_manager` 作为能力角色；具体可见范围由 leader assignment 决定。
* 优点：权限准确、可审计、支持调组和未来层级扩展。
* 代价：需要 migration、旧部门数据回填和统一权限服务。

### B. Department + manager mapping 过渡

* 保留部门字符串，新增“组长—部门”映射，以此替代当前直接取本人部门。
* 优点：改动较小。
* 代价：仍无法表达一个部门多个小组、跨部门团队、多人兼任和名称变更，后续必然再次迁移。

### C. 引入外部 FGA 服务

* 将团队关系和权限规则迁入 OpenFGA 类服务。
* 优点：长期复杂授权扩展能力强。
* 代价：新增基础设施、可用性和运维负担；当前明显过度设计。

## Recommendation

MVP 采用 A，但先实现单层团队，不做父子团队和复杂继承；所有训练、审核和主管能力复用现有 application service，并在入口处统一调用团队范围 policy。
