# /admin/settings 视觉分析

**wave**: admin | **截图数**: 1
**截图清单**：
- `screenshots/admin/admin-settings-1440.png` — 系统设置

**a11y 树要点**：
- 1 H1: "系统设置"
- 5 sub-tab: 常规/安全/通知/模型/治理矩阵
- 表单 + 区域设置
- 0 console error

---

## P0
- 无

## P1（1 周内）

### P1-1：表单 0 inline 错误反馈（同跨项目 P0-8）
- 平台名称/支持邮箱/欢迎语/默认语言等都是 input
- 修改后无明确"已保存"反馈
- 修复：项目级表单状态机（同 /reset-password P0-4）

### P1-2：5 sub-tab 视觉权重等同
- 修复：当前 active tab 加 primary 边

### P1-3：表单 label 与 input 关联弱
- 修复：所有 input 配 for/aria-describedby

## P2（可优化）

### P2-1：发布历史回滚区域空
- 修复：默认折叠 / 显示最近 1 条

### P2-2：模型/治理矩阵 跳到对应 tab 引导弱
