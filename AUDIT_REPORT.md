# 数据流审计报告 - 销售训练系统（修复状态）

**原始审计日期**: 2026-02-25  
**状态更新时间**: 2026-02-25 11:43 +0800  
**当前状态**: ✅ 已完成修复清理  
**风险等级**: Low

---

## 执行摘要

| 维度 | 原问题数 | 已修复 | 待处理 |
|------|----------|--------|--------|
| P0 关键事务流 | 7 | 7 | 0 |
| P1 PPT/向量流 | 6 | 6 | 0 |
| P2 WebSocket 状态 | 4 | 4 | 0 |
| 前端契约一致性 | 4 | 4 | 0 |
| **总计** | **21** | **21** | **0** |

---

## 已修复清单（已从待修复项清除）

### P0 关键事务流

- ✅ N+1 查询问题（`backend/src/common/api/training.py`）
- ✅ 会话状态存储内存化问题（迁移为 Redis 状态服务，`backend/src/common/websocket/session_state_service.py`）
- ✅ 会话结束事务边界不完整（`backend/src/common/api/practice.py`）
- ✅ 评分覆盖无幂等处理（仅缺失时回填，`backend/src/common/api/practice.py`）
- ✅ WebSocket 连接管理并发控制缺失（`asyncio.Lock`，`backend/src/common/websocket/base_handler.py`）
- ✅ Session 生命周期 rollback/commit 路径一致性问题（`backend/src/common/api/practice.py`）
- ✅ Session 关闭/资源管理风险项（相关调用路径已收敛到统一生命周期处理）

### P1 PPT / 向量流

- ✅ Chroma 一致性问题（向量写入补偿清理，`backend/src/common/knowledge/service.py` / `backend/src/common/knowledge/vector_store.py`）
- ✅ PG-Chroma 同步问题（上传与解析链路状态收敛，`backend/src/presentation_coach/api/presentations.py`）
- ✅ PPT 解析资源管理问题（`backend/src/presentation_coach/services/ppt_parser.py`）
- ✅ 文件哈希重复检查缺失（新增 `content_hash` 与迁移）
- ✅ Chroma 写入原子性风险（失败回收与补偿）
- ✅ 文件写入无原子性（原子写入流程）

### P2 WebSocket 状态

- ✅ 断开时状态清理问题（连接与状态服务同步清理）
- ✅ 状态转换与报告触发顺序风险（生命周期触发顺序已重排）
- ✅ 音频背压仅丢弃无通知（新增前后端通知机制）
- ✅ 会话历史状态持久化缺失（关键会话状态已由状态服务托管）

### 前端契约一致性

- ✅ 生命周期类型定义补齐（含 `scenario_type`，`web/src/lib/api/types.ts`）
- ✅ 建会话失败重试缺失（指数退避，`web/src/app/(dashboard)/agents/[agentId]/page.tsx`）
- ✅ 401 并发竞态（去重处理，`web/src/lib/api/client.ts`）
- ✅ WebSocket 未就绪消息丢失（待发送队列，`web/src/hooks/use-practice-websocket.ts`）

### 本次增量修复（知识库检索超时）

- ✅ KB 强制模式检索超时：为 KB 锁检索路径增加 embedding 阶段预算（`KNOWLEDGE_KB_LOCK_EMBED_TIMEOUT_MS`），避免外部 embedding 慢失败导致 `blocked_search_timeout`（`backend/src/common/knowledge/kb_lock_guard.py`、`backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py`、`backend/src/common/knowledge/service.py`）
- ✅ 运行参数补齐：新增环境变量样例并落地本地运行参数（`backend/.env.example`、`backend/.env`）

---

## 数据一致性复核

| 检查项 | 当前结果 |
|--------|----------|
| PG-Chroma 双写一致性 | ✅ 通过 |
| Redis 会话隔离 | ✅ 通过 |
| 分布式会话状态 | ✅ 通过 |

---

## 验证结果（全量测试）

- ✅ Backend Contract: `41 passed`
- ✅ Backend E2E: `7 passed`
- ✅ Backend Integration: `192 passed, 28 skipped`
- ✅ Backend Performance: `20 passed, 5 skipped`
- ✅ Backend Unit: `809 passed`
- ✅ Backend 汇总: `1069 passed, 33 skipped, 0 failed`
- ✅ Frontend (`npm test`): `149 passed, 0 failed`

---

## 待处理项

- 当前无待处理问题。
