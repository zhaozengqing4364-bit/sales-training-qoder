/** Pure DTO-to-display mapping for the Readiness detail route. */

import type {
    ReadinessDossier,
    ReadinessDossierCompetency,
    ReadinessDossierEvidence,
    ReadinessDossierRetrainingTask,
} from "@/lib/api/types/training-journey";

export const STATUS_LABELS: Record<string, string> = {
    not_started: "未开始",
    in_training: "训练中",
    ai_evaluating: "评分中",
    needs_remediation: "需补练",
    pending_review: "待复核",
    approved: "已达标",
    rejected: "未达标",
    manual_follow_up: "需人工跟进",
    blocked_by_config: "配置异常",
    not_trained: "未训练",
    ai_passed: "AI 初评达标",
    ai_failed: "AI 初评未达标",
    needs_retraining: "需重练",
    passed: "已通过",
    failed: "未通过",
    scored: "已评分",
    processing: "评分中",
    uploaded: "已提交",
    completed: "已完成",
};

export const RECORD_TYPE_LABELS: Record<string, string> = {
    audio_submission: "录音提交",
    quiz_attempt: "答题记录",
    ai_coach_session: "AI 补练记录",
    business_etiquette_quiz_attempt: "商务礼仪练习",
};

export function paramValue(value: string | string[] | undefined): string {
    return Array.isArray(value) ? (value[0] ?? "") : (value ?? "");
}

export function statusBadgeClass(status: string): string {
    if (status === "approved" || status === "ai_passed") {
        return "bg-emerald-50 text-emerald-700";
    }
    if (status === "blocked_by_config" || status === "ai_failed") {
        return "bg-red-50 text-red-700";
    }
    if (status === "needs_remediation" || status === "needs_retraining") {
        return "bg-amber-50 text-amber-700";
    }
    if (status === "pending_review") {
        return "bg-blue-50 text-blue-700";
    }
    return "bg-slate-100 text-slate-700";
}

export function formatDate(value: string | null | undefined): string {
    if (!value) {
        return "--";
    }
    return new Date(value).toLocaleString();
}

export function formatScore(
    score: number | null | undefined,
    maxScore: number | null | undefined,
): string {
    if (score == null) {
        return "--";
    }
    if (maxScore == null) {
        return String(score);
    }
    return `${score} / ${maxScore}`;
}

export function statusLabel(status: string | null | undefined): string {
    if (!status) {
        return "未判定";
    }
    return STATUS_LABELS[status] || "待确认";
}

export function recordTypeLabel(recordType: string | null | undefined): string {
    if (!recordType) {
        return "训练证据";
    }
    return RECORD_TYPE_LABELS[recordType] || "训练证据";
}

export function readinessDisplayMessage(message: string | null | undefined): string {
    const rawMessage = String(message || "").trim();
    if (!rawMessage) {
        return "";
    }
    if (rawMessage.includes("runtime binding")) {
        return "真实语音对练后台接入配置缺失，请先处理训练路径配置。";
    }
    if (rawMessage.includes("provider readiness")) {
        return "真实语音服务检查未通过，下一阶段暂不开放。";
    }
    if (rawMessage.includes("active path revision")) {
        return "当前发布的训练路径配置需要处理。";
    }
    if (rawMessage.includes("target_unit_id")) {
        return "训练模块还没有绑定可练内容。";
    }
    if (
        rawMessage.includes("AI Coach") &&
        (rawMessage.includes("Prompt") || rawMessage.includes("配置非法"))
    ) {
        return "AI 补练教练缺少后台配置。";
    }
    return rawMessage
        .replace(/\s*\(trace_id:[^)]+\)/g, "")
        .replace(/\[[A-Z0-9_]+\]\s*/g, "")
        .replace(/TrainingJourney/g, "训练路径")
        .replace(/Journey/g, "训练路径")
        .replace(/active revision/g, "当前发布版本")
        .replace(/provider readiness/g, "语音服务检查")
        .replace(/runtime binding/g, "后台接入配置")
        .replace(/target_unit_id/g, "训练内容")
        .replace(/AI Coach/g, "AI 补练教练")
        .replace(/Prompt/g, "后台配置")
        .replace(/terminal/g, "需处理")
        .trim();
}

export function snapshotSummary(
    snapshot: Record<string, unknown> | null,
    kind: "material" | "scoring" | "task",
): string {
    if (!snapshot) {
        return "--";
    }
    if (kind === "material") {
        const label = snapshot.title || snapshot.name || snapshot.filename;
        return label ? String(label) : "已保留材料版本快照";
    }
    if (kind === "scoring") {
        const values: string[] = [];
        if (snapshot.title) {
            values.push(String(snapshot.title));
        }
        if (snapshot.pass_threshold != null) {
            values.push(`通过线 ${snapshot.pass_threshold}`);
        }
        if (snapshot.max_score != null) {
            values.push(`满分 ${snapshot.max_score}`);
        }
        if (snapshot.dimension_count != null) {
            values.push(`评分维度 ${snapshot.dimension_count} 个`);
        }
        if (snapshot.summary) {
            values.push(String(snapshot.summary));
        }
        return values.length ? values.slice(0, 3).join(" · ") : "已保留评分依据快照";
    }
    const values: string[] = [];
    if (snapshot.title) {
        values.push(String(snapshot.title));
    }
    if (snapshot.purpose) {
        values.push(String(snapshot.purpose));
    }
    if (snapshot.scenario) {
        values.push(String(snapshot.scenario));
    }
    if (Array.isArray(snapshot.success_criteria)) {
        values.push(`完成标准 ${snapshot.success_criteria.length} 条`);
    }
    return values.length ? values.slice(0, 3).join(" · ") : "已保留任务说明快照";
}

export function evidenceLabel(evidence: ReadinessDossierEvidence): string {
    return evidence.module_title || evidence.module_key || evidence.evidence_id;
}

export function evidenceResultSummary(evidence: ReadinessDossierEvidence): string {
    const score = formatScore(evidence.score, evidence.max_score);
    const status = statusLabel(evidence.status);
    if (score !== "--") {
        return `${status}，得分 ${score}。`;
    }
    return evidence.result_summary || "该证据已进入档案，等待汇总判断。";
}

export function retrainingTaskStatusText(task: ReadinessDossierRetrainingTask): string {
    if (task.status === "completed") {
        return "新人已完成重练，等待复核";
    }
    if (task.status === "in_progress") {
        return "新人已重新提交，正在评分";
    }
    if (task.status === "pending") {
        return "已要求重练，等待新人重新提交";
    }
    return "重练任务已记录";
}

export function retrainingTaskResultText(task: ReadinessDossierRetrainingTask): string | null {
    const comparison = task.comparison;
    if (!comparison) {
        return null;
    }
    if (comparison.after_passed === true) {
        return `重练后结果：已通过，得分 ${formatScore(comparison.after_score, comparison.after_max_score)}。`;
    }
    if (comparison.after_passed === false) {
        return `重练后结果：未通过，得分 ${formatScore(comparison.after_score, comparison.after_max_score)}。`;
    }
    if (comparison.after_status) {
        return `重练后状态：${statusLabel(comparison.after_status)}。`;
    }
    return null;
}

export function capabilityNames(
    capabilityKeys: string[],
    competenciesByKey: Map<string, ReadinessDossierCompetency>,
): string[] {
    return capabilityKeys.map((key) => competenciesByKey.get(key)?.display_name).filter(Boolean) as string[];
}

export function defaultCapabilitySelection(dossier: ReadinessDossier): string[] {
    const risk = dossier.competencies
        .filter((item) => item.status === "ai_failed" || item.status === "pending_review")
        .map((item) => item.capability_key);
    if (risk.length > 0) {
        return risk;
    }
    return dossier.competencies
        .filter((item) => item.status === "ai_passed" || item.status === "approved")
        .map((item) => item.capability_key);
}

export function defaultEvidenceSelection(dossier: ReadinessDossier): string[] {
    const risk = dossier.evidence
        .filter((item) => item.passed === false || item.status === "failed")
        .map((item) => item.evidence_id);
    if (risk.length > 0) {
        return risk.slice(0, 10);
    }
    return dossier.evidence.slice(0, 10).map((item) => item.evidence_id);
}

export function toggleValue(values: string[], value: string): string[] {
    return values.includes(value) ? values.filter((item) => item !== value) : [...values, value];
}
