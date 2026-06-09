# /admin/personas 视觉分析

**wave**: admin | **截图数**: 1
**截图清单**：
- `screenshots/admin/admin-personas-1440.png` — 角色管理

**a11y 树要点**：
- 1 H1: "角色管理"
- 1 banner "Roleset 测试套件"
- 4 Roleset 卡片 + 4 角色卡片
- 0 console error

---

## P0（必须修）

### P0-1：测试套件标识泄漏
- **位置**：顶部 banner
- **原文**："Roleset **测试**套件"
- **影响**：admin 端再次暴露"测试"字样 — 跨 admin/agents /admin/personas /admin/users 同源
- **截图**：`admin-personas-1440.png`
- **修复方向**：与 /admin/agents P0-1 同方案（is_test_data flag 过滤）

---

## P1（1 周内）

### P1-1：4+4 卡片布局无视觉分组
- 上 4 (Roleset 列表) + 下 4 (角色列表) 用同一卡片样式
- 用户不知哪个是 Roleset 哪个是 Persona
- 修复：加 section header "Roleset 套件" / "Persona 角色"

### P1-1：角色名"金玉守护" / "上门生资颖" 生造词
- 含义不清
- 修复：内容治理

### P1-3：状态 tag 不可点
- "已发布" / "隐藏" 仅显示
- 修复：改为 dropdown toggle

## P2（可优化）

### P2-1：描述文案偏英文+技术
- "Roleset 是一组角色..." 是 dev 文档语言
- 修复：简化 + 用户友好

### P2-2：缺搜索
- 多套件多角色时无法快速定位

---

## 设计 token 实测

| 维度 | 实测值 | token | 偏差 |
|---|---|---|---|
| 主背景 | 浅灰 | ✅ | 0 |
| 卡片 | 白底 | ✅ | 0 |
| 圆角 | 24px | ✅ | 0 |
| 状态 tag | 浅绿 / 浅灰 | ✅ | 0 |

**结论**：100% token 化。

---

## 视觉层级评估

- **视线流**：H1 → 描述 → banner 套件 → 4 Roleset → 4 角色
- **CTA 强度**：右上 "新增角色" 主焦点；操作 icon 弱

## 一致性

- ✅ admin sidebar 切换正确
- ✅ 与 /admin/users /admin/agents 表格/卡片风格一致
- ❌ 测试套件泄漏同源

---

## 总结

/admin/personas 是**同源问题第 5 处**（test data 泄漏）。视觉本身工整，token 一致。
