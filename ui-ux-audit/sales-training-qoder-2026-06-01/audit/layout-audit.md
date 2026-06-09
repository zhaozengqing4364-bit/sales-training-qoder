# 布局层排版审计

> 数据源：12 个审计页面的截图 + globals.css
> 重点：网格 / 容器 / 断点 / 对齐 / 留白节奏

---

## 1. 全局布局结构

### 1.1 Layout 数量盘点

| Layout | 路径 | 包含页数 |
|---|---|---|
| `(auth)/layout.tsx` | /login, /forgot-password, /reset-password | 3 |
| `(dashboard)/layout.tsx` | /, /training*, /history, /profile, /leaderboard, /support, /agents, /sales-trainer/* | 14+ |
| `(user)/layout.tsx` | /learning-path, /practice, /study, /exam | 4 |
| **`admin/layout.tsx`** | /admin, /admin/* | 50+ |
| `layout.tsx`（根） | 全部 | — |

**重大发现（P0）**：
- **dashboard layout 与 admin layout 是两个完全独立的 React 组件**
- 各自的 sidebar 风格、菜单结构、用户信息区都不同
- 用户从 dashboard 跳到 admin 后，整个 LHS 全部换掉

详见 `vision/admin.md` P0-1。

### 1.2 整体结构

| 区域 | 宽度（1440 桌面） | 备注 |
|---|---|---|
| 顶部 | 0 | dashboard / admin 无顶栏 |
| Sidebar | 240px 固定 | dashboard / admin 都用 240px |
| 主区 | `flex-1` | 无 max-width 限制（响应式 padding） |
| 底部 | 0 | dashboard / admin 无 footer |
| 移动端 | Sidebar 折叠为汉堡 | ✅ |

---

## 2. 网格 / 栅格

### 2.1 主区栅格

| 页 | 栅格 | 评价 |
|---|---|---|
| / | metric 4 列 + 任务卡 + 历史 list | ✅ 12 列 + 8 px gap |
| /training | 1 横幅 + 2 列卡 | ✅ |
| /training/sales | 3 列 agent 卡 | ✅ |
| /history | 4 metric + list | ✅ |
| /profile | 4 metric + 2 section | ✅ |
| /admin | 4 metric + 3 列卡 | ✅ |
| /leaderboard | 时间/场景/榜单 3 组 tab + 单列 | ✅ |
| /login 等 | 居中单列 max-w 480px | ✅ |

**结论**：主区栅格 12 列 + 24px gap（Tailwind `gap-6`），整体一致。

### 2.2 卡片栅格

- 多数用 `grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6` 模式
- ⚠️ /training/presentation 单卡时**未填满网格**，显空

---

## 3. 容器 / 间距

### 3.1 主区 padding

| 页 | 主区 padding |
|---|---|
| / | `p-8` (32px) |
| /training | `p-8` |
| /history | `p-8` |
| /profile | `p-8` |
| /admin | `p-8` |
| /leaderboard | `p-8` |
| /login 等 | `p-12` (48px) — 居中卡用大 padding |

**结论**：dashboard / admin 主区统一 `p-8`，居中表单用 `p-12`。✅

### 3.2 卡片内 padding

- metric 数字卡：`p-4` / `p-6` 混用
- 长内容卡：`p-6` (24px)
- 表单字段组：`p-6` / `p-8` 混用
- 建议：统一 `p-6`

---

## 4. 断点

### 4.1 实际使用

- `md:` (768px)：从单列 → 多列的切换
- `lg:` (1024px)：sidebar 显示 / 隐藏
- `xl:` (1280px)：未大量使用
- `2xl:` (1536px)：未使用

### 4.2 移动端行为

| 元素 | 桌面 | 移动 | 评价 |
|---|---|---|---|
| Sidebar | 240px 显示 | 折叠汉堡 | ✅ |
| 主区 padding | `p-8` | `p-4` (推测) | ⚠️ 应统一规则 |
| 表格 / List | 多列 | 单列堆叠 | ✅ |
| metric 卡 | 4 列 | 2 列 / 1 列 | ⚠️ 不一致 |
| Agent 卡 | 3 列 | 1 列 | ✅ |
| **底部 FAB** | 无 | 3 个浮窗 | ❌ **P0：FAB 覆盖内容** |

### 4.3 tablet (768-1024) 行为

- ⚠️ **未充分测试** — sidebar 与主区可能挤
- 建议：补 tablet 截图

---

## 5. 对齐 / 留白节奏

### 5.1 留白节奏

| 页 | 节奏 |
|---|---|
| / | 紧 → metric 4 列紧贴 → 任务卡单独行 |
| /training | 横幅单独行 → 卡 2 列 |
| /history | 4 metric 紧贴 → list 单独行 |
| /login | 居中卡留白 60vh（card 高度 50vh）|

### 5.2 视觉对齐

- ✅ 主区基线对齐良好
- ⚠️ /training "训练能力地图" ⓘ 图标在 H2 之后，与下方数据无视觉绑定

---

## 6. 字号节奏

- 同一 H1 在不同页字号不一致：
  - / 用 `text-3xl` (30px)
  - /training 用 `text-3xl` (30px)  
  - /history 用 `text-3xl` (30px) (推测)
  - /admin 用 `text-3xl` (30px)
  - ✅ 一致

- 副标题用 `text-sm` (14px) 或 `text-base` (16px) — 略不统一

---

## 7. 顶部 / 底部

| 页 | 顶部 | 底部 |
|---|---|---|
| / | 无 | sidebar 折叠按钮在 sidebar 内 |
| /training | 无 | sidebar 折叠按钮 |
| /admin | 无 | sidebar 折叠按钮 |
| /login | 无 | 无 |
| /test-mic | "开发工具" 横幅 chip | 无 |

**⚠️ 缺统一顶栏**：所有 dashboard/admin 页无搜索、无通知、无面包屑。

---

## 8. 总评

| 维度 | 评价 | 重点问题 |
|---|---|---|
| Layout 数量 | ❌ | dashboard / admin 两套 layout（P0 IA） |
| 主区栅格 | ✅ | 12 列 + 24px gap 统一 |
| 容器 padding | ✅ | p-8 一致 |
| 断点 | ⚠️ | tablet 行为未充分测试 |
| 移动端 | ⚠️ | FAB 覆盖内容（P0） |
| 留白节奏 | ✅ | 基本一致 |
| 字号节奏 | ✅ | H1 一致 |
| 顶/底 | ❌ | 缺统一顶栏（搜索/通知/面包屑） |
