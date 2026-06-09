# /reset-password 视觉分析

**wave**: public | **viewport**: 1440 / 375 | **截图数**: 4
**截图清单**：
- `screenshots/public/reset-password-default-1440.png` — 默认态（按钮 disabled）
- `screenshots/public/reset-password-default-375.png` — 移动端默认
- `screenshots/public/reset-password-filled-375.png` — 已填全部（按钮 enabled）
- `screenshots/public/reset-password-mismatch-375.png` — 两次密码不一致

**a11y 树要点**：
- H1 = "设置新密码"（✓ 仅 1 个 H1）
- 1 button（disabled / enabled 状态机）
- 3 textbox：重置令牌、新密码、确认新密码
- 1 link "返回登录" → /login
- 0 console error

---

## P0（必须修）

### P0-1：密码不一致时按钮仍可提交，缺 inline 错误
- **位置**：确认新密码 input
- **复现**：
  1. 填入 token + 任意新密码 + **不同**的确认密码
  2. 按钮"重置密码"**仍 enabled**（黑色填充）
  3. 无任何 inline 错误提示
- **影响**：用户会点击提交，被后端拒绝，错误链路拉长；移动端尤其严重（用户不知哪里错）
- **截图**：`reset-password-mismatch-375.png`
- **修复方向**：
  - 添加 `aria-describedby` 关联错误位
  - 确认密码 input 失焦时对比新密码，不一致 → 红色边框 + "两次输入的密码不一致"
  - 按钮在不一致时 disabled
  - 或后端返回 422 时把焦点回错误字段

---

## P1（1 周内）

### P1-1：无密码强度提示
- **位置**：新密码 input
- **问题**：
  - placeholder 只说"至少 8 个字符"，无强度反馈
  - `hasPasswordStrength = false`（DOM 查询确认）
  - 内网工具对密码强度要求更严格（合规要求），缺可视化反馈
- **修复方向**：
  - 输入时实时显示强度（弱/中/强）
  - 建议规则：长度 ≥ 10 + 含数字 + 含大写 + 含符号
  - 用 progress bar 或分色 label

### P1-2：重置令牌字段 UX 不直观
- **位置**：重置令牌 input
- **问题**：
  - placeholder 写"粘贴邮件中的重置令牌"
  - 副标题又说"若您在本地开发环境，请粘贴邮件或控制台中的重置令牌"
  - 但页面**没有自动从 URL 解析 token**（如 `?token=...`）—— 用户必须手动复制粘贴
- **修复方向**：
  - 监听 URL `?token=` 参数，自动填入
  - 复制粘贴后自动 trim 空白

## P2（可优化）

### P2-1：副标题文案 "邮件中的重置令牌和您的新密码" 略生硬
- 改为"在邮件中找到令牌，输入并设置新密码"

### P2-2：缺少显示/隐藏密码切换
- /login 页有，/reset-password 缺
- 修复：在新密码、确认新密码都加眼睛图标

### P2-3：logo 改用 key 图标（密码场景）
- 与 /forgot-password 的 mail 图标、/login 的 AI logo 形成系列
- ✅ 当前已经用 key 图标（截图证实）— 已对齐

## P3（可选）

### P3-1：令牌过期无 UI 倒计时
- 提交时若 token 过期，错误信息应说明"令牌已过期，请重新申请"

---

## 设计 token 实测

| 维度 | 实测值 | token 体系 | 偏差 |
|---|---|---|---|
| 主背景 | #FAFAF9 | ✅ `--color-bg-main` | 0 |
| 卡片 | #FFFFFF | ✅ `--color-bg-card` | 0 |
| 错误反馈 | **缺失** | ⚠️ 无 `--color-error` token | **token 漏定义** |
| 圆角 | 16/24/9999 | ✅ `--radius-*` | 0 |

**结论**：表单排版 100% 走 token；**错误色 token 缺失**（P0-1 的修复需要 `--color-error`）。

---

## 视觉层级评估

- **视线流**：logo (key) → 标题 → 副标题 → 3 字段 → 主按钮 → 返回链接 ✅
- **CTA 强度**：按钮 enabled 时最强 ✅
- **3 字段垂直堆叠**：标签 + 输入框 + 字段说明（如 token）— 层级清晰

## 一致性（与 /login / /forgot-password 对比）

- ✅ 卡片宽度、padding、圆角一致
- ✅ 字体、字号阶一致
- ✅ 配色一致
- ✅ 按钮 disabled / enabled 状态机一致
- ❌ **缺 inline 错误反馈**（P0）— 其他表单页也没显式 inline error，**项目级问题**
- ❌ 缺密码强度（其他页无）
- ❌ /reset-password 缺显示密码切换（/login 有）

---

## 总结

整体布局/视觉一致，**但 P0-1（密码不一致无反馈）是阻塞级缺陷**，影响所有含密码确认的表单（后续审计 /change-password、/admin/users 等也会重复出现）。
