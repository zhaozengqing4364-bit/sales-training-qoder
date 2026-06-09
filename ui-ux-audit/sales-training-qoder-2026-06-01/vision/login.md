# /login 视觉分析

**wave**: public | **viewport**: 1440 / 375 | **截图数**: 3
**截图清单**：
- `screenshots/public/login-default-1440.png` — 默认态
- `screenshots/public/login-default-375.png` — 移动端默认
- `screenshots/public/login-focus-email-375.png` — 移动端邮箱 focus
- `screenshots/public/login-filled-1440.png` — 桌面端已填邮箱

**a11y 树要点**：
- H1 = "欢迎回来"（✓ 仅 1 个 H1）
- 3 个按钮：企业微信登录（disabled）、开发者快速登录、登录
- 2 个 textbox：邮箱、密码（含显示密码切换）
- 1 个 checkbox
- 0 个 console error
- 标题层级正确（无跳级）

---

## P0（必须修）
- 无

## P1（1 周内）

### P1-1：两个 SSO 选项语义混乱
- **位置**：顶部 "企业微信登录" 与 "开发者快速登录" 并列
- **问题**：
  - "企业微信登录 (WeCom)" 渲染为 disabled 状态卡片 + 提示 "当前环境未配置企业微信 SSO"
  - "开发者快速登录" 渲染为 active 按钮 + 提示 "仅 development 环境可用的开发者登录"
  - 两个并存，**让生产用户看到 disabled 卡片和"开发者"入口，是产品级混淆**
- **修复方向**：
  - 部署生产时，开发者入口消失（环境判定）
  - 未配置 WeCom 时，**整张卡片不显示**（避免 negative 信息）
  - 仅 dev / preview 环境才显示开发者入口

### P1-2：长 checkbox label 触碰 a11y 边界
- **位置**："记住邮箱..." 复选框
- **问题**：
  - label 长度 25 个汉字 + 中文标点："记住邮箱，下次自动填入；登录有效期仍由后端会话配置决定。"
  - 移动端（375）label 折 2 行但仍可读
  - 屏幕阅读器会读完整串，但视觉上 label 与 checkbox 的对齐偏离（label 出现 wrap 时，checkbox 居中位置无变化）
- **修复方向**：
  - 拆成"记住邮箱" + 一个次级说明链接"（登录有效期由后端决定）"
  - 或加 `aria-describedby` 指向说明文本

## P2（可优化）

### P2-1：缺少"测试账号"提示
- **位置**：账号登录区下方
- **问题**：未配置 demo 凭据时，dev / preview 环境中用户不知道可用测试账号
- **修复方向**：env == development 时显示折叠的"测试账号"区块

### P2-2：移动端"Open Next.js Dev Tools" 浮窗泄露
- **位置**：左下角浮动按钮
- **问题**：Next.js 16 dev 模式的浮窗在 375 视口也显示，**生产前必须隐藏**
- **修复方向**：依赖 dev 构建特性自动消失；如在 staging 出现需配置 `next.config.js` 关闭

### P2-3：logo 与首屏留白偏多
- **位置**：logo (40px) 距卡片顶部 48px
- **问题**：在 1440 桌面端首屏能看到 80px+ 空白；紧凑型布局可缩到 24-32px
- **修复方向**：card padding-top 从 `pt-12` 改为 `pt-8`

### P2-4：登录按钮箭头图标未传达动作语义
- **位置**：登录按钮内的右箭头 `→`
- **问题**：a11y 树显示是 `img`，未与按钮文字绑定 ARIA
- **修复方向**：装饰性图标 `aria-hidden="true"`（如果它已经是 button 文字的一部分）

## P3（可选）

### P3-1：暗色模式未支持
- 全站仅一个浅色 token，无 `prefers-color-scheme` 适配

### P3-2：未提供"扫码登录"等替代
- 仅有账号密码 + 微信登录，缺 SSO（OAuth / SAML）

---

## 设计 token 实测

| 维度 | 实测值 | token 体系 | 偏差 |
|---|---|---|---|
| 主背景 | #FAFAF9 | ✅ `--color-bg-main` | 0 |
| 卡片背景 | #FFFFFF | ✅ `--color-bg-card` | 0 |
| 主文本 | #18181B | ✅ `--color-text-primary` | 0 |
| 次文本 | #71717A | ✅ `--color-text-secondary` | 0 |
| 主色（accent） | #3B82F6 | ✅ `--color-accent-blue` | 0 |
| 错误/警告 | #F59E0B（橙色"开发者提示"） | ⚠️ 未在 token 出现 | **token 漏定义** |
| 圆角（按钮） | 9999px | ✅ `--radius-full` | 0 |
| 圆角（输入框） | 16px | ✅ `--radius-subtle` | 0 |
| 圆角（卡片） | 24px | ✅ `--radius-medium` | 0 |
| 阴影（卡片） | 0 20px 25px -5px rgba(0,0,0,0.05) | ✅ `--shadow-float` | 0 |

**结论**：登录页 **100% 走 token 体系**，但**警告色 / 错误色未在 globals.css 显式定义**（`#F59E0B` 直接硬编码）。建议补 `--color-warn` / `--color-error` / `--color-success`。

---

## 视觉层级评估

- **视线流**：logo → 标题 → 副标题 → 主 CTA（开发者登录）→ 分隔 → 表单 → 登录按钮 ✅
- **CTA 强度**：开发者登录（蓝边框）> 账号登录（深色填充）—— **反直觉**。账号密码应是主路径，开发者入口应是次要
- **建议**：把"账号密码登录"放在最前，SSO 区块折叠 / 收起

## 一致性

- 与 globals.css 高度一致
- 与项目其他页面（待审计）需后续交叉验证
