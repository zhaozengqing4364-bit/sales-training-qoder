# UI/UX 审计 · 场景子文件

> 主入口：`.claude/loop.md` 每轮先读它。
> 状态机：`discover → audit(wave × N) → aggregate → done`
> 产物根目录：`ui-ux-audit/sales-training-qoder-<YYYY-MM-DD>/`

---

## 0. 前置检查（每轮第一件事）

```bash
# 0.1 dev server 探活
curl -sS -o /dev/null -w "%{http_code}\n" --max-time 5 http://localhost:3445
# 期望：200 / 307 / 404 之一（非 000）；返回 000 立即升级

# 0.2 读取状态
Read .claude/loop-state/ui-ux-audit.last.json
Read .claude/loop-state/ui-ux-audit.todo.json
Read .claude/loop-state/ui-ux-audit.reflexion.json
```

如果 `last.json.phase` 不存在或 `todo.json` 为空 → 走 **Stage 0：发现 & 路由盘点**。
否则直接按 `last.json.phase` 继续。

---

## Stage 0 · 路由发现 & pages.json 生成

**只在 `phase=discover` 时跑一次。**

### 0.1 列路由
优先用项目源码（不靠盲爬）：

```bash
find web/src/app -name "page.tsx" -o -name "layout.tsx" | sort
```

把结果映射到路由（去掉 `(group)` 段、保留 `[param]` 段、`_` 开头忽略）。

### 0.2 解析路由组与 wave

| 路径前缀 | wave | 鉴权 |
|---|---|---|
| `/` `(auth)/login`、`register` 等 | `public` | false |
| `(auth)/*` | `auth` | false（自带登录页） |
| `(dashboard)/*` | `dashboard` | true |
| `(user)/*` | `user` | true |
| `admin/*` | `admin` | true（管理员） |
| `sales-trainer/audio|learn|quiz` | `dashboard` 子 | true |

### 0.3 写 pages.json

`ui-ux-audit/<date>/pages.json`：

```json
[
  {"path": "/", "name": "首页", "auth": false, "wave": "public", "status": "pending", "screenshots": []},
  {"path": "/login", "name": "登录", "auth": false, "wave": "auth", "status": "pending", "screenshots": []},
  {"path": "/dashboard", "name": "工作台", "auth": true, "wave": "dashboard", "status": "pending", "screenshots": []},
  {"path": "/admin", "name": "管理首页", "auth": true, "wave": "admin", "status": "pending", "screenshots": []}
]
```

### 0.4 写 todo.json

`.claude/loop-state/ui-ux-audit.todo.json`：

```json
{
  "queue": ["/login", "/dashboard", ...],  // 按 wave 顺序：public → auth → dashboard → user → admin
  "blocked": ["/admin/users" /* 需要 admin 权限 */],
  "skipped": ["/_next/..."]
}
```

### 0.5 切 phase
- 覆盖写 `last.json`：phase=audit, current_wave=todo.json 第一个 path 所在 wave
- 输出 evidence log 标记"Stage 0 完成 / N 个路由入队 / M 个 blocked"

---

## Stage 1 · 截图采集（每页 = 1 轮）

**工具映射**（MCP playwright）：

| 动作 | 工具 |
|---|---|
| 打开 URL | `mcp__playwright__browser_navigate` |
| 调视口 | `mcp__playwright__browser_resize`（desktop 1440×900 / mobile 375×812） |
| 截图 | `mcp__playwright__browser_take_screenshot`（`fullPage: true`） |
| a11y 树 | `mcp__playwright__browser_snapshot` |
| 控制台 | `mcp__playwright__browser_console_messages`（level=error） |
| 网络 | `mcp__playwright__browser_network_requests`（filter=`api/.*`） |
| 点击 / 输入 | `mcp__playwright__browser_click` / `browser_type` |
| 注入脚本 | `mcp__playwright__browser_evaluate` |

### 1.1 每页必采

1. `browser_resize 1440 900`
2. `browser_navigate <base-url><path>` 等 `wait_for` 到关键文本出现
3. `browser_console_messages level=error` → 记录到 vision 文件
4. `browser_snapshot` → 存为 a11y 证据
5. `browser_take_screenshot fullPage=true type=png filename=...`（桌面）
6. `browser_resize 375 812` → 再截一张移动
7. **关键交互态**（按页面元素判定，常见的 3-5 个）：
   - 打开主 modal / drawer
   - 触发空态（如果有 empty placeholder）
   - 触发 loading（如果可注入）
   - hover 主 CTA（可选）
   - 错误态（表单填错）

### 1.2 命名规范
`ui-ux-audit/<date>/screenshots/<wave>/<page-slug>-<state>-<viewport>.png`

例：
```
screenshots/dashboard/sales-trainer-audio-default-1440.png
screenshots/dashboard/sales-trainer-audio-default-375.png
screenshots/dashboard/sales-trainer-audio-modal-recording-1440.png
```

### 1.3 写截图记录
每张图追加到 `pages.json` 对应 path 的 `screenshots` 数组。

---

## Stage 2 · 视觉理解（多模态）

**用 Read 直接打开 PNG**（你本身就是多模态模型，可看图）。

对**每张截图**问自己这 5 类问题（按 P0/P1/P2/P3 严重度列）：

```
1. 排版与栅格
   - 网格对齐、列宽、容器最大宽
   - 间距体系（4/8 px 基准？）
   - 字号阶、字重、行高、字间距
   - 颜色对比度（文本/背景、CTA/背景）

2. 视觉异常
   - 元素错位 / 截断 / 溢出 / 重叠
   - 缺失图、占位未替换、broken image
   - 像素级瑕疵（1px 偏移、毛刺、模糊）

3. 视觉层级
   - 视线流是否清晰
   - CTA / 主操作是否突出
   - 信息密度是否合理

4. 一致性
   - 同类组件在不同上下文是否一致
   - 颜色 / 圆角 / 阴影 / 字体用法是否统一

5. 可用性
   - 文字是否易读（行宽 ≤ 75 字符？行高 ≥ 1.4？）
   - 点击目标 ≥ 44×44 px？
   - 错误态 / 空态是否有引导
```

把每页结果写到 `ui-ux-audit/<date>/vision/<page-slug>.md`：

```markdown
# <path> 视觉分析

**wave**: <w> | **viewport**: 1440 / 375 | **截图数**: N

## P0（必须修）
- [ ] <位置>：<问题>（截图：screenshots/.../<page>-1440.png）
- [ ] ...

## P1（1 周内）
- ...

## P2 / P3（抽样）
- ...

## 设计 token 实测
| 维度 | 值 | 是否在 token 体系内 |
|---|---|---|
| 主背景 | #FAFAF9（实测） | ✅ globals.css --color-bg-main |
| 主文本 | #18181B | ✅ --color-text-primary |
| 主色 | #3B82F6 | ✅ --color-accent-blue |
| 圆角 | 16/24/9999 | ✅ --radius-* |
| 阴影 | sm/card/float | ✅ --shadow-* |
```

**对照基准**：`web/src/app/globals.css` 顶部 `:root` 块。

---

## Stage 3 · 排版 4 层审计

> 每层独立 .md，路径 `ui-ux-audit/<date>/audit/<layer>-audit.md`
> 不在 Stage 2 写，**所有页面跑完**后聚合。

### 3.1 token-audit.md
扫全站页面（Read 实际源码 + vision 文件），统计实际出现的：
- 色板：去重后列出现频次
- 字号阶：text-xs / sm / base / lg / xl / 2xl / 3xl / 4xl 实际使用
- 间距阶：p-1/2/3/4/6/8 实际使用
- 圆角：rounded / rounded-md / lg / xl / full
- 阴影：shadow-sm / card / float

对比 globals.css 里定义的 token，**列出所有"未在 token 体系内"的硬编码值**（`grep -rE "#[0-9a-fA-F]{3,6}" web/src`）。

### 3.2 components-audit.md
按组件类型列：
- 按钮：primary / secondary / ghost / destructive
- 表单：input / select / textarea / checkbox / radio
- 卡片：base / elevated / interactive
- 模态：dialog / drawer / sheet
- 导航：tab / breadcrumb / pagination
- 反馈：toast / alert / badge / tag

每类至少 1 行 + 截图证据 + "与同类组件的差异"。

### 3.3 layout-audit.md
- 网格：12 列？8pt 基准？实测是多少
- 容器：max-width 取值（看 layout.tsx）
- 断点：tailwind 默认 sm/md/lg/xl/2xl 使用情况
- 对齐 / 留白节奏
- 移动端：底部安全区、横屏、深色模式（如支持）

### 3.4 information-audit.md
- 标题层级：扫 `grep -rE "<h[1-6]" web/src/app` 看有无跳级
- 文本密度：每页字数 / 区块数
- 视觉锚点：hero / 主 CTA / 关键 metric
- 视线流：F 型 / Z 型 / 居中
- 信息架构：导航层级深度（最多 3 层？）

---

## Stage 4 · UI/UX 优化建议（5 视角）

输出到 `report.md` §5，每条带 **优先级 / 影响面 / 成本 / 验收**。

### 5.1 视觉设计
- 色彩系统：主色 ≤ 2 处 / 屏；语义色（success/warn/error）是否齐
- 字体搭配：Avenir Next 体系下中文 PingFang SC 兜底，跨平台是否一致
- 图标语言：lucide-react（项目已用）大小/线宽是否统一
- 玻璃/毛玻璃效果（项目 globals.css 有 glass tokens）：使用一致？
- 品牌一致性：logo、吉祥物、营销素材

### 5.2 交互设计
- 反馈可见性：每个 mutation 都有 loading / success / error 提示
- 状态过渡：hover / focus / active / disabled
- 错误恢复：表单错误是否 inline + 焦点回到错误字段
- 撤销/重做：危险操作（删除、覆盖）是否可撤销

### 5.3 信息架构
- 导航清晰度：sidebar / top nav / breadcrumb
- 页面层级：H1 → H2 → H3 是否每页只 1 个 H1
- 入口发现性：核心功能是否在首屏 / 一跳之内
- 面包屑：admin 子页面是否都有

### 5.4 可用性 / a11y
- WCAG 2.2 AA：对比度（4.5:1 文本 / 3:1 大文本）
- 键盘：Tab 顺序 / focus 可见 / skip link
- 屏幕阅读器：aria-label / aria-describedby
- 动效偏好：`prefers-reduced-motion` 是否尊重
- 点击目标 ≥ 44×44 px

### 5.5 微交互
- 过渡：duration 200/300/500 是否统一 token
- 加载：skeleton / spinner / shimmer
- hover / focus / active 视觉差异
- 动效：framer-motion 使用是否克制（项目已有 framer-motion 12）

---

## Stage 5 · 功能裁剪建议（2×2 矩阵）

> 扫描所有页面，列出**功能候选清单**（按钮、Tab、入口、菜单项）。

每条 1 句理由 + 截图证据 + 结论（**保留 / 合并 / 简化 / 移除**）。

```
                高战略价值
                    │
       保留并强化   │   简化或合并
                    │
   ── 使用频次 ─────┼────── 使用频次 ──
                    │
       重新设计     │   建议移除
                    │
                低战略价值
```

判定依据（必填证据）：
- **战略价值**：是否对应核心 OKR / 关键转化 / 差异化
- **使用频次**：界面位置（首屏 / 二级 / 三级）+ 推断点击热区
- **复杂度**：实现成本 / 测试覆盖 / 文档
- **重复度**：是否与其他入口功能相同

**直接移除**需满足：低频 + 低战略 + 实现复杂 / 出 bug 多 / 与其他入口完全重复。

---

## Stage 6 · 聚合报告

`ui-ux-audit/<date>/report.md` 章节（必齐，聚焦模式可裁）：

1. **执行摘要**（≤ 5 句）
2. **审计方法 & 覆盖范围**（路由总数 / 实际访问 / 截图数 / 跳过原因）
3. **P0 / P1 问题清单**（按页面索引，每行带截图）
4. **排版 4 层审计**（摘要 + 链接到 audit/*.md）
5. **UI/UX 优化建议**（5 视角，每条带优先级/成本/验收）
6. **功能裁剪建议**（2×2 矩阵 + 建议移除 / 合并 / 保留）
7. **优化路线图**（短 ≤1 周 / 中 1-4 周 / 长 >1 月）
8. **附录**：截图索引 + 数据来源 + 范围声明

`ui-ux-audit/<date>/summary.html`：用 `frontend-slides` 或 `canvas-design` 生成可视化总览（不强求，能生成就生成）。

---

## 7 部件 loop 框架

虽然这是 worker，但每轮仍按 7 部件走：

| 部件 | 本场景怎么填 |
|---|---|
| 🎯 目标 | 全部 wave × 全部 page × 桌面+移动+交互态 完成 + 报告交付 |
| 👁️ 观察 | last.json / todo.json / reflexion.json / dev server 探活 / 上一轮 vision 文件 |
| ⚙️ 动作 | playwright MCP + Read PNG + Edit 产物文件（限 ui-ux-audit/） |
| 🔍 验证 | 截图 size ≥ 5KB + vision 文件 ≥ 10 行 + pages.json 一致 + log 追加 |
| ✅ 退出 | pages_done == pages_total AND phase=done |
| 🚨 升级 | dev server 3 轮不通 / playwright 2 轮同错 / reflexion ≥ 3 / 阻塞 P0 |
| 📝 证据 | logs/ui-ux-audit.log 追加 + last.json 覆盖 + reflexion 追加失败 |

---

## 关键约束（实施层）

1. **每页最多 8 张截图**（防止 token 爆炸）。如果 8 张仍不足，把多模态分析分两轮。
2. **每页 vision 文件**不超过 200 行，超过则拆 vision/<page>-states.md。
3. **subagent 隔离**：用 `Explore` subagent 扫源码、生成 pages.json（不污染主上下文）。
4. **Writer/Reviewer 分离**：报告写完后，用 `general-purpose` subagent 在新上下文跑 `cat report.md | head -200` 做反审查，输出"哪些 P0 漏了 / 哪些建议没给验收"。
5. **断点续传**：下一轮从 `last.json.current_page` 继续。`forced_exit=true` 立即停。
6. **失败 2 次即升级**：同一 stage 失败 2 次 → 升级（让人类看 reflexion）。
7. **不要"完成证明"靠嘴说**：每轮证据都是 `stat`、`sha256sum`、`wc -l` 这些可机器读的输出。

---

## 输出契约（最终交付）

```bash
ui-ux-audit/sales-training-qoder-2026-06-01/
├── report.md                # 主报告（≥ 50 节）
├── pages.json               # 路由清单（完整）
├── summary.html             # 可视化总览
├── screenshots/             # 全部截图
│   ├── public/  auth/  dashboard/  user/  admin/
│   └── <page>-<state>-<viewport>.png
├── vision/                  # 每页多模态分析
│   └── <page-slug>.md
└── audit/                   # 4 层排版
    ├── token-audit.md
    ├── components-audit.md
    ├── layout-audit.md
    └── information-audit.md
```

完成时用 `<media />` 把 `report.md` + `summary.html` 发到对话。
