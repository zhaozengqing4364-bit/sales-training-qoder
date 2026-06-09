import { describe, expect, it } from "vitest";

import type { SalesTrainerOperationLog } from "@/lib/api/types";

import { buildOperationLogDisplay } from "./operation-log-display";

function log(overrides: Partial<SalesTrainerOperationLog>): SalesTrainerOperationLog {
    return {
        log_id: "log-1",
        actor_id: "admin-1",
        actor_role: "admin",
        action: "unknown",
        target_type: "unknown",
        target_id: "target-1",
        request_id: "trace-1",
        ip_address: null,
        user_agent: null,
        metadata: {},
        created_at: "2026-06-04T05:30:00Z",
        ...overrides,
    };
}

describe("buildOperationLogDisplay", () => {
    it("summarizes revision publish and rollback with before after lineage", () => {
        const publish = buildOperationLogDisplay(log({
            action: "audio_score_prompt_revision_published",
            target_type: "sales_trainer_audio_score_prompt",
            metadata: {
                before_revision_id: "prompt-revision-1",
                after_revision_id: "prompt-revision-2",
                trace_id: "trace-prompt",
                future_only: true,
                reason: "发布新版评分 prompt",
            },
        }));

        expect(publish.actionLabel).toBe("录音评分标准修订已发布");
        expect(publish.summaryLines).toContain("修订：prompt-revision-1 → prompt-revision-2");
        expect(publish.summaryLines).toContain("影响范围：只影响后续学员");
        expect(publish.summaryLines).toContain("原因：发布新版评分 prompt");
        expect(publish.summaryLines).toContain("追踪号：trace-prompt");

        const rollback = buildOperationLogDisplay(log({
            action: "newcomer_path_config.rollback",
            target_type: "newcomer_path_config",
            metadata: {
                before_revision_id: "path-revision-5",
                after_revision_id: "path-revision-3",
                impact_scope: "future_learners_only",
                reason: "回滚到稳定版本",
                trace_id: "trace-rollback",
            },
        }));

        expect(rollback.actionLabel).toBe("路径配置已回滚");
        expect(rollback.targetLabel).toBe("新人训练路径配置");
        expect(rollback.summaryLines).toContain("修订：path-revision-5 → path-revision-3");
        expect(rollback.summaryLines).toContain("影响范围：只影响后续学员");
        expect(rollback.summaryLines).toContain("原因：回滚到稳定版本");
    });

    it("summarizes binding and historical regrade audit events", () => {
        const binding = buildOperationLogDisplay(log({
            action: "newcomer_module.article_binding_changed",
            target_type: "newcomer_training_module",
            target_id: "business_skills",
            metadata: {
                before_revision_id: "path-revision-2",
                after_revision_id: "path-revision-3",
                changed_fields: ["learning_content_id"],
                future_only: true,
                trace_id: "trace-binding",
            },
        }));

        expect(binding.actionLabel).toBe("学习文章绑定已变更");
        expect(binding.targetLabel).toBe("新人训练路径关卡");
        expect(binding.summaryLines).toContain("变更字段：学习文章");
        expect(binding.summaryLines).toContain("修订：path-revision-2 → path-revision-3");
        expect(binding.summaryLines).toContain("影响范围：只影响后续学员");

        const regrade = buildOperationLogDisplay(log({
            action: "historical_regrade.completed",
            target_type: "sales_trainer_audio_submission",
            metadata: {
                reason: "评分 prompt 发布新版后追加重评记录",
                trace_id: "trace-regrade",
                append_only: true,
                history_overwrite: false,
                impact_scope: { record_count: 1 },
                before_snapshot: { total_score: 88 },
                after_snapshot: { total_score: 42, target_revision_no: 2 },
            },
        }));

        expect(regrade.actionLabel).toBe("历史记录已重评");
        expect(regrade.summaryLines).toContain("影响范围：1 条历史记录");
        expect(regrade.summaryLines).toContain("写入方式：追加重评结果，不覆盖原始记录");
        expect(regrade.summaryLines).toContain("原始评分：88");
        expect(regrade.summaryLines).toContain("重评结果：42");
        expect(regrade.summaryLines).toContain("目标修订：v2");
    });
});
