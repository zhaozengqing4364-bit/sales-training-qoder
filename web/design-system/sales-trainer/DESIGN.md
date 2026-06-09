# 销售训练 · Modern Soft UI

> **ID:** `sales-trainer-modern-soft-ui`  
> **真源:** `web/design-system/sales-trainer/tokens/`  
> **与石犀训练 OD 原型无关** — 本体系从 `web/src` 生产代码提炼

## 设计语言

**Modern Soft UI** — 透气感、毛玻璃、便当盒布局、超级圆角。

| 要素 | 规则 |
|------|------|
| 画布 | `#FAFAF9` / `slate-50`，禁止全页纯白 |
| 锚点 | `slate-900` 主按钮、Logo |
| 圆角 | 按钮 `rounded-full`，卡片 `32px`，侧栏 `40px` |
| 阴影 | 弥散低对比 `0 8px 30px rgb(0,0,0,0.04)` |
| 状态 | 粉彩标签 green/amber/red/blue-50 |
| 演练 | 非阻塞 StatusIndicator，禁止 alert |

## Token 分层

| 文件 | 内容 |
|------|------|
| `colors.css` | 画布、文字、品牌色 |
| `semantic.css` | 成功/警告/错误/语音态 |
| `score.css` | 评分环、销售维度色 |
| `glass.css` | 毛玻璃 + blur |
| `typography.css` | 字体栈、字号、字重 |
| `spacing.css` | 4px 基准间距 |
| `radius.css` | 圆角 scale |
| `shadow.css` |  elevation |
| `motion.css` | 时长、easing、focus ring |
| `layout.css` | z-index、sidebar、触控尺寸 |
| `tokens.json` | W3C Design Tokens（Figma/工具链） |

## 组件映射

| Primitive | 代码 |
|-----------|------|
| GlassCard | `components/ui/glass-card.tsx` |
| Button | `components/ui/button.tsx` |
| StatusIndicator | `components/ui/status-indicator.tsx` |
| ScorePanel | `components/practice/ScorePanel.tsx` |
| Sidebar | `components/layout/sidebar.tsx` |

## 反模式

- 全页 `bg-white`、纯黑文字
- 演练中阻塞弹窗
- 霓虹渐变、游戏化仪表盘
- 偏离 token 的 ad-hoc 颜色

## 预览

浏览器打开 `showcase/index.html`，或 Open Design 项目 **222**（建议重命名为「销售训练设计体系」）。
