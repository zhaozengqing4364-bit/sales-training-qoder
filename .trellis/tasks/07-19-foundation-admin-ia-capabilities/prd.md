# 新人训练管理端信息架构与权限可发现性

## Goal

保留 `/admin/newcomer-training` 作为唯一产品入口，同时把训练方案、内容、题库、讲解评分、AI 教练和客户场景做成清晰、稳定、按权限可发现的内部工作区，解决“管理端只有一个新人训练工作台、配置入口不知道在哪里”的问题。

## Dependencies

- `07-19-foundation-authoring-contract-inventory` 冻结 capability。
- 多媒体、题库、录音评分、Coach、异步场景任务的目标路由与页面对象已经稳定；不得用空白占位页伪造完成。

## Information Architecture

全局管理侧边栏保留一个“新人训练”入口；进入后使用持久的本地导航表达：

1. 总览与待办；
2. 训练方案（路径与版本）；
3. 内容中心；
4. 题库与测验；
5. 讲解与评分；
6. AI 教练；
7. 客户场景；
8. 学员与班级；
9. 评测与复核；
10. 发布与治理。

桌面端使用稳定的本地侧栏或等价清晰结构；窄屏使用可访问的模块选择器。不得继续依赖可横向溢出、难发现的 Tab 列表，也不得退化为九宫格卡片导航。

## Page Contract

当培训团队进入新人训练管理端时，帮助其在三秒内判断当前负责的对象、待办和下一步，并能从稳定导航进入对应配置或运营工作区；无编辑权限时得到可理解的只读/申请权限状态，而不是误以为功能不存在或数据为空。

## Requirements

### R1. 后端 Capability Projection

- 后端返回 view/edit/review/publish 等动作级 capability 和 organization/object scope。
- 前端禁止基于 role string 复制权限矩阵。
- 区分“不可见产品”“可查看不可编辑”“可编辑不可发布”“可发布/回滚”。
- 无 view capability 不请求敏感数据；直接访问 URL 仍由后端对象级权限拒绝。

建议默认：

- Content Editor：内容、题库编辑/审核；
- Training Admin：路径、录音评分、Coach、场景、班级、发布；
- Training Manager：总览、学员、评测、复核，并可按策略只读查看已发布训练配置；
- Platform/System Admin：全部业务 capability 与受控治理能力；
- 密钥、Provider 原文和高风险系统策略继续单独授权。

最终映射以合同任务冻结结果为准。

### R2. 导航与路由

- 每个模块有稳定 URL、标题、任务说明和当前主操作。
- 根路由根据 capability 和待办进入总览，不把所有用户强制重定向到内容或路径。
- `/resources` 等历史 Foundation 别名只做有期限、可测试的路由兼容；最终链接使用业务名称。
- 浏览器刷新、深链和返回保持当前模块、筛选和对象上下文。
- Legacy `/admin/sales-trainer/*` 不重新加入新人训练导航。

### R3. 总览与空状态

- 总览展示真实待审核候选、缺失发布依赖、失败任务、待复核和即将到期项。
- 每项说明对象、原因、影响和下一步；不增加无行动价值的 KPI/图表或“AI 洞察”。
- 首次无内容时给出“创建首个训练方案/导入材料”的正确动作；无权限与没有数据分开。

### R4. 模块页一致性

- 列表页统一搜索、筛选、服务端分页、状态标签和创建动作位置。
- 详情页统一身份、状态、工作修订/已发布修订、引用、历史和高风险动作。
- 普通用户语言统一：内容、题目、测验、讲解材料、评分方案、教练配置、客户场景、训练方案、发布。
- 不展示 `E2E`、`seed`、`mock`、`Prompt`、`traceId`、raw JSON、数据库 ID 或原始枚举。

### R5. 状态、可访问性与响应式

- 本地导航支持键盘、可见焦点、当前项语义和跳过导航。
- 页面覆盖 loading、empty、no-result、error、permission denied、stale、partial、submitting 和 recovery。
- 360px 与 200% zoom 下不丢模块和主操作；长中文、长文件名和多状态不破版。
- 权限变化或组织切换清除不再合法的缓存，不短暂显示敏感内容。

## Acceptance Criteria

- [ ] 全局只保留一个“新人训练”产品入口，但授权管理员进入后能直接看到其全部业务模块。
- [ ] 内容编辑能找到内容/题库；训练管理员能找到路径/讲解评分/Coach/场景/发布；经理能找到学员/评测/复核。
- [ ] 无编辑权限的可查看用户看到明确只读状态；无查看权限不加载数据且直接 URL 被后端拒绝。
- [ ] 页面刷新、深链、返回和窄屏模块切换保持正确上下文。
- [ ] 总览基于真实可行动数据，不是卡片目录或虚构指标。
- [ ] Legacy 页面不重新成为导航或业务权威。
- [ ] 键盘、焦点、360px、200% zoom、长文本和权限切换经过实际渲染验证。

## Minimal Verification

- 后端 capability 矩阵与跨组织/对象级权限集成测试。
- 前端导航投影、深链、权限变化、无权限和状态组件测试。
- 针对性浏览器测试覆盖四类管理员角色、桌面/窄屏和直接 URL。
- 只运行管理导航与 Foundation capability 相关 Vitest/Playwright、TS/ESLint；不跑全站 E2E。

## Out of Scope

- 不重新设计全局视觉系统或其他管理产品导航。
- 不在本任务实现资源 CRUD、路径逻辑或数据迁移。
- 不通过扩大默认权限解决可发现性；权限变更必须有业务合同依据。

## Risk And Rollback

- 风险等级：P2（导航与权限投影；后端权限仍为安全边界）。
- 新本地导航可回退到现有 workspace nav；直接业务 URL 与后端 capability 不受回退影响。

## Likely Areas

- `web/src/components/layout/admin-sidebar.tsx`、`admin-shell.tsx`；
- `web/src/components/admin/newcomer-training/workspace-nav.tsx`、管理 layout/routes；
- `backend/src/foundation_admin_permissions.py` 与 capability projection；
- `web/src/lib/api/types/foundation-admin.ts` 和对应 ViewModel。

## Execution Constraints

遵守父任务 [`execution-policy.md`](../07-19-newcomer-training-content-authoring-closure/execution-policy.md)，不顺带调整其他产品导航。

