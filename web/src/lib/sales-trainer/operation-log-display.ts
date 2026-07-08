import type { SalesTrainerOperationLog } from "@/lib/api/types";

const ACTION_LABELS: Readonly<Record<string, string>> = {
    exam_paper_created: "考卷已创建",
    exam_paper_updated: "考卷已更新",
    exam_paper_published: "考卷已发布",
    exam_paper_archived: "考卷已归档",
    exam_paper_revision_saved: "考卷修订已保存",
    exam_paper_revision_published: "考卷修订已发布",
    exam_paper_revision_rolled_back: "考卷修订已回滚",
    unit_created: "模块单元已创建",
    unit_updated: "模块单元已更新",
    unit_published: "模块单元已发布",
    unit_archived: "模块单元已归档",
    unit_revision_saved: "模块单元修订已保存",
    unit_revision_published: "模块单元修订已发布",
    unit_revision_rolled_back: "模块单元修订已回滚",
    material_created: "训练材料已创建",
    material_version_created: "材料版本已创建",
    material_version_published: "材料版本已发布",
    audio_score_prompt_created: "录音评分标准已创建",
    audio_score_prompt_updated: "录音评分标准已更新",
    audio_score_prompt_published: "录音评分标准已发布",
    audio_score_prompt_revision_saved: "录音评分标准修订已保存",
    audio_score_prompt_revision_published: "录音评分标准修订已发布",
    question_revision_saved: "题目修订已保存",
    question_revision_published: "题目修订已发布",
    question_published: "题目已发布",
    "newcomer_path_config.save_working": "路径配置修订已保存",
    "newcomer_path_config.publish": "路径配置已发布",
    "newcomer_path_config.rollback": "路径配置已回滚",
    "newcomer_path_config.article_binding_saved": "专题内容绑定已变更",
    "newcomer_module.article_binding_changed": "专题内容绑定已变更",
    "historical_regrade.completed": "历史记录已重评",
    quiz_submitted: "学员已提交考试",
    audio_uploaded: "学员已上传录音",
    audio_transcription_started: "录音开始转写",
    audio_transcription_succeeded: "录音转写成功",
    audio_transcription_failed: "录音转写失败",
    audio_scoring_started: "录音开始评分",
    audio_scoring_succeeded: "录音评分成功",
    audio_scoring_failed: "录音评分失败",
};

const TARGET_LABELS: Readonly<Record<string, string>> = {
    sales_trainer_exam_paper: "考卷",
    sales_trainer_unit: "模块单元",
    sales_trainer_material: "训练材料",
    sales_trainer_material_version: "材料版本",
    sales_trainer_audio_score_prompt: "录音评分标准",
    sales_trainer_question: "题目",
    sales_trainer_quiz_attempt: "考试记录",
    business_etiquette_unit_quiz_attempt: "商务礼仪小测记录",
    sales_trainer_audio_submission: "录音记录",
    newcomer_training_path_config: "新人训练路径配置",
    newcomer_path_config: "新人训练路径配置",
    newcomer_training_module: "新人训练路径关卡",
};

const FIELD_LABELS: Readonly<Record<string, string>> = {
    title: "标题",
    name: "名称",
    status: "状态",
    config: "配置",
    questions: "题目组成",
    pass_threshold: "通过线",
    module_key: "所属训练关卡",
    unit_id: "模块单元",
    path_key: "训练路径",
    paper_key: "考卷配置",
    source_page: "来源页面",
    scoring_prompt_id: "录音评分标准",
    material_id: "训练材料",
    learning_content_id: "专题内容",
    exam_paper_id: "考卷",
    current_version_id: "当前版本",
};

const STATUS_LABELS: Readonly<Record<string, string>> = {
    draft: "草稿",
    published: "已发布",
    archived: "已归档",
};

const ACTOR_ROLE_LABELS: Readonly<Record<string, string>> = {
    admin: "管理员",
    super_admin: "超级管理员",
    training_owner: "培训负责人",
    content_admin: "内容管理员",
    ops: "运维人员",
    learner: "学员",
};

export interface OperationLogDisplay {
    readonly actionLabel: string;
    readonly actorLabel: string;
    readonly targetLabel: string;
    readonly summaryLines: readonly string[];
    readonly rawJson: string;
}

function isRecord(value: unknown): value is Record<string, unknown> {
    return typeof value === "object" && value !== null && !Array.isArray(value);
}

function stringValue(value: unknown): string | null {
    return typeof value === "string" && value.trim() ? value : null;
}

function numberValue(value: unknown): number | null {
    return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function formatStatus(value: unknown): string | null {
    const status = stringValue(value);
    return status ? STATUS_LABELS[status] ?? status : null;
}

function fieldLabel(value: unknown): string {
    const field = stringValue(value);
    return field ? FIELD_LABELS[field] ?? "其他字段" : "未知字段";
}

function formatActor(role: string | null, actorId: string | null): string {
    const roleLabel = role ? ACTOR_ROLE_LABELS[role] ?? "工作人员" : "系统";
    return actorId ? `${roleLabel} · ${actorId}` : roleLabel;
}

function formatRevisionLine(metadata: Record<string, unknown>): string | null {
    const before = stringValue(
        metadata.before_revision_id ?? metadata.source_revision_id,
    );
    const after = stringValue(
        metadata.after_revision_id
        ?? metadata.working_revision_id
        ?? metadata.target_revision_id,
    );
    if (before && after && before !== after) {
        return `修订：${before} → ${after}`;
    }
    if (after) {
        return `修订：${after}`;
    }
    return null;
}

function formatImpactScope(metadata: Record<string, unknown>): string | null {
    const impactScope = metadata.impact_scope;
    if (impactScope === "future_learners_only" || metadata.future_only === true) {
        return "影响范围：只影响后续学员";
    }
    if (isRecord(impactScope)) {
        const recordCount = numberValue(impactScope.record_count);
        if (recordCount !== null) {
            return `影响范围：${recordCount} 条历史记录`;
        }
    }
    return null;
}

function formatAppendOnlyLine(metadata: Record<string, unknown>): string | null {
    if (metadata.append_only === true && metadata.history_overwrite === false) {
        return "写入方式：追加重评结果，不覆盖原始记录";
    }
    return null;
}

function formatSnapshotScore(
    metadata: Record<string, unknown>,
    key: "before_snapshot" | "after_snapshot",
    label: string,
): string | null {
    const snapshot = isRecord(metadata[key]) ? metadata[key] : null;
    const score = numberValue(snapshot?.total_score);
    if (score === null) {
        return null;
    }
    return `${label}：${score}`;
}

function formatTargetRevisionNo(metadata: Record<string, unknown>): string | null {
    const snapshot = isRecord(metadata.after_snapshot) ? metadata.after_snapshot : null;
    const revisionNo = numberValue(snapshot?.target_revision_no);
    return revisionNo === null ? null : `目标修订：v${revisionNo}`;
}

function pushIfPresent(lines: string[], line: string | null): void {
    if (line) {
        lines.push(line);
    }
}

function levelLabel(value: unknown): string | null {
    if (!isRecord(value)) {
        return null;
    }
    return stringValue(value.label) ?? stringValue(value.level_key);
}

function buildTrainingContextLines(
    context: SalesTrainerOperationLog["training_context"],
): string[] {
    if (!context) {
        return [];
    }
    const lines: string[] = [];
    if (context.path_revision_no !== null && context.path_revision_no !== undefined) {
        lines.push(`路径版本：v${context.path_revision_no}`);
    }
    if (context.training_stage) {
        lines.push(`训练阶段：${context.training_stage}`);
    }
    const learnerLevel = levelLabel(context.learner_level);
    if (learnerLevel) {
        lines.push(`学员等级：${learnerLevel}`);
    }
    const roleLevel = levelLabel(context.role_level);
    if (roleLevel) {
        lines.push(`角色等级：${roleLevel}`);
    }
    return lines;
}

function buildSummaryLines(
    metadata: Record<string, unknown>,
    trainingContext: SalesTrainerOperationLog["training_context"],
): string[] {
    const previous = isRecord(metadata.previous) ? metadata.previous : null;
    const next = isRecord(metadata.next) ? metadata.next : null;
    const lines: string[] = [];
    const previousTitle = stringValue(previous?.title ?? previous?.name);
    const nextTitle = stringValue(next?.title ?? next?.name);
    if (previousTitle && nextTitle && previousTitle !== nextTitle) {
        lines.push(`标题：${previousTitle} → ${nextTitle}`);
    }
    const previousStatus = formatStatus(metadata.previous_status ?? previous?.status);
    const nextStatus = formatStatus(metadata.next_status ?? next?.status);
    if (previousStatus && nextStatus && previousStatus !== nextStatus) {
        lines.push(`状态：${previousStatus} → ${nextStatus}`);
    }
    if (Array.isArray(metadata.changed_fields) && metadata.changed_fields.length > 0) {
        lines.push(`变更字段：${metadata.changed_fields.map(fieldLabel).join("、")}`);
    }
    pushIfPresent(lines, formatRevisionLine(metadata));
    pushIfPresent(lines, formatImpactScope(metadata));
    const reason = stringValue(metadata.reason);
    if (reason) {
        lines.push(`原因：${reason}`);
    }
    pushIfPresent(lines, formatAppendOnlyLine(metadata));
    pushIfPresent(lines, formatSnapshotScore(metadata, "before_snapshot", "原始评分"));
    pushIfPresent(lines, formatSnapshotScore(metadata, "after_snapshot", "重评结果"));
    pushIfPresent(lines, formatTargetRevisionNo(metadata));
    const traceId = stringValue(metadata.trace_id);
    if (traceId) {
        lines.push(`追踪号：${traceId}`);
    }
    const questionCount = numberValue(metadata.question_count);
    if (questionCount !== null) {
        lines.push(`题目数量：${questionCount}`);
    }
    const errorCode = stringValue(metadata.error_code);
    if (errorCode) {
        lines.push(`错误码：${errorCode}`);
    }
    const versionLabel = stringValue(metadata.version_label);
    if (versionLabel) {
        lines.push(`版本：${versionLabel}`);
    }
    lines.push(...buildTrainingContextLines(trainingContext));
    return lines.length ? lines : ["已记录关键操作，可展开查看原始诊断数据。"];
}

export function buildOperationLogDisplay(item: SalesTrainerOperationLog): OperationLogDisplay {
    return {
        actionLabel: ACTION_LABELS[item.action] ?? "关键操作",
        actorLabel: formatActor(item.actor_role, item.actor_id),
        targetLabel: TARGET_LABELS[item.target_type] ?? "业务对象",
        summaryLines: buildSummaryLines(item.metadata, item.training_context ?? null),
        rawJson: JSON.stringify({
            action: item.action,
            target_type: item.target_type,
            target_id: item.target_id,
            metadata: item.metadata,
            training_context: item.training_context ?? null,
        }, null, 2),
    };
}
