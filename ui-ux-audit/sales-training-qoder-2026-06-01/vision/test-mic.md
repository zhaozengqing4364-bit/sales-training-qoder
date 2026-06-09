# /test-mic 视觉分析

**wave**: public | **viewport**: 1440 / 375 | **截图数**: 4
**截图清单**：
- `screenshots/public/test-mic-default-1440.png` — 未登录访问（被重定向到 /login）
- `screenshots/public/test-mic-authed-1440.png` — dev 登录后访问
- `screenshots/public/test-mic-authed-375.png` — 移动端（**P1 关键证据**）
- `screenshots/public/test-mic-devices-1440.png` — 点击"列出设备"后

**a11y 树要点**：
- H1 = "麦克风调试工具"
- 顶部 banner "开发工具 · 不属于学员训练主流程"（视觉标识 dev 页）
- 4 button：重新检测后端 / 开始录音 / 列出设备 / 清空日志 / 后端诊断
- 1 checkbox "直接监听"
- 1 console log 区域（无 role，**a11y 弱**）

---

## P0（必须修）

### P0-1：未登录访问 /test-mic 直接触发后端 401
- **位置**：路由保护
- **复现**：
  1. 未登录访问 /test-mic
  2. 页面被重定向到 /login
  3. **但重定向前**已经发起 `/api/v1/sessions/stats` 和 `/api/v1/scenarios?scenario_type=sales` 请求
  4. 2 个 401 错误进入 console
- **影响**：
  - 控制台被污染，掩盖真实错误
  - 后端 metrics 记录无效 401
  - 信息泄露（攻击者知道这两个 endpoint 存在）
- **截图**：`test-mic-default-1440.png`（实际是 /login 页，URL 已重定向）
- **修复方向**：
  - 在 middleware / 路由守卫里，**先重定向**再发请求
  - 或在 layout 层面预先检查 auth state，protected 页直接不渲染

### P0-2：移动端 4 个按钮 **字符级垂直换行**（用户无法阅读）
- **位置**：开始录音 / 列出设备 / 清空日志 / 后端诊断 4 个按钮
- **复现**：视口 375 宽度
- **现象**：
  - "开始录音" → "始" / "录" / "音" **逐字垂直堆叠**
  - "列出设备" → "列" / "出" / "设" / "备"
  - "清空日志" → "清" / "空" / "日" / "志"
  - "后端诊断" → "后" / "端" / "诊" / "断"
- **截图**：`test-mic-authed-375.png`
- **根因推断**：按钮宽度被挤压（`width: fit-content` + flex `flex-wrap: wrap` + `min-width` 缺失）
- **影响**：
  - 移动端 dev 工具**几乎不可用**
  - dev 排查效率严重下降
- **修复方向**：
  - 移动端改为单列纵向排列（`flex-col`）
  - 或加 `whitespace-nowrap` + 横向滚动
  - 或按钮文本改为短词（"录音" / "设备" / "清空" / "诊断"）

---

## P1（1 周内）

### P1-1：英文混排
- **位置**：console log 区域
- **现象**：
  - "Checking backend connectivity..."（英文）
  - "✅ 后端健康检查通过"（中文）
  - "Found 1 audio input devices"（英文）
  - "1. Unknown (...)"（英文 + 数据缺失）
- **修复方向**：统一 i18n；至少把 device name fallback 写好

### P1-2：未登录访问的中间态闪烁
- **位置**：/test-mic 路由
- **现象**：进入 /test-mic → 一闪 /login → /login 完整渲染
- **修复方向**：layout 用 loading.tsx 或 redirect

## P2（可优化）

### P2-1：开发工具 banner 视觉权重弱
- 顶部 "开发工具 · 不属于学员训练主流程" 用橙色描边 chip，OK 但小

### P2-2：频谱区域 idle 态用 placeholder 圆点
- 实际未录音时显示一组 "●" 字符，体验略糙
- 建议：未录音时显示"开始录音后此处显示波形"占位文案 + 空频谱图

### P2-3：调试说明区用黄色背景
- 颜色 `#FEF3C7`-ish（实测未确认）走 Tailwind `bg-amber-50` 之类
- ⚠️ **警告色未在 globals.css token 出现**（与 /login 的开发者入口同源问题）

## P3（可选）

### P3-1：未提供"导出日志"功能
- dev 排查需要 copy log 到工单
- 加"复制全部日志"按钮

---

## 设计 token 实测

| 维度 | 实测值 | token 体系 | 偏差 |
|---|---|---|---|
| 主背景 | #FAFAF9 | ✅ `--color-bg-main` | 0 |
| 卡片 | #FFFFFF | ✅ `--color-bg-card` | 0 |
| 成功状态 | 绿色"在线" | ⚠️ `--color-success` 未定义 | **token 漏** |
| 警告状态 | 黄色调试说明背景 | ⚠️ `--color-warn` 未定义 | **token 漏** |
| Console 区域背景 | 深色 #0F172A 之类 | ⚠️ `--color-bg-code` 未定义 | **token 漏** |

**结论**：表单类页 100% token；**dev 工具页暴露 3 个 token 缺口**（success / warn / code-bg）。

---

## 视觉层级评估

- **视线流**：banner → H1 → 副标题 → 状态卡 → 频谱卡 → 操作按钮 → 日志 → 调试说明 ✅
- **CTA 强度**：开始录音（紫填充）vs 其他（白底）—— 唯一视觉焦点 ✅

## 一致性（与 /login / /forgot-password / /reset-password 对比）

- ✅ 主色用法一致
- ❌ **移动端按钮布局不一致**（其他页 1-2 个按钮，无问题；本页 4 个按钮就崩）
- ❌ dev/警告色硬编码，与 form 页不一致

---

## 总结

`/test-mic` 是项目**目前问题最严重的页面**：
- 2 个 P0（401 泄露 + 移动端按钮不可读）
- 暴露 token 体系在 dev 工具场景的缺失
- 提醒：dev 工具的视觉优先级低，但**移动端可用性是硬伤**，可能影响支持团队出差排查
