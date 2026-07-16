# 企业内部账号开通与批量导入模式

## Comparable patterns

### 1. 企业身份源同步（Microsoft Entra / SCIM）

* Microsoft Entra 通过 SCIM 创建、更新、停用用户及群组，并强调使用稳定匹配属性和明确的属性映射。
* 常见范围控制是“已分配用户/群组”，成员离开范围后触发去配置或停用，而不是保留失效权限。
* 适合身份源已经成熟、希望长期自动同步的企业；初期接入成本高于本地导入。

来源：

* https://learn.microsoft.com/en-us/entra/identity/app-provisioning/how-provisioning-works
* https://learn.microsoft.com/en-us/entra/identity/app-provisioning/use-scim-to-provision-users-and-groups

### 2. 组织邀请（Auth0 Organizations）

* 邀请发送给指定邮箱，接受邀请时必须使用被邀请邮箱登录或创建账号。
* 应用需要有明确的邀请接受路由，将邀请票据与组织上下文带入认证流程。
* 适合管理员先分配组织/团队/角色，用户再证明邮箱所有权并激活账号。

来源：https://auth0.com/docs/manage-users/organizations/configure-organizations/invite-members

### 3. 临时密码（Amazon Cognito AdminCreateUser）

* 管理员创建用户后发送欢迎消息和临时密码。
* 用户处于 `FORCE_CHANGE_PASSWORD` 状态，首次登录必须设置新密码。
* 支持重发并重置临时密码有效期，但管理员和通知渠道会接触一次性密码，治理成本更高。

来源：https://docs.aws.amazon.com/cognito-user-identity-pools/latest/APIReference/API_AdminCreateUser.html

### 4. 批量操作（SCIM 2.0 Bulk）

* 每个操作拥有请求内唯一 `bulkId`，响应逐项返回状态和错误详情。
* 默认尽可能继续处理部分成功，可通过 `failOnErrors` 控制停止阈值。
* 可在同一批次中建立新用户与新群组之间的引用，说明批次必须保留客户端行标识和依赖顺序。

来源：https://www.rfc-editor.org/rfc/rfc7644.html#section-3.7

## Common conventions

* 将“账号创建”和“身份激活”分开建模，至少区分 invited、active、suspended、expired。
* 不让管理员设置或知晓用户长期密码；邀请票据和临时密码必须单次、短期、可撤销。
* 批量操作先校验/预览，再确认执行；每一行有稳定客户端标识、结果状态和可重试语义。
* 邮箱、企业身份 ID、员工编号使用归一化后的稳定唯一键。
* 调岗、离职或离开授权范围必须触发权限撤销/停用，并留下审计记录。

## Mapping to this repository

* 已有企业微信登录，可作为正式身份主通道；已有密码重置令牌能力，可复用安全票据、过期和单次消费机制。
* 当前缺少账号生命周期状态和正式通知通道；后台创建密码未持久化，不应在此基础上继续扩展管理员设置长期密码。
* 当前规模尚不需要完整实现 SCIM 协议，但本地导入批次应借鉴 SCIM 的逐项标识、部分失败和结果映射。
* 后续若企业微信通讯录或其他 HR/IdP 成为权威来源，可在独立连接器层增加同步，不必改变应用内 User/Team 契约。

## Feasible approaches

### A. 企业微信优先 + 邀请激活兜底（推荐）

* 批量导入先创建 pending identity、团队成员关系和角色分配。
* 企业微信身份匹配成功后直接激活；未匹配人员通过邮件或受控邀请链接完成身份绑定/设密。
* 优点：符合现有架构，不暴露长期密码，兼容当前未完全接入企业微信的人员。
* 代价：需要账号状态、邀请票据、正式通知适配器和身份绑定冲突处理。

### B. 纯邀请激活

* 所有用户通过邮箱邀请完成激活与设密，企业微信只作为后续可绑定登录方式。
* 优点：流程统一，容易解释和测试。
* 代价：依赖正式邮件服务，企业微信用户多走一步。

### C. 管理员临时密码

* 系统生成一次性临时密码，首次登录强制改密。
* 优点：实现路径较短，适合短期内部试运行。
* 代价：密码传递、泄露、过期、重发和客服成本最高，不建议作为长期方案。

## Recommendation

MVP 采用 A；批量导入实现本地 `ProvisioningBatch + ProvisioningRow`，不在本期实现完整 SCIM endpoint，但保持未来连接器可以调用同一 application service。
