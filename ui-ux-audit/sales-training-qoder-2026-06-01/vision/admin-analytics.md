# /admin/analytics 视觉分析

**wave**: admin | **截图数**: 1
**截图清单**：
- `screenshots/admin/admin-analytics-1440.png` — 数据分析

**a11y 树要点**：
- 1 H1: "数据分析"
- 时间 tab: 7天/30天/全部
- 4 metric cards + 1 weekly card 4 sub-metrics
- 0 console error

---

## P0（必须修）

### P0-1：4 metric 数字无标签/单位
- **位置**：4 metric cards
- **现象**：显示"22" / "0" / "93" / "70.9"，**无单位标签**（次？小时？%？）
- **影响**：admin 不知道"22"是什么
- **截图**：`admin-analytics-1440.png`
- **修复方向**：
  - 每个 metric 加主标签（"日均会话" / "完成率" / "活跃用户" / "平均分"）
  - 0 数据用浅灰底 + "暂无数据" 文案而非 0

---

## P1（1 周内）

### P1-1：未渲染图表
- 项目装了 recharts 但首屏只有数字卡，**没图**
- 修复：至少加一个 trend line（recharts ResponsiveContainer）

### P1-2：时间 tab 视觉权重等同
- 修复：7天（默认）加 primary 强调

### P1-3："本周经营节奏" 卡片 4 子 metric 都 0
- 0 0 0 0 — 强烈空态感
- 修复：0 用浅灰字，主体改为 sparkline 占位

## P2（可优化）

### P2-1：缺对比
- 与"上周" / "上月" 环比
- 修复：每个 metric 旁加 ↑↓% 趋势

### P2-2：缺 export 报告
- 仅"导出数据"是 csv，缺 PDF 报告

---

## 设计 token 实测

| 维度 | 实测值 | token | 偏差 |
|---|---|---|---|
| 主背景 | 浅灰渐变 | ✅ | 0 |
| 时间 tab active | 蓝 | ✅ | 0 |
| Metric 卡 | 白底 | ✅ | 0 |

**结论**：100% token 化。

---

## 总结

/admin/analytics 是**项目 chart 重灾区**：
- 装 recharts 但没渲染图
- 4 metric 数字孤立
- 缺对比、缺趋势、缺 0 数据视觉
- 是 admin 决策页，**应该最丰富，实际最单薄**
