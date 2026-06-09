# 组件层排版审计

> 数据源：12 个审计页面的 snapshot + 截图
> 重点：按钮 / 表单 / 卡片 / 模态 / 导航 / 反馈

---

## 1. 按钮

### 1.1 形态盘点

| 类型 | 截图证据 | 出现页 | 评价 |
|---|---|---|---|
| Primary（深色填充） | 登录、训练 CTA | /login, /training, / | ✅ 清晰 |
| Secondary（边框 + 文字） | 销售训练 MVP 之外的卡 | /training, /training/sales | ✅ |
| Ghost（仅文字 + 箭头） | "进入场景库" | /training, /training/sales | ✅ |
| Disabled（浅灰） | 销售训练 MVP 入口未达成 | /login WeCom | ⚠️ 与 enabled 态对比度可加强 |
| Destructive（红色） | /history 删除 | /history | ⚠️ 视觉权重与普通按钮等同，**危险** |
| Icon-only | sidebar 折叠 / show pwd | /login, / | ✅ |

### 1.2 问题

| # | 问题 | 截图 | 优先级 |
|---|---|---|---|
| C-B1 | "删除" 按钮在 /history 视觉与主操作等同 | history-default-1440.png | **P0**（误删风险） |
| C-B2 | /test-mic 移动端 4 按钮字符级垂直换行 | test-mic-authed-375.png | **P0** |
| C-B3 | /training "进入销售训练" 与 "进入场景库" 权重不清晰 | training-default-1440.png | P1 |
| C-B4 | 多个 "去训练大厅" CTA 同页重复（/leaderboard） | leaderboard-default-1440.png | P2 |

### 1.3 修复方向

- **C-B1**：删除按钮改用 ghost + hover 红描边；或 icon button；点按前必须 confirm
- **C-B2**：移动端按钮 `flex-col` 单列 + `whitespace-nowrap`
- **C-B3**：明确"主路径 vs 次路径"层级，主路径用 primary

---

## 2. 表单

### 2.1 字段类型

| 类型 | 出现页 | 评价 |
|---|---|---|
| 邮箱 | /login, /forgot-password, /reset-password | ✅ 统一 placeholder |
| 密码（带显示切换） | /login, /reset-password | ⚠️ /reset-password 缺切换 |
| 重置令牌 | /reset-password | ✅ |
| 复选框 | /login "记住邮箱" | ⚠️ label 25 字超长 |
| 下拉 / select | /profile (1.0x) | ⚠️ 控件偏小 |

### 2.2 错误反馈机制（**项目级 P0**）

| 检查 | 状态 |
|---|---|
| 失焦 inline 错误 | ❌ 无 |
| 提交后端 422 错误回填 | ❌ 未验证（snapshot 无错误态） |
| 焦点回到错误字段 | ❌ 未验证 |
| 密码不一致红色边框 | ❌ /reset-password 已确认缺失 |
| 密码强度提示 | ❌ /reset-password 已确认缺失 |

**P0**：所有含密码确认的表单都需要 inline 错误反馈（影响至少 3 个页：/reset-password, /profile "修改密码", /admin/users 新建用户）。

### 2.3 占位 vs label

- ✅ 大多数用 `<label>` 关联 input（snapshot 证实）
- ❌ placeholder 当 label 用的页（如 /login 邮箱）— 用户清空后字段无描述

---

## 3. 卡片

### 3.1 形态盘点

| 类型 | 出现页 | 评价 |
|---|---|---|
| 基础白卡 | 全部 dashboard / admin 页 | ✅ |
| 悬浮卡 (hover) | /training/sales, /admin/users | ⚠️ hover 反馈不一致 |
| Metric 数字卡 | /, /profile, /admin | ✅ |
| List 项卡 | /history | ✅ |
| 空状态 CTA 卡 | /leaderboard | ✅ 项目亮点 |

### 3.2 圆角一致性

- 96% 卡片用 `rounded-2xl` (16px) — ✅
- 4% 用 `rounded-3xl` (24px) — hero 类，OK

### 3.3 阴影一致性

- 多数用 `shadow-card` (globals.css 自定义)
- ⚠️ /login 用 `shadow-slate-900`（染色）— 与其他不一致
- 建议：login 改 `shadow-float`

---

## 4. 模态 / Drawer

| 类型 | 出现页 | 评价 |
|---|---|---|
| 模态 | /test-mic "列出设备" 在 log 显示（非真模态） | — |
| 确认 dialog | /history 删除（无 dialog 直接删）| ❌ **P0**：危险操作无确认 |
| 抽屉 | 暂未观察到 | — |

**P0**：所有 "删除" / "重置" 等不可逆操作前必须 confirm。

---

## 5. 导航

### 5.1 Sidebar

| 区域 | 路径 | 菜单项数 | 状态 |
|---|---|---|---|
| dashboard | /, /training, /history, /profile, /leaderboard, /support, /test-mic | 5 + 2 = 7 | ✅ |
| **admin** | /admin, /admin/users, /admin/agents, ... | 10+ | ❌ **P0** |

**P0 跨区 sidebar 不一致** — 详见 `vision/admin.md` P0-1。

### 5.2 Tab

- /training (3 场景 chip), /history (3 筛选), /leaderboard (3 组 tab)
- 全部用 segmented control，**视觉一致** ✅
- ⚠️ /leaderboard 3 组 tab 视觉权重等同，无主次

### 5.3 面包屑

- 仅 /training/sales, /training/presentation 有"返回训练大厅"
- ❌ 大部分子页面无面包屑

### 5.4 底部 FAB（移动端）

- /, /training, /history 都有 3 个 FAB
- ⚠️ **P0**：FAB 覆盖底部内容（/, /training 已确认）
- 修复：sticky bottom + 半透明 + 主体 padding-bottom

---

## 6. 反馈组件

### 6.1 Toast

- 暂未观察到 toast（可能用 state 临时弹）
- 0 console error 是反馈缺失的间接证据

### 6.2 Loading

- /test-mic 有 "重新检测后端" 按钮，但点击后无明显 loading 反馈
- ⚠️ **P1**：loading 反馈不统一

### 6.3 Empty State

- /leaderboard 是**项目最佳实践**（2 个空状态都配 CTA）
- /training/presentation 大空白 = 缺失空状态引导

### 6.4 Error Boundary

- 在 dashboard `/support/runtime` 入口
- 暂未触发错误，无法验证

---

## 7. 总评

| 组件 | 评价 | 重点问题 |
|---|---|---|
| 按钮 | ⚠️ | 删除按钮权重 + 移动端按钮 |
| 表单 | ❌ | **P0 项目级：错误反馈机制缺失** |
| 卡片 | ✅ | hover 反馈不一致（小问题）|
| 模态 | ❌ | **P0：删除/重置操作无 confirm** |
| 导航 | ❌ | **P0：dashboard/admin 双 sidebar** |
| 反馈 | ⚠️ | loading 反馈不统一 |
