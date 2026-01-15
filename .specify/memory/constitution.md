# AI 智能演练系统 - 项目原则 (Constitution)

<!--
SYNC IMPACT REPORT
==================
Version change: 1.0.1 → 1.1.0
Modified principles:
  - Deployment Strategy section updated to remove Docker dependency
Added sections: None
Removed sections: None
Templates requiring updates:
  - .specify/templates/plan-template.md (deployment section)
  - specs/001-ai-practice-system/plan.md (existing implementation plan)
  - CLAUDE.md (development guidelines)
  - README.md (if exists, deployment instructions)
Follow-up TODOs:
  - Update deployment documentation to reflect bare metal/virtualenv setup
  - Verify all Docker references removed from codebase
-->

## 核心原则

### I. 用户体验永不中断 (NON-NEGOTIABLE)

**定义**：在演练过程中，无论后台发生任何错误（断网、超时、报错），前端界面永远不允许弹窗报错！

**实施规则**：
- 所有错误必须通过以下方式处理：
  1. **自动重连**：网络断开时尝试静默重连
  2. **垫场话术**：AI 播放缓冲性语言（"请稍等..."、"让我想想..."）
  3. **优雅降级**：必要时切换到浏览器原生语音或其他备用方案
  4. **后台记录**：所有错误必须记录到日志，但不影响用户体验

**验收标准**：
- 用户在任何情况下都不会看到错误弹窗
- 对话流不会因为技术问题而中断
- 用户感知到的"故障"为 0

---

### II. 实时性优先

**定义**：语音交互系统的核心价值在于流畅的实时对话体验。

**实施规则**：
- **端到端延迟目标**：<300ms（从用户停止说话到 AI 开始回应）
- **流式处理**：ASR 采用流式识别，不等待用户说完才开始处理
- **打断响应**：关键词检测和打断判断必须在 100ms 内完成
- **性能监控**：实时监控各环节延迟，超标立即告警

**验收标准**：
- 95% 的交互延迟 <300ms
- 用户感知不到"卡顿"

---

### III. 模块化场景独立

**定义**：两个核心场景（PPT 演练、销售对练）必须独立演进，互不影响。

**实施规则**：
- **目录结构**：按功能分模块（`presentation_coach/`, `sales_bot/`, `common/`）
- **接口隔离**：每个场景有独立的 API 端点、WebSocket 连接
- **数据隔离**：不同场景的数据存储在同一集合中但通过 `scenario_type` 字段区分
- **独立部署**：理论上可以单独发布某个场景而不影响另一个

**验收标准**：
- 修改销售对练逻辑不需要触碰 PPT 演练代码
- 新增演练场景只需复制现有模块并修改业务逻辑

---

### IV. 容错与恢复

**定义**：分布式系统必然故障，必须在架构层面设计容错机制。

**实施规则**：
- **所有错误场景必须处理**：
  - ASR 识别失败 → 使用基础识别或提示用户重说
  - TTS 生成失败 → 使用备用 TTS 或文本显示
  - LLM API 超时/限流 → 使用预设回复或降级到简单规则
  - WebSocket 连接断开 → 自动重连 + 恢复上下文
  - PPT 解析失败 → 提示人工处理或使用占位符
  - 向量检索失败 → 退化为基于关键词的搜索
- **重试机制**：所有外部 API 调用必须包含指数退避重试
- **熔断机制**：连续失败后暂时停止调用该服务，快速失败

**验收标准**：
- 任何单一服务故障不会导致整个系统崩溃
- 用户可以在部分功能降级的情况下继续使用

---

### V. 成本控制

**定义**：在保证质量的前提下，优先选择低成本方案。

**实施规则**：
- **优先开源**：ASR 使用 qwen3-asr-flash（免费），TTS 使用 Edge-TTS（免费）
- **按需调用**：LLM API 只在必要时调用，避免无意义的消耗
- **数据生命周期管理**：语音数据留存一年后自动归档或删除
- **监控成本**：实时监控 API 调用成本，设置预算告警

**验收标准**：
- 单次演练成本 <¥1（包含所有 API 调用）
- 月度运营成本可预测且可控

---

### VI. 数据隐私与合规

**定义**：企业培训数据包含敏感信息，必须严格保护。

**实施规则**：
- **数据加密**：所有传输数据使用 TLS 加密
- **访问控制**：演练记录只能被本人和管理员访问
- **数据最小化**：只收集必要的语音数据，避免过度采集
- **删除权**：用户可以删除自己的演练记录
- **日志脱敏**：错误日志中不能包含用户的语音内容或敏感信息

**验收标准**：
- 符合企业内部数据安全规范
- 通过安全审计

---

### VII. 可观测性

**定义**：分布式系统必须具备完善的监控和诊断能力。

**实施规则**：
- **结构化日志**：所有日志使用 JSON 格式，包含 `trace_id`
- **关键指标**：实时监控延迟、错误率、并发数、API 调用量
- **链路追踪**：每个请求从 WebSocket 到 ASR/LLM/TTS 的完整链路可追踪
- **用户行为分析**：记录演练完成率、平均时长、评分分布

**验收标准**：
- 任何问题可以在 5 分钟内定位根因
- 系统健康状况一目了然

---

## 开发流程

### 测试策略

- **单元测试**：核心业务逻辑（打断判断、评分算法）必须有单元测试
- **集成测试**：WebSocket → ASR → LLM → TTS 的完整流程必须有集成测试
- **性能测试**：支持 50 个并发会话的场景必须通过压力测试

### 代码审查

- **所有 PR 必须审查**：即使是个人项目，也必须通过自我审查清单
- **关键代码双人审查**：语音核心模块、错误处理逻辑必须有人复核

### 部署策略

- **本地虚拟环境部署**：使用 Python venv 或 conda 管理依赖，直接运行服务
- **进程管理**：使用 systemd、supervisor 或 PM2 进行进程守护
- **蓝绿部署**：新版本先在备用进程启动，验证后切换流量
- **回滚预案**：每次部署前必须准备回滚脚本和数据库迁移回滚

**部署命令参考**：
```bash
# 后端部署
cd backend
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows
pip install -r requirements.txt
uvicorn src.main:app --host 0.0.0.0 --port 8000

# 前端部署
cd frontend
npm install
npm run build
# 将 dist/ 目录部署到 Nginx/Apache 静态服务器
```

---

## 技术约束

### 必须使用

**语音层**：
- **ASR 引擎**：qwen3-asr-flash（流式识别，低延迟，支持实时打断）
- **TTS 引擎**：Microsoft Edge-TTS（免费，自然度高）
- **通信协议**：WebSocket（全双工，支持双向打断）

**后端层**：
- **后端框架**：FastAPI（高性能异步）
- **WebSocket**：FastAPI 原生 WebSocket 支持
- **向量数据库**：ChromaDB（快速开发）
- **AI 框架**：LangChain/LangSmith

**前端层**：
- **前端组件库**：Ant Design Mobile

### 禁止使用

- **禁止使用同步阻塞调用**：所有 I/O 操作必须异步
- **禁止硬编码配置**：所有配置通过环境变量或配置文件管理
- **禁止在生产环境打印敏感信息**
- **禁止使用 Docker 容器化部署**：采用传统虚拟环境部署方式

---

## 版本

**Version**: 1.1.0 | **Ratified**: 2025-01-10 | **Last Amended**: 2025-01-10
**Changelog**:
- v1.1.0: 移除 Docker 部署要求，改用本地虚拟环境部署（MINOR：部署策略变更）
- v1.0.1: 明确 ASR 引擎为 qwen3-asr-flash，优化技术约束分类
- v1.0.0: 初始版本
