# Token 层排版审计

> 数据源：`grep -rE` 全 `web/src/app/**/*.tsx`
> 实际页面样本：12 个（详见 `pages.json` audited 状态）
> 对比基准：`web/src/app/globals.css` `:root` 块

---

## 1. 色板 / 颜色系统

### 1.1 硬编码颜色（应全部走 token）

| 颜色 | 出现次数 | 出现位置 | 评价 |
|---|---|---|---|
| `#FAFAF9` | 2 | globals.css 自身 | ✅ token 定义 |
| `#64748b` | 2 | slate-500 同色 | ⚠️ 跳过（与 Tailwind 重复） |
| `#2563eb` | 2 | blue-600 同色 | ⚠️ 跳过 |
| `#10b981` | 2 | emerald-500 同色 | ⚠️ 跳过 |
| `#e2e8f0` | 1 | slate-200 同色 | ⚠️ 跳过 |

**结论**：**没有真正的硬编码颜色**（除 globals.css 自身外）。色板全部走 Tailwind 调色板 + CSS 变量。

### 1.2 Tailwind 调色板使用频率 Top 30

| 类名 | 次数 | 用途 |
|---|---|---|
| `text-slate-500` | 750 | 次要文本 |
| `text-slate-900` | 517 | 主文本 |
| `border-slate-200` | 317 | 主边框 |
| `text-slate-400` | 253 | 弱化文本 |
| `text-slate-600` | 249 | 副文本 |
| `text-slate-700` | 234 | 强副文本 |
| `bg-slate-50` | 205 | 浅背景 |
| `border-slate-100` | 145 | 弱边框 |
| `bg-slate-100` | 127 | 中背景 |
| `bg-blue-50` | 109 | 蓝软背景 |
| `bg-amber-50` | 96 | 警告软背景 |
| `bg-red-50` | 91 | 错误软背景 |
| `bg-slate-900` | 87 | 深背景（按钮） |
| `border-amber-200` | 79 | 警告边框 |
| `text-amber-700` | 75 | 警告文本 |
| `text-blue-700` | 73 | 蓝主文本 |
| `text-blue-600` | 73 | 蓝副文本 |
| `text-slate-800` | 70 | 强文本 |
| `text-amber-800` | 67 | 警告强文本 |
| `bg-emerald-50` | 59 | 成功软背景 |
| `text-red-700` | 57 | 错误文本 |
| `text-zinc-900` | 48 | 锌色主文本 |
| `text-red-600` | 47 | 错误副文本 |
| `text-emerald-700` | 46 | 成功文本 |
| `border-red-200` | 40 | 错误边框 |
| `border-emerald-200` | 38 | 成功边框 |
| `text-zinc-700` | 36 | 锌色副文本 |
| `text-zinc-500` | 35 | 锌色次文本 |
| `text-emerald-600` | 35 | 成功副文本 |

### 1.3 颜色用法矩阵

| 语义 | Token | 使用情况 | 评价 |
|---|---|---|---|
| 主文本 | `text-slate-900` / `text-zinc-900` | 517 + 48 = 565 | ⚠️ **slate 和 zinc 混用**，应统一 |
| 次文本 | `text-slate-500` | 750 | ✅ 单一 |
| 弱文本 | `text-slate-400` | 253 | ✅ 单一 |
| 边框 | `border-slate-200` | 317 | ✅ 主流 |
| 浅背景 | `bg-slate-50` | 205 | ✅ 主流 |
| 警告 | `bg-amber-50` / `border-amber-200` / `text-amber-700` | 96 + 79 + 75 | ✅ **三件套齐** |
| 错误 | `bg-red-50` / `border-red-200` / `text-red-700` | 91 + 40 + 57 | ✅ **三件套齐** |
| 成功 | `bg-emerald-50` / `border-emerald-200` / `text-emerald-700` | 59 + 38 + 46 | ✅ **三件套齐** |
| 蓝主 | `bg-blue-50` / `text-blue-700` | 109 + 73 | ✅ |

### 1.4 globals.css 定义的语义色（与 Tailwind 对比）

```css
/* globals.css 有 */
--color-bg-main
--color-bg-card
--color-text-primary
--color-text-secondary
--color-text-tertiary
--color-accent-blue
--color-accent-blue-soft
--color-accent-purple
--color-accent-purple-soft
--font-jakarta
--shadow-sm / card / float / glow
--radius-subtle / medium / full
```

**缺口**：
- ❌ 无 `--color-warn` / `--color-warn-soft`（amber 走 Tailwind 而非 token）
- ❌ 无 `--color-error` / `--color-error-soft`（red 走 Tailwind）
- ❌ 无 `--color-success` / `--color-success-soft`（emerald 走 Tailwind）
- ❌ 无 `--color-bg-code`（dev 工具页深色背景）

**结论**：globals.css 走的是"品牌色"路线（蓝紫），**状态色（success/warn/error）走 Tailwind 直调**。建议把 Tailwind 状态色抽到 globals.css 统一管理。

### 1.5 Slate vs Zinc 混用

```
text-slate-*: 750 + 517 + 317 + 253 + 249 + 234 + 205 + 145 + 127 + 87 + 70 = 2954 处
text-zinc-*:  48 + 36 + 35 = 119 处
```

**`zinc` 仅占 slate 的 4%**。建议：要么全部走 `slate`，要么全部走 `zinc`（zinc 比 slate 略偏冷）。**用 `--color-text-primary` 替代最干净**。

---

## 2. 字号阶

| 阶 | 类名 | 出现次数 | 用途推断 |
|---|---|---|---|
| xs | `text-xs` | 875 | label / 弱化文本 / chip / 表单说明 |
| sm | `text-sm` | 1087 | **主力**：正文 / 列表项 / 描述 |
| base | `text-base` | 54 | 强调正文 |
| lg | `text-lg` | 163 | 副标题 / 列表标题 |
| xl | `text-xl` | 52 | 子标题 |
| 2xl | `text-2xl` | 100 | 卡片标题 |
| 3xl | `text-3xl` | 39 | H1 / 大数字 |
| 4xl | `text-4xl` | 8 | 极少数 hero 数字 |

**评价**：
- ✅ 8 阶齐全
- ✅ 用 `text-sm` (1087) + `text-xs` (875) 撑起 80% 文字
- ⚠️ H1 用 `text-3xl` (39) — 应有专门 H1 类（如 `text-h1`）配 `font-bold`
- 字号阶在 TypeScript 里有校验，但缺 design doc

---

## 3. 间距阶

| 阶 | 出现次数 | 评价 |
|---|---|---|
| `gap-1` / `gap-2` / `gap-3` / `gap-4` / `gap-6` | 49+286+263+187+51 = 836 | ✅ 4/8 px 基准 |
| `p-3` / `p-4` / `p-5` / `p-6` / `p-8` | 102+257+103+197+80 = 739 | ✅ 12/16/20/24/32 px |
| `m-4` / `m-6` | 24+3 = 27 | ⚠️ **margin 用得少**，应多用 flex/grid gap |
| `p-0` | 17 | ✅ 合理 |
| `p-10` / `p-12` | 12+6 = 18 | ⚠️ 偏大，hero 才用 |

**评价**：
- ✅ 主间距用 4/8 px 基准
- ❌ `p-5` (103) 出现 — 是 20px 不在 4/8 基准上（除非当 24px-4px 用）
- ❌ `gap-3` 出现 263 次 — 12px 不在 8 基准上
- 建议：去掉 p-5 / gap-3，统一到 p-4 / gap-4

---

## 4. 圆角

| 阶 | 类名 | 出现次数 | 实测 px |
|---|---|---|---|
| none | `rounded` | 46 | 4px (Tailwind 默认) |
| sm | `rounded-md` | 1 | 6px |
| md | `rounded-lg` | 162 | 8px |
| lg | `rounded-xl` | 220 | 12px |
| xl | `rounded-2xl` | 261 | 16px |
| 2xl | `rounded-3xl` | 22 | 24px |
| full | `rounded-full` | 539 | 9999px |

**评价**：
- ⚠️ **8 个圆角档位**（4/6/8/12/16/24/9999px）— 偏多
- globals.css 只定义 3 档（16/24/9999），**实际使用 8 档**
- 建议收敛到 4 档：sm (8) / md (12) / lg (16) / full (9999)
- `rounded-md` 出现 1 次 = 几乎是误用

---

## 5. 阴影

| 类名 | 出现次数 | 实测 |
|---|---|---|
| `shadow-sm` | 30 | 0 1px 2px |
| `shadow-md` | 5 | 0 4px 6px |
| `shadow-lg` | 17 | 0 10px 15px |
| `shadow-xl` | 4 | 0 20px 25px |
| `shadow-card` | 7 | globals.css 自定义 |
| `shadow-slate-900` | 14 | 带颜色（多用于 login 页 card） |
| `shadow-none` | 2 | 关闭阴影 |

**评价**：
- ✅ 4 档标准 + 1 自定义
- ⚠️ `shadow-slate-900` 14 次 — 给阴影染色，**不在 token 体系**（globals.css 无对应）
- 建议：把 `shadow-slate-900` 改名 `shadow-float` 与 globals.css 一致

---

## 6. 字体

```css
/* globals.css */
--font-jakarta: "Avenir Next", "Segoe UI", "PingFang SC", "Microsoft YaHei", "Heiti SC", system-ui, sans-serif;
```

**评价**：
- ✅ 中英文 fallback 链完整
- ⚠️ "Avenir Next" 商业字体，仅 macOS 自带 — 部署到 Linux 服务器会 fallback
- 建议：主字体换 "Inter" 或 "system-ui"（更跨平台）

---

## 7. 总评

| 维度 | 评价 | 优先级 |
|---|---|---|
| 色板 | ⚠️ slate/zinc 混用 + 状态色未走 token | P1 |
| 字号阶 | ✅ 8 阶清晰 | — |
| 间距阶 | ⚠️ p-5 / gap-3 偏 4/8 基准 | P2 |
| 圆角 | ⚠️ 8 档偏多，建议收敛到 4 档 | P1 |
| 阴影 | ⚠️ shadow-slate-900 应改名 | P2 |
| 字体 | ⚠️ Avenir Next 商业字体跨平台差 | P1 |
| 状态色 | ❌ success/warn/error/code-bg 未在 token | P0 |
