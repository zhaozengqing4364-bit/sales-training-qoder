# /forgot-password 视觉分析

**wave**: public | **viewport**: 1440 / 375 | **截图数**: 3
**截图清单**：
- `screenshots/public/forgot-password-default-1440.png` — 默认态（按钮 disabled）
- `screenshots/public/forgot-password-default-375.png` — 移动端默认
- `screenshots/public/forgot-password-filled-375.png` — 移动端已填（按钮 enabled）

**a11y 树要点**：
- H1 = "忘记密码"（✓ 仅 1 个 H1）
- 1 button（disabled until valid email）
- 1 textbox（邮箱）
- 1 link "返回登录" → /login
- 0 console error

---

## P0（必须修）
- 无

## P1（1 周内）
- 无

## P2（可优化）

### P2-1：缺少 form-level 错误提示
- **位置**：邮箱输入框
- **问题**：snapshot 显示无 `aria-describedby` 关联错误文案位
- **修复方向**：提交时若 email 不存在 / 格式错，inline 错误应紧贴 input 下方

### P2-2：缺少 rate-limit 视觉提示
- **位置**：按钮按下后
- **问题**：连续点击"发送重置链接"无防抖，UI 无 loading 反馈（虽然后端可能有限流）
- **修复方向**：点击后按钮内显示 spinner + 禁用重复点击；30s 内不可重发

### P2-3：与 /login 视觉一致性优秀
- logo 改为 mail 图标（语义化，**比 /login 强**）
- 卡片宽度、padding、字体阶 与 /login 完全一致
- 按钮 disabled 态、focus 态、enabled 态对比清晰

## P3（可选）

### P3-1：未提供 SSO 用户的"用企业微信找回"
- 已有 SSO 入口，理应也支持 SSO 重置

---

## 设计 token 实测

| 维度 | 实测值 | token 体系 | 偏差 |
|---|---|---|---|
| 主背景 | #FAFAF9 | ✅ `--color-bg-main` | 0 |
| 卡片 | #FFFFFF | ✅ `--color-bg-card` | 0 |
| 主文本 | #18181B | ✅ `--color-text-primary` | 0 |
| 按钮 disabled 态 | 浅灰填充 | ✅ `disabled:` 样式 | 0 |
| 按钮 enabled 态 | 深色填充 + 白字 | ✅ `--color-text-primary` 背景 | 0 |
| 圆角 | 16/24/9999 | ✅ `--radius-*` | 0 |
| 阴影 | 卡片悬浮 | ✅ `--shadow-float` | 0 |

**结论**：100% 走 token 体系。

---

## 视觉层级评估

- **视线流**：logo (mail) → 标题 → 副标题 → 表单 → 主按钮 → 返回链接 ✅
- **CTA 强度**：按钮 enabled 时是页面最强元素 ✅
- **返回链接** 用左箭头 + "返回登录" 文字，符合"返回"语义

## 一致性（与 /login 对比）

- ✅ 卡片宽度、padding、圆角一致
- ✅ 字体、字号阶一致
- ✅ 配色一致
- ✅ a11y 实践一致（单 H1、label 关联、focus 可见）
- ✅ disabled 态反馈一致

**与 /login 差异**（合理）：
- logo 图标不同（mail vs AI）— 语义化更准确
- 副标题文案更长（解释操作）— 表单页需要说明
- 没有 SSO 区块 — 简单任务不需要

---

## 总结

这是项目**目前看到的最佳落地页**：简洁、token 化、可访问、视觉一致。**无 P0 / P1**。
