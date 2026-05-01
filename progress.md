# Progress

## 2026-04-30

- 项目规范重构完成：引入 PROJECT_BRIEF / ARCHITECTURE / FEATURES / PROGRESS / DECISIONS / QUALITY / README 分层规范
- **功能状态核查更新**：
  - ✅ feat-011 KB锁可配置化 — 已实现（`kb_lock_guard.py` 支持 `strict_audit` / `coach_mode`）
  - ✅ feat-012 单轮提问数限制 — 已实现（`enforce_question_limit()` + `max_questions_per_turn`）
  - ✅ feat-010 PPT六维报告 — 已实现（`PresentationReportService` 1120行）
  - ❌ feat-013 用户词典贯通 — **完全未实现**
- **依赖版本修正**：Next.js 16.1.1 → 16.2.3
- 根目录从 ~26 个文件精简到 ~15 个核心文件

## 2026-03-17

- 建立了本轮全量实现的磁盘计划文件。
- 已确认当前分支、已有未提交改动和上一轮已写入的修复文档。
- 下一步：读取相关实现入口，确认每个需求点在当前代码中的落点和缺口。
- 已完成核心代码盘点，确认：
  - KB lock 需要从 strict block 改为可配置的 coach mode。
  - 单轮提问数限制需要加到指令编译层，并视情况在最终输出层兜底。
  - 用户词典功能需要贯通到 ASR final transcript -> grounding -> scoring -> persistence。
  - PPT 六维报告更适合复用 `ComprehensiveReportService` 做 scenario 分支，而不是继续堆在 `coach_service` 的三分逻辑上。
