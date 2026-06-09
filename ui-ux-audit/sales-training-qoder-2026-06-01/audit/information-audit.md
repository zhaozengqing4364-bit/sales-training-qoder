# 信息层排版审计

> 数据源：12 个审计页面的截图 + snapshot
> 重点：标题层级 / 文本密度 / 视觉锚点 / 视线流 / 信息架构

---

## 1. 标题层级

### 1.1 实际使用

| 页面 | H1 | H2 | H3 | H4+ |
|---|---|---|---|---|
| /login | 欢迎回来 | — | — | — |
| /forgot-password | 忘记密码 | — | — | — |
| /reset-password | 设置新密码 | — | — | — |
| /test-mic | 麦克风调试工具 | — | — | — |
| / | 午安, Developer 👋 | 连续练习 / 本周目标 / 成长动态 / 今日复练任务 / 学习路径下一步 / 最近记录 | — | "制造业 CIO 首访训练教练" |
| /training | 训练模式 | 销售训练 MVP / 销售对练 / 演讲练习 | — | — |
| /training/sales | 销售能力训练 | (无明显 H2) | 6 个 agent 名 | — |
| /training/presentation | 演讲与表达训练 | (无明显 H2) | ppt训练 | — |
| /history | 训练历史记录 | (无 H2) | — | 行内 H4 |
| /profile | 个人中心 | 系统设置 / 帮助与反馈 | — | — |
| /admin | 管理控制台 | (隐式) | — | — |
| /leaderboard | 排行榜 | (隐式) | — | — |

### 1.2 层级问题

| # | 问题 | 位置 | 评价 |
|---|---|---|---|
| I-H1 | / 上有 6 个 H2 紧邻 | / | ✅ 良好（任务流清晰） |
| I-H2 | /training "训练模式" H1 + 副标题 + 卡内 H2，**H2 缺统一层级** | /training | ⚠️ |
| I-H3 | /history 行内用 H4 标记录标题 | /history | ⚠️ 实际数据行级 H4 过重 |
| I-H4 | /admin "管理控制台" H1 之后无 H2，3 个"待你真实统计"卡是 div | /admin | ⚠️ 缺次级 H2 |

**建议**：每个 dashboard / admin 页**至少 2 个 H2**（"数据指标" + "任务/列表"），用 section 区分。

---

## 2. 文本密度

| 页 | 文字量 | 评价 |
|---|---|---|
| /login | 低（4 字段 + 2 按钮） | ✅ 简洁 |
| /forgot-password | 极低 | ✅ |
| /reset-password | 中（3 字段 + 副标题） | ✅ |
| /test-mic | 中（4 按钮 + 日志） | ✅ |
| / | 高（4 metric + 4 长卡 + 历史 5 行） | ⚠️ **首屏信息过载** |
| /training | 低 | ✅ |
| /training/sales | 中（6 卡） | ✅ |
| /history | 中（5 行 + 4 metric） | ✅ |
| /profile | 中（2 section） | ✅ |
| /admin | 中（4 metric + 3 配置） | ✅ |
| /leaderboard | 中（3 组 tab + 当前用户 + 空状态） | ✅ |

**重点**：**/ 首次信息密度过高**（首屏 4 metric + 6 大卡 + 历史 5 行），建议：
- 折叠"最近记录"到二级（"查看全部"）
- 4 metric 中空态的弱化

---

## 3. 视觉锚点

### 3.1 锚点评估

| 页 | 主锚点 | 强度 | 评价 |
|---|---|---|---|
| /login | "登录" 深色按钮 | 强 | ✅ |
| /forgot-password | "发送重置链接" | 中 | ⚠️ disabled 时无替代锚点 |
| /reset-password | "重置密码" | 强 | ✅ |
| /test-mic | "开始录音" 紫按钮 | 强 | ✅ |
| / | "今日复练任务" 卡 | 中 | ⚠️ **应有浮动主 CTA** |
| /training | "进入销售训练" 横幅 | 强 | ✅ |
| /training/sales | 6 张卡等权 | 弱 | ❌ 无主焦点 |
| /history | 删除 button（误）| — | ❌ 删除过强 |
| /profile | 编辑资料 | 弱 | ⚠️ |
| /admin | 3 配置卡等权 | 弱 | ❌ 无主焦点 |
| /leaderboard | "去训练大厅" 出现 2 次 | 中 | ⚠️ |

### 3.2 共性问题

**P1**：除登录/重置密码等表单页，**dashboard / admin / leaderboard 普遍缺主视觉锚点**。
**修复方向**：
- 顶部 H1 旁加一个 primary button "开始训练 →"
- 列表型页（/history, /leaderboard）首屏顶部加主 CTA

---

## 4. 视线流

### 4.1 视线流分析

| 页 | 视线流 | 评价 |
|---|---|---|
| / | sidebar → H1 → 4 metric → 4 大卡 → 历史 | ⚠️ 末段历史是 mouse trail 末，用户常跳过 |
| /training | sidebar → H1 → 横幅 → 2 卡 | ✅ 清晰 |
| /training/sales | sidebar → H1 → 3 metric → 6 卡 | ⚠️ 6 卡 grid 无主次 |
| /history | sidebar → H1 → 4 metric → 3 filter → 5 行 | ✅ 经典 F 型 |
| /admin | sidebar → H1 → 4 metric → 3 配置 → 采集 | ✅ |

**P2**：/training/sales 6 张 agent 卡等权，**视线不知道停在哪儿**。建议：
- 加 ⭐ 推荐标
- 按"最近使用 / 评分 / 难度"重排

---

## 5. 信息架构（IA）

### 5.1 全局 IA 评估

| 区域 | 路径 | IA 评价 |
|---|---|---|
| 公开 | /login, /forgot-password, /reset-password | ✅ 标准 auth flow |
| 学员 | /, /training, /training/*, /history, /leaderboard, /profile | ✅ 覆盖核心 loop |
| 学员扩展 | /support, /support/runtime, /agents, /sales-trainer/* | ⚠️ 与学员区部分重叠 |
| 管理 | /admin/* (50+) | ⚠️ 内部 IA 需审 admin/* 子页 |

### 5.2 sidebar 分组问题

| sidebar | 分组 | 评价 |
|---|---|---|
| dashboard | 菜单 (5) + 系统 (2) | ✅ 清晰 |
| admin | 10 项平铺 | ❌ 无分组 |

### 5.3 跨区导航问题（P0）

- 从 dashboard 跳到 admin：**整个 sidebar 全换**，无视觉提示
- 无"返回学员区"快捷入口
- 详见 `vision/admin.md` P0-1

---

## 6. 文案

### 6.1 文案错别字（P0-1 in leaderboard）

- "按号分级练习的排名，疑是当期排行练习" — 错别字 + 语义不通

### 6.2 英文术语泄漏到中文界面

- /training "evidence_backing" / "advance" — 后端 skill key 直显
- /training/sales "Smoke Phase 4 Sales Agent" — smoke test 标记

### 6.3 冗长文案

- /login "记住邮箱，下次自动填入；登录有效期仍由后端会话配置决定。" — 25 字

### 6.4 描述性 vs 动作性

- 多数按钮用动作性（"开始录音" / "去训练大厅"）✅
- ⚠️ /history 描述性标签（"查看历史"）— 弱动作

---

## 7. 总评

| 维度 | 评价 | 重点问题 |
|---|---|---|
| 标题层级 | ⚠️ | 部分页 H2 缺位 |
| 文本密度 | ⚠️ | / 首屏过载 |
| 视觉锚点 | ❌ | dashboard / admin / leaderboard 缺主 CTA |
| 视线流 | ✅ | 大部分合理 |
| 信息架构 | ❌ | **P0：dashboard / admin 双 sidebar** |
| 文案 | ❌ | **P0：错别字 + 英文泄漏** |
