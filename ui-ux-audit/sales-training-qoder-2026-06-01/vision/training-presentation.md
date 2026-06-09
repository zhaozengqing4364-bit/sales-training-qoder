# /training/presentation 视觉分析

**wave**: dashboard | **viewport**: 1440 | **截图数**: 1
**截图清单**：
- `screenshots/dashboard/training-presentation-default-1440.png`

**a11y 树要点**：
- 1 H1: "演讲与表达训练"
- 1 link: "进入演讲演练"
- 0 console error
- 1 agent 卡 "ppt训练"

---

## P0 / P1
- 无重大问题

## P2（可优化）

### P2-1：大量空白显得"功能贫瘠"
- **位置**：主区除 1 张卡外全是空白
- **现象**：1440 桌面视口，主区只有 ~30% 有内容
- **影响**：用户感觉"产品还没做出来"
- **修复方向**：
  - 若场景会持续增加：加"敬请期待" / "新场景筹备中" 提示
  - 若场景为终态：改用 hero card 居中，节省垂直空间

### P2-2：单卡片无对比
- 销售对练 7 个，演讲练习 1 个
- /training 主页有"1 个场景"标记，但**进 /training/presentation 后无对应引导**
- 修复：在 /training 主页"演讲练习"卡上注明"开发中"或"试运行"

### P2-3：agent 名 "ppt训练" 全小写
- 其他 agent 名是中文（"售前训练智能体"）
- "ppt训练"小写突兀
- 修复：改为"PPT 训练"（PPT 全大写是惯例）

## P3（可选）

### P3-1：未提供"上传 PPT 文件"入口
- 演讲练习场景应该让用户先传 PPT
- 当前没有上传入口

---

## 设计 token 实测

- ✅ 100% token 化（同 /training/sales）
- 圆角 24px / 卡片白底 / 阴影浮起 / 中等 chip 浅蓝 — 全部对齐

---

## 一致性

- ✅ 与 /training/sales 100% 一致（同组件、同布局）
- 验证了"<场景类页>"的模板设计已稳定

---

## 总结

/training/presentation 视觉无问题，但**功能单一 + 大量空白** 显出产品成熟度。
此页主要价值：**确认了 agent 卡组件的复用性**（同一组件在 /training/sales 和 /training/presentation 用法一致）。
