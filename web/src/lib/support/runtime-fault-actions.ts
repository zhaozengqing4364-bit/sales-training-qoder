export const SUPPORT_RUNTIME_FAULT_ACTION_COPY = {
    stuck_scoring: "下一步：检查评分任务队列和该会话的 report_status，必要时触发重新评分或结束挂起任务。",
    knowledge_search_failed: "下一步：检查关联知识库、Embedding 服务和最近资产变更，再重试知识检索。",
    kb_not_ready: "下一步：确认知识库文档处理完成、向量索引可用，再恢复需要知识库锁的会话。",
    kb_lock_blocked_no_kb: "下一步：为角色/会话绑定知识库，或在运行时配置中关闭严格知识库锁并记录原因。",
    kb_lock_blocked_not_ready: "下一步：等待或修复知识库处理任务，确认文档完成解析后重新运行会话。",
    kb_lock_blocked_search_failed: "下一步：排查检索链路、Embedding 配置和最近知识库变更，修复后重试。",
    kb_lock_blocked_empty: "下一步：补充知识库内容或调整检索策略，避免严格锁模式下无命中。",
    projection_failed: "下一步：检查 canonical evidence projection 输入与报告诊断，修复结构化证据后重新生成。",
    not_evaluable_completed: "下一步：查看会话轮次、时长和评分证据；若数据不足，联系训练负责人补跑会话。",
    upstream_unstable: "下一步：查看实时链路断连日志，确认上游 ASR/LLM/TTS 服务可用性。",
    presentation_degraded_missing_page_metadata: "下一步：检查 PPT 页缩略图、OCR 与页码元数据是否已完成解析。",
    optional_report_failed: "下一步：保留 canonical report 可用路径，排查增强报告生成失败原因。",
    audio_missing: "下一步：检查浏览器录音上传、OSS 回调和会话音频分段任务，必要时重新采集录音。",
    audio_upload_degraded: "下一步：核对失败音频分段数量与上传错误，修复 OSS/网络问题后重新同步。",
} as const;

export const SUPPORT_RUNTIME_DEFAULT_FAULT_ACTION = "下一步：查看诊断字段和关联资产变更，确认影响范围后分派给对应模块负责人。";

export function getSupportRuntimeFaultAction(kind: string): string {
    return SUPPORT_RUNTIME_FAULT_ACTION_COPY[kind as keyof typeof SUPPORT_RUNTIME_FAULT_ACTION_COPY] || SUPPORT_RUNTIME_DEFAULT_FAULT_ACTION;
}
