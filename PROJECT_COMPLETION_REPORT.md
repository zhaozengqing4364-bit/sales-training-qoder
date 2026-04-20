# 销售训练 Qoder - 项目功能完成度报告

**生成日期**: 2026-04-08  
**项目阶段**: 功能开发中期，存在大量待修复和待完善项  
**报告范围**: 全栈功能完成度 + 系统审计问题 + 待实现清单

---

## 一、项目概述

### 1.1 项目定位
**项目名称**: 企业级 AI 智能演练系统（销售训练 Qoder）  
**核心价值**: 基于 Web(H5)端的企业级 AI 员工陪练平台，集成于企业微信工作台  
**核心场景**: 
- PPT 演讲复盘（实时语音交互 + 要点追踪）
- 高压销售对练（AI 客户角色扮演 + 实时反馈）

### 1.2 技术架构
**前端**: Next.js 16.1.1 + React 19.2.3 + TypeScript + Tailwind CSS  
**后端**: FastAPI + SQLAlchemy 2.0 + PostgreSQL + Redis  
**实时通信**: WebSocket（全双工语音交互）  
**AI 服务**: StepFun Realtime（双轨语音）、阿里云 ASR/TTS  
**向量存储**: ChromaDB（知识库检索）  
**架构模式**: 模块化单体架构（presentation_coach、sales_bot、common 独立演进）

### 1.3 开发模式
Spec-Driven Development with .kiro steering system

---

## 二、已完成功能清单

### 2.1 核心业务功能（完成度：70%）

#### ✅ PPT 演练场景
- **PPT 上传与解析**
  - ✅ PPT 文件上传（支持 PPTX 格式）
  - ✅ OCR 文本提取
  - ✅ 页面图像存储
  - ✅ 知识库向量化
  - ✅ 版本管理

- **演练配置**
  - ✅ 必讲点配置（按页面）
  - ✅ 禁忌词配置（全局/页面级）
  - ✅ PPT AI 策略配置
  - ✅ 提示词角色解析

- **实时演练**
  - ✅ WebSocket 实时通信
  - ✅ 语音识别（阿里云 ASR + 降级链）
  - ✅ 语音合成（阿里云 TTS + 降级链）
  - ✅ 实时打断检测
  - ✅ 要点追踪（语义匹配 + AHO 算法）
  - ✅ 禁忌词检测
  - ✅ 页面导航
  - ✅ 暂停/恢复/结束

- **评估报告**
  - ✅ 多维度评分（逻辑、准确度、完整度）
  - ✅ 详细反馈（做得好、需改进、建议）
  - ✅ 对话记录保存
  - ✅ 音频录制与存储

#### ✅ 销售对练场景
- **Agent 平台**
  - ✅ Agent 管理（创建、编辑、删除）
  - ✅ Persona 管理（角色配置）
  - ✅ 知识库关联
  - ✅ 语音运行时配置

- **实时对话**
  - ✅ StepFun Realtime 双轨语音模式
  - ✅ 实时模糊词检测
  - ✅ 销售阶段识别
  - ✅ 实时评分（专业度、沟通技巧、销售流程、异议处理、成交能力）
  - ✅ 知识库检索（RAG）
  - ✅ 暂停/恢复/结束

- **评估报告**
  - ✅ 综合评分
  - ✅ 维度评分
  - ✅ 详细反馈
  - ✅ 对话摘要

#### ✅ 知识库管理
- ✅ 知识库上传与解析
- ✅ RAG Profile 配置
- ✅ 检索策略配置
- ✅ 意图规则配置
- ✅ 实体别名配置
- ✅ 排序配置
- ✅ 分块预设配置

### 2.2 用户端功能（完成度：75%）

#### ✅ 认证与授权
- ✅ 登录页面（企业微信 OAuth + 开发者登录）
- ✅ 密码重置流程（基础实现）
- ✅ 会话管理
- ✅ 权限控制（user/admin/support）

#### ✅ 用户仪表板
- ✅ 首页（训练场景入口）
- ✅ 历史记录列表
- ✅ 排行榜
- ✅ 个人中心
- ✅ 支持页面

#### ✅ 训练流程
- ✅ Agent 详情页
- ✅ 练习会话页（实时语音交互）
- ✅ 会话报告页
- ✅ 回放功能

### 2.3 管理端功能（完成度：80%）

#### ✅ 管理后台
- ✅ 管理首页（系统概览）
- ✅ Agent 管理
- ✅ Persona 管理
- ✅ 知识库管理
- ✅ PPT 管理
- ✅ PPT AI 策略管理
- ✅ 提示词管理
- ✅ 语音运行时配置
- ✅ 用户管理
- ✅ 演练记录
- ✅ 数据分析
- ✅ 系统设置
- ✅ 日志查看
- ✅ RAG Profile 管理
- ✅ 检索策略管理

### 2.4 技术基础设施（完成度：85%）

#### ✅ 后端服务
- ✅ FastAPI 应用框架
- ✅ WebSocket 基础设施
- ✅ SQLAlchemy Async ORM
- ✅ PostgreSQL 数据库
- ✅ Redis 缓存
- ✅ Alembic 数据库迁移
- ✅ 结构化日志（structlog）
- ✅ 错误处理（Result[T] 模式）
- ✅ 熔断器（circuit_breaker）
- ✅ 重试机制（backoff）
- ✅ 速率限制（session_limiter、api_limiter）
- ✅ 音频服务（ASR/TTS 工厂模式）
- ✅ AI 服务（LLM、Embedding、ConfigManager）
- ✅ 向量存储（ChromaDB）
- ✅ OSS 存储（阿里云）

#### ✅ 前端基础设施
- ✅ Next.js 应用框架
- ✅ React 组件库
- ✅ Tailwind CSS 样式
- ✅ Zustand 状态管理
- ✅ API 客户端（统一错误处理）
- ✅ WebSocket 客户端（usePracticeWebSocket）
- ✅ 音频录制（useAudioRecorder）
- ✅ 音频播放（useStreamingAudioPlayer）
- ✅ 音频可视化（audio-visualizer、audio-waveform）
- ✅ 错误边界（ErrorBoundary）
- ✅ 路由保护（useAuthProtection）
- ✅ 主题切换（useTheme）

#### ✅ 测试基础设施
- ✅ 后端测试（pytest + pytest-asyncio）
- ✅ 前端测试（Vitest）
- ✅ 契约测试
- ✅ 集成测试
- ✅ 性能测试（50 并发）

---

## 三、待实现功能清单

### 3.1 核心业务功能缺口（完成度：70% → 90%）

#### ❌ PPT 演练场景
- **六维评分与长时段报告**（当前任务计划 Phase 4）
  - ❌ 10-30 分钟讲解的六维评分
  - ❌ 长时段报告生成
  - ❌ 复用 ComprehensiveReportService

- **训练友好降级**
  - ❌ KB 强制模式可配置（从 strict block 改为 coach mode）
  - ❌ 单轮提问数限制（指令编译层 + 输出层兜底）

- **用户词典 / 同音词归一化**（当前任务计划 Phase 3）
  - ❌ 用户词典功能
  - ❌ 同音词归一化
  - ❌ ASR final transcript → grounding → scoring → persistence 全链路

- **检索增强能力**（当前任务计划 Phase 5）
  - ❌ 检索链路增强
  - ❌ 运行时配置

#### ❌ 销售对练场景
- **StepFun 最新默认模型切换**（当前任务计划 Phase 1）
  - ❌ StepFun 最新默认模型切换后的系统化落地

### 3.2 用户端功能缺口（完成度：75% → 90%）

#### ❌ 首页优化
- ❌ 硬编码内容清理
- ❌ 空壳动作收口（下载报告、设定目标、分享分析、筛选）
- ❌ 新手 onboarding 入口（最小 3 步）
- ❌ 版本/更新弹窗内容来源校正

#### ❌ 认证与个人中心
- ❌ Password reset 正式化（PasswordResetToken 模型、migration、EmailService）
- ❌ Profile 修改密码体验闭合（当前只是重定向到忘记密码）
- ❌ 语速偏好持久化（当前 try/catch 静默忽略）
- ❌ 通知开关 / 摆设项的 disposition

#### ❌ Learner 导航与反馈
- ❌ 统一反馈入口（联系管理员）
- ❌ 角色/权限说明最小文案
- ❌ learner shell 导航一致性检查

#### ❌ 训练前预期管理
- ❌ 训练前目标/评价标准/角色简介最小预告
- ❌ 暂停/恢复/结束失败的用户可理解文案
- ❌ test-mic 页的可访问性约束（隐藏/标记开发工具）

#### ❌ 文本输入模式
- ❌ 文本输入模式（当前仅支持语音，需要 spike 决策）

### 3.3 管理端功能缺口（完成度：80% → 95%）

#### ❌ 管理后台功能
- ❌ 公告系统（按钮存在但功能未实现）
- ❌ 系统监控数据（当前硬编码，需要集成 Prometheus）
- ❌ 全局搜索功能（搜索框存在但逻辑未实现）
- ❌ 日志导出功能（按钮存在但功能未实现）

### 3.4 技术基础设施缺口（完成度：85% → 95%）

#### ❌ 前端 hygiene
- ❌ 前端日志出口统一化（console.* 清点、分类、收口）
- ❌ 原生弹窗清理（alert/confirm 替换为 Dialog）
- ❌ window.location 跳转清理（统一到 router）
- ❌ Learner error/loading 覆盖补齐
- ❌ 响应式/a11y/timezone baseline

#### ❌ 后端安全与稳定性
- ❌ API 错误契约统一（减少裸 HTTPException）
- ❌ RBAC 细粒度权限检查
- ❌ 日志脱敏（token、password、PII）
- ❌ Session lifecycle 并发安全 proof
- ❌ Practice WebSocket 复杂度收口
- ❌ 文件上传并发处理
- ❌ 资源竞争条件处理
- ❌ 分布式锁机制

#### ❌ 性能与优化
- ❌ 数据库性能基线 discovery（N+1、索引、slow query）
- ❌ 前端性能优化（代码分割、图片优化、Service Worker）
- ❌ 后端性能优化（查询索引、缓存策略、响应时间监控）
- ❌ WebSocket 性能优化（消息压缩、连接池管理）

#### ❌ 安全与合规
- ❌ 依赖版本安全漏洞扫描
- ❌ 依赖许可证合规性检查
- ❌ 依赖更新策略
- ❌ 数据库备份策略
- ❌ 故障恢复流程
- ❌ 灾难恢复演练

#### ❌ 可观测性
- ❌ OpenAPI/Swagger 自动生成文档
- ❌ 分布式追踪完善
- ❌ 性能指标监控
- ❌ 错误率监控告警

---

## 四、系统审计问题清单

### 4.1 高优先级问题（需立即修复）

#### 🔴 前端 UX 问题
1. **使用 alert() 和 confirm() 弹窗**
   - 影响文件：`web/src/app/admin/rag-profiles/page.tsx`、`web/src/app/admin/records/page.tsx`、`web/src/app/admin/personas/[id]/page.tsx`
   - 影响：用户体验中断，违反"用户体验永不中断"原则
   - 修复方案：使用 Radix UI Dialog 组件替代

2. **录音按钮防抖逻辑不足**
   - 影响文件：`web/src/app/(user)/practice/[sessionId]/page.tsx`
   - 影响：可能导致重复录音开始
   - 修复方案：增加防抖时间至 500ms，添加更严格的状态检查

#### 🔴 后端 API 问题
1. **使用 HTTPException 而非 Result[T] 模式**
   - 影响文件：`backend/src/prompt_templates/api/routes.py`（13 处）、`backend/src/main.py`、`backend/src/presentation_coach/api/presentations.py`（8 处）
   - 影响：错误处理不统一，违反"用户体验永不中断"原则
   - 修复方案：统一使用 Result.fail() 包装错误

2. **会话状态流转竞态条件**
   - 影响文件：`backend/src/common/db/session_lifecycle.py`
   - 影响：并发操作时可能导致状态不一致
   - 修复方案：添加数据库行锁或乐观并发控制

#### 🔴 前后端联调问题
1. **API 错误处理不统一**
   - 影响文件：`web/src/lib/api/client.ts` + 后端多个 API 路由
   - 影响：前端错误处理可能失效
   - 修复方案：统一所有 API 的错误响应格式，添加 API 契约测试

#### 🔴 权限控制问题
1. **权限检查不够细粒度**
   - 影响文件：`backend/src/admin/api/` 下的多个路由
   - 影响：可能存在越权访问风险
   - 修复方案：实现基于资源的权限检查（RBAC），添加权限审计日志

2. **敏感信息可能通过日志泄露**
   - 影响文件：多个日志输出位置
   - 影响：数据隐私合规风险
   - 修复方案：实现日志脱敏中间件，对 token、密码等敏感字段进行掩码

### 4.2 中优先级问题（近期修复）

#### 🟡 前端代码规范
1. **使用 console.log/console.error 而非结构化日志**
   - 影响文件：多个前端组件
   - 影响：生产环境可能泄露敏感信息
   - 修复方案：统一使用 `@/lib/debug` 模块

2. **使用 window.location 直接跳转**
   - 影响文件：多个前端组件
   - 影响：页面跳转不经过 Next.js 路由系统
   - 修复方案：统一使用 useRouter hook

3. **移动端布局可能存在溢出**
   - 影响文件：多个页面
   - 影响：移动端用户体验
   - 修复方案：增加移动端专用样式测试

#### 🟡 后端代码规范
1. **使用 print() 而非 logger**
   - 影响文件：`backend/src/evaluation/schemas.py`、`backend/src/agent/capabilities/registry.py`、`backend/src/common/ai/encryption.py`
   - 影响：生产环境日志不规范
   - 修复方案：统一使用 get_logger()

2. **异常处理不够细致**
   - 影响文件：`backend/src/prompt_templates/models.py`、`backend/src/presentation_coach/services/interruption_detector.py`
   - 影响：难以定位具体错误
   - 修复方案：捕获具体的异常类型，记录详细的错误堆栈

3. **TODO 标记未处理**
   - 影响文件：`backend/src/evaluation/services/staged_evaluation.py`
   - 影响：代码可维护性
   - 修复方案：完成 TODO 标记的功能或转换为 Issue

#### 🟡 WebSocket 通信问题
1. **WebSocket 连接管理复杂度高**
   - 影响文件：`web/src/hooks/use-practice-websocket.ts`（844 行）、`backend/src/sales_bot/websocket/stepfun_realtime_handler.py`（4511 行）
   - 影响：维护困难
   - 修复方案：进一步拆分模块，考虑使用状态机模式

2. **WebSocket 重连逻辑不够健壮**
   - 影响文件：`web/src/hooks/use-practice-websocket.ts`
   - 影响：网络不稳定时重连策略不够智能
   - 修复方案：实现指数退避重连策略，增加网络状态检测

### 4.3 低优先级问题（逐步优化）

#### 🟢 视觉一致性
1. **使用 bg-white 而非 bg-stone-50**
   - 影响文件：多个前端组件
   - 影响：视觉不一致
   - 修复方案：统一使用 bg-stone-50 或 bg-white/60

#### 🟢 数据库设计
1. **UUID 使用 String(36) 存储**
   - 影响文件：`backend/src/common/db/models.py`
   - 影响：性能略有损失
   - 修复方案：当前方案合理，保持不变

#### 🟢 功能缺失
1. **公告系统未实现**
   - 影响：管理功能不完整
   - 修复方案：实现公告数据模型、CRUD API、前端展示

2. **系统监控数据为硬编码**
   - 影响：监控数据不准确
   - 修复方案：集成真实的系统监控 API（如 Prometheus）

3. **全局搜索功能未实现**
   - 影响：用户体验
   - 修复方案：实现全文搜索 API、前端搜索结果展示

4. **日志导出功能未实现**
   - 影响：运维不便
   - 修复方案：实现日志导出 API，支持多种格式

---

## 五、性能与质量指标

### 5.1 性能目标 vs 实际情况

| 指标 | 目标 | 当前状态 | 差距 |
|------|------|----------|------|
| 端到端延迟（用户停止说话 → AI 回应） | <300ms (95%) | 未验证 | 需性能测试 |
| ASR 流式延迟 | <200ms | 已实现阿里云 ASR + 降级链 | 需验证 |
| 打断检测 | <100ms | 已实现 | 需验证 |
| 并发会话数 | 50 | 未验证 | 需性能测试 |
| 页面加载时间 | <2s | 未验证 | 需性能测试 |
| 单次演练成本 | <¥1 | 未监控 | 需成本追踪 |

### 5.2 代码质量指标

| 指标 | 目标 | 当前状态 |
|------|------|----------|
| 前端测试覆盖率 | >80% | 未统计 |
| 后端测试覆盖率 | >80% | 未统计 |
| 代码规范检查 | 100% 通过 | 部分违规 |
| 类型检查 | 100% 通过 | 部分违规 |

---

## 六、部署与运维现状

### 6.1 已实现
- ✅ Docker Compose 编排
- ✅ 环境变量配置（.env.example）
- ✅ 数据库迁移（Alembic）
- ✅ 基础日志（structlog）

### 6.2 待实现
- ❌ 数据库备份策略
- ❌ 故障恢复流程
- ❌ 灾难恢复演练
- ❌ 监控告警系统
- ❌ CI/CD 流程
- ❌ 生产环境部署脚本

---

## 七、文档与可维护性

### 7.1 已完成文档
- ✅ CLAUDE.md（项目指导文档）
- ✅ AGENTS.md（Codex 项目指令）
- ✅ api-spec.md（API 规格说明）
- ✅ specs/001-ai-practice-system/（功能规格）
- ✅ docs/roadmap/（路线图）
- ✅ docs/api-contract/（API 契约）
- ✅ docs/explain/（业务逻辑说明）
- ✅ SYSTEM_AUDIT_REPORT.md（系统审计报告）
- ✅ .gsd/plans/GSD_PLAN_system-audit-repair.md（修复计划）

### 7.2 待完善文档
- ❌ 部署文档
- ❌ 运维手册
- ❌ 故障排查指南
- ❌ API 文档（OpenAPI/Swagger 自动生成）
- ❌ 代码注释（部分复杂逻辑缺少注释）

---

## 八、优先级建议

### 8.1 立即执行（本周）
1. 修复高优先级前端 UX 问题（alert/confirm 清理）
2. 修复高优先级后端 API 问题（Result[T] 模式统一）
3. 完成当前任务计划 Phase 1（StepFun 最新模型切换）

### 8.2 近期执行（本月）
1. 完成当前任务计划 Phase 2-5（KB 降级、用户词典、PPT 六维评分、检索增强）
2. 执行系统审计修复计划 M1-M2（审计归一化、Learner 入口与体验闭环）
3. 修复中优先级代码规范问题

### 8.3 中期执行（下季度）
1. 执行系统审计修复计划 M3-M6（Frontend hygiene、Auth/API 安全、实时状态、性能 discovery）
2. 补齐管理端功能缺口（公告系统、系统监控、全局搜索、日志导出）
3. 完善部署与运维体系

### 8.4 长期规划（明年）
1. 性能优化与监控体系建设
2. 安全与合规体系完善
3. 国际化（i18n）支持
4. 移动端适配完善

---

## 九、总结

### 9.1 整体评估
**完成度**: **75%**  
**可用性**: **核心功能可用，但存在大量待修复问题**  
**稳定性**: **中等，需要加强错误处理和并发安全**  
**可维护性**: **良好，架构清晰，但代码规范需要统一**

### 9.2 核心优势
1. ✅ 模块化架构清晰，两个核心场景独立演进
2. ✅ 技术栈现代化（Next.js 16 + React 19 + FastAPI）
3. ✅ 实时语音交互能力完整
4. ✅ 知识库检索能力强（RAG + ChromaDB）
5. ✅ 管理后台功能丰富

### 9.3 主要差距
1. ❌ 用户体验存在中断（alert/confirm 弹窗）
2. ❌ 错误处理不统一（HTTPException vs Result[T]）
3. ❌ 代码规范不一致（console.log、print()、window.location）
4. ❌ 权限控制不够细粒度
5. ❌ 性能指标未验证
6. ❌ 部署运维体系不完善

### 9.4 建议路径
**短期**（1-2 周）：修复高优先级 UX 和 API 问题，完成当前任务计划 Phase 1-2  
**中期**（1-2 月）：执行系统审计修复计划 M1-M4，补齐核心功能缺口  
**长期**（3-6 月）：执行系统审计修复计划 M5-M6，完善部署运维体系

---

**报告生成人**: Cascade AI Assistant  
**下次审查建议**: 1 个月后或重大版本发布前
