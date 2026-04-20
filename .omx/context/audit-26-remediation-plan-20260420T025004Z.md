Task statement: 为项目代码审计发现的 26 个问题制定全面、可靠、可执行的解决计划，覆盖代码质量、用户体验、用户粘性和后续迭代优先级，不涉及 Docker、部署、运维，不直接实现代码。
Desired outcome: 产出可交给 ralph 或 team 执行的共识计划，包含分阶段路线、26 个问题逐项解决方案、验收标准、测试规格、风险控制、人员/agent 分工和执行顺序。
Known facts/evidence:
- 项目为 Next.js/React 前端 web/src + FastAPI/Python 后端 backend/src。
- 关键前端路径：dashboard 首页、training 销售/PPT 入口、practice live session、report、replay、history、leaderboard、profile、admin settings/personas。
- 关键后端路径：common/api/dashboard.py、common/api/practice.py、common/analytics/history_service.py、common/services/practice_session_service.py、common/auth/service.py、common/middleware/auth.py、sales_bot/websocket/stepfun_realtime_handler.py、presentation_coach/api/presentations.py。
- 刚完成审计输出 26 项问题，分为高优紧急 10 项、中优待排 10 项、低优可选 6 项。
- 当前工作区存在未提交修改，计划阶段不得覆盖或回滚现有改动。
- 验证证据：web targeted vitest 4 files/35 tests passed；backend targeted pytest collection blocked by missing rank_bm25 and jwt；backend ruff check src tests 仍有大量历史 lint/test lint 问题。
Constraints:
- 完全排除 Docker、部署、运维、基础设施建议。
- 规划阶段不修改业务源码。
- 后续实现需保护现有未提交改动，不得回滚他人修改。
- 不新增依赖，除非为恢复既有后端测试运行所需且经计划明确说明。
- 所有高风险重构必须先补行为回归测试。
Unknowns/open questions:
- 后端测试运行依赖应通过哪个 Python 环境/包管理路径最终固定；当前 pytest 使用 Python 3.13.12，backend pyproject 声明 Python >=3.11。
- 26 个问题是否一次执行全部，还是先执行高优紧急 tranche；计划应同时给全量路线和首批执行建议。
Likely codebase touchpoints:
- backend/requirements.txt, backend/pyproject.toml, backend/src/common/middleware/auth.py, backend/src/common/api/response.py, backend/src/common/api/dashboard.py, backend/src/common/api/practice.py, backend/src/common/analytics/history_service.py, backend/src/common/services/practice_session_service.py, backend/src/sales_bot/websocket/stepfun_realtime_handler.py
- web/src/lib/api/client.ts, web/src/lib/api/client-domains.ts, web/src/app/(dashboard)/page.tsx, history/page.tsx, training/page.tsx, training/sales/page.tsx, training/presentation/page.tsx, leaderboard/page.tsx, profile/page.tsx, web/src/app/(dashboard)/agents/[agentId]/page.tsx
- web/src/app/(user)/practice/[sessionId]/page.tsx, use-practice-session-lifecycle.ts, report/page.tsx, replay/page.tsx
- web/src/app/admin/settings/page.tsx, admin/personas/[id]/page.tsx, web/src/components/highlights/*, web/src/components/practice/*, web/src/components/layout/*, web/src/components/analytics/*
