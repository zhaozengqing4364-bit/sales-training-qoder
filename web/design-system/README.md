# 销售训练前端设计体系

独立于 Open Design「石犀训练」原型的 **Modern Soft UI** 令牌仓库，与 `web/src` 实现对齐。

## 目录

```
design-system/
└── sales-trainer/          # 设计体系 ID: sales-trainer-modern-soft-ui
    ├── DESIGN.md           # 设计语言规范（L1 设计地图）
    ├── tokens/             # CSS + JSON 令牌（单一真源）
    │   ├── index.css       # 聚合入口
    │   ├── colors.css
    │   ├── typography.css
    │   ├── spacing.css
    │   ├── radius.css
    │   ├── shadow.css
    │   ├── motion.css
    │   ├── glass.css
    │   ├── semantic.css
    │   ├── score.css
    │   ├── layout.css
    │   └── tokens.json     # W3C Design Tokens 格式
    ├── primitives/
    │   └── primitives.css  # 组件 primitive 类
    └── showcase/
        └── index.html      # 本地可视化预览
```

## 使用方式

### 在 Tailwind / globals 中引用

```css
@import "../design-system/sales-trainer/tokens/index.css";
```

### 在 Open Design 中预览

Open Design 项目 **222**（建议在 OD 中重命名为「销售训练设计体系」）与本目录结构同步。

## 与代码库映射

| 令牌 | 当前实现 |
|------|----------|
| 色彩 / 阴影 / 圆角 | `web/src/app/globals.css` |
| 原则 | `.kiro/steering/frontend-principles.md` |
| GlassCard | `web/src/components/ui/glass-card.tsx` |
| Button | `web/src/components/ui/button.tsx` |
| ScorePanel | `web/src/components/practice/ScorePanel.tsx` |

## 命名约定

所有 CSS 变量前缀 `--st-`（Sales Trainer），避免与第三方或 legacy `--color-*` 冲突。迁移时可逐步将 `globals.css` 别名指向 `--st-*`。
