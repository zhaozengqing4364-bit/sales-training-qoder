export const SUPPORT_RUNTIME_FAULT_ACTION_COPY = {
    stuck_scoring: "下一步：检查评分任务队列和该会话的 report_status，必要时触发重新评分或结束挂起任务。",
    knowledge_search_failed: "下一步：检查关联知识库、Embedding 服务和最近资产变更，再重试知识检索。",
    upstream_unstable: "下一步：查看实时链路断连日志，确认上游 ASR/LLM/TTS 服务可用性。",
    presentation_degraded_missing_page_metadata: "下一步：检查 PPT 页缩略图、OCR 与页码元数据是否已完成解析。",
    optional_report_failed: "下一步：保留 canonical report 可用路径，排查增强报告生成失败原因。",
} as const;

export const SUPPORT_RUNTIME_DEFAULT_FAULT_ACTION = "下一步：查看诊断字段和关联资产变更，确认影响范围后分派给对应模块负责人。";

export function getSupportRuntimeFaultAction(kind: string): string {
    return SUPPORT_RUNTIME_FAULT_ACTION_COPY[kind as keyof typeof SUPPORT_RUNTIME_FAULT_ACTION_COPY] || SUPPORT_RUNTIME_DEFAULT_FAULT_ACTION;
}
