import { describe, expect, it, vi } from "vitest";

import {
    createAdminNewcomerTrainingDomain,
    createNewcomerTrainingDomain,
} from "./domains/newcomer-training";

describe("newcomer training orchestration API", () => {
    it("uses activity identity for learner actions", async () => {
        const request = vi.fn().mockResolvedValue({ activity: { activity_id: "activity-1" } });
        const domain = createNewcomerTrainingDomain({ request });

        await domain.getJourney();
        await domain.executeCommand("activity-1", {
            command_type: "save_progress",
            attempt_id: "attempt-1",
            expected_enrollment_version: null,
            expected_attempt_version: 2,
            payload: {
                completed_checkpoint_ids: ["checkpoint-1"],
                reading_position: { concept_id: "concept-1" },
            },
        }, "token-1");

        expect(request).toHaveBeenNthCalledWith(1, "/newcomer-training/journey");
        expect(request).toHaveBeenNthCalledWith(
            2,
            "/newcomer-training/activities/activity-1/commands",
            {
                method: "POST",
                headers: { "Idempotency-Key": "token-1" },
                body: JSON.stringify({
                    command_type: "save_progress",
                    attempt_id: "attempt-1",
                    expected_enrollment_version: null,
                    expected_attempt_version: 2,
                    payload: {
                        completed_checkpoint_ids: ["checkpoint-1"],
                        reading_position: { concept_id: "concept-1" },
                    },
                }),
                signal: undefined,
            },
        );
        expect("startRealtime" in domain).toBe(false);
    });

    it("uses the v2 path workspace and versioned draft commands", async () => {
        const request = vi.fn().mockResolvedValue({});
        const domain = createAdminNewcomerTrainingDomain({ request, upload: vi.fn() });

        await domain.listPaths({ status: "draft" });
        await domain.getPathWorkspace("path-1");
        const draft = {
            contract_version: "newcomer_training_path_v2" as const,
            title: "新人训练",
            revision_label: "首发版",
            stages: [],
        };
        await domain.savePathDraftV2("path-1", draft, 2, "draft-token");
        await domain.validatePathV2("path-1");

        expect(request).toHaveBeenNthCalledWith(
            1,
            "/admin/newcomer-training/paths?status=draft",
        );
        expect(request).toHaveBeenNthCalledWith(
            2,
            "/admin/newcomer-training/paths/path-1/workspace",
        );
        expect(request).toHaveBeenNthCalledWith(
            3,
            "/admin/newcomer-training/paths/path-1/working-revision",
            {
                method: "PUT",
                headers: {
                    "If-Match": 'W/"2"',
                    "Idempotency-Key": "draft-token",
                },
                body: JSON.stringify(draft),
            },
        );
        expect(request).toHaveBeenNthCalledWith(
            4,
            "/admin/newcomer-training/paths/path-1/commands/validate",
            { method: "POST" },
        );
    });

    it("uses the v2 scoped learner progress endpoints", async () => {
        const request = vi.fn().mockResolvedValue({});
        const domain = createAdminNewcomerTrainingDomain({ request, upload: vi.fn() });

        await domain.listLearners({ search: "张三", limit: 20, offset: 20 });
        await domain.getLearner("learner/1");

        expect(request).toHaveBeenNthCalledWith(
            1,
            "/admin/newcomer-training/learners?search=%E5%BC%A0%E4%B8%89&limit=20&offset=20",
        );
        expect(request).toHaveBeenNthCalledWith(
            2,
            "/admin/newcomer-training/learners/learner%2F1",
        );
    });

    it("uploads source documents with an idempotency header and bounded timeout", async () => {
        const request = vi.fn().mockResolvedValue({});
        const upload = vi.fn().mockResolvedValue({ task: { state: "queued" } });
        const domain = createAdminNewcomerTrainingDomain({ request, upload });
        const formData = new FormData();
        formData.set("file", new File(["training content"], "handbook.txt", { type: "text/plain" }));

        await domain.uploadSourceDocumentV2(formData, "upload-token");

        expect(upload).toHaveBeenCalledWith(
            "/admin/newcomer-training/resources/source_document/uploads",
            formData,
            undefined,
            {
                timeoutMs: 60_000,
                timeoutMessage: "材料上传超时，请检查网络后重试。",
                headers: { "Idempotency-Key": "upload-token" },
            },
        );
    });

    it("uses the versioned readiness dossier and human-review endpoints", async () => {
        const request = vi.fn().mockResolvedValue({});
        const learner = createNewcomerTrainingDomain({ request });
        const admin = createAdminNewcomerTrainingDomain({ request, upload: vi.fn() });

        await learner.getDossier();
        await learner.submitAppeal({
            target_type: "decision",
            target_id: "decision-1",
            dossier_version: 3,
            reason_category: "fact_error",
            statement: "复核事实需要核对。",
        }, "appeal-token");
        await admin.listReadinessReviews({
            state: "pending_review",
            cohort_id: "cohort-1",
            reviewer_id: "reviewer-1",
            waiting_hours_gte: 24,
            limit: 20,
        });
        await admin.getReadinessReview("dossier-1");
        await admin.previewReadinessException("dossier-1", {
            expected_dossier_version: 3,
            snapshot_id: "snapshot-1",
            reason: "预览例外影响。",
            competency_keys: ["value_expression"],
            evidence_ids: ["evidence-1"],
        }, "exception-preview-token");
        await admin.recordReadinessDecision("dossier-1", {
            decision_type: "approve_foundation_ready",
            expected_dossier_version: 3,
            snapshot_id: "snapshot-1",
            reason: "人工确认达标。",
            competency_keys: ["value_expression"],
            evidence_ids: ["evidence-1"],
        }, "decision-token");

        expect(request).toHaveBeenNthCalledWith(1, "/newcomer-training/dossier");
        expect(request).toHaveBeenNthCalledWith(2, "/newcomer-training/dossier/appeals", {
            method: "POST",
            headers: { "Idempotency-Key": "appeal-token" },
            body: JSON.stringify({
                target_type: "decision",
                target_id: "decision-1",
                dossier_version: 3,
                reason_category: "fact_error",
                statement: "复核事实需要核对。",
            }),
        });
        expect(request).toHaveBeenNthCalledWith(
            3,
            "/admin/newcomer-training/reviews?state=pending_review&cohort_id=cohort-1&reviewer_id=reviewer-1&waiting_hours_gte=24&limit=20",
        );
        expect(request).toHaveBeenNthCalledWith(
            4,
            "/admin/newcomer-training/reviews/dossier-1",
        );
        expect(request).toHaveBeenNthCalledWith(
            5,
            "/admin/newcomer-training/reviews/dossier-1/commands/preview-exception",
            {
                method: "POST",
                headers: {
                    "Idempotency-Key": "exception-preview-token",
                    "If-Match": 'W/"3"',
                },
                body: JSON.stringify({
                    expected_dossier_version: 3,
                    snapshot_id: "snapshot-1",
                    reason: "预览例外影响。",
                    competency_keys: ["value_expression"],
                    evidence_ids: ["evidence-1"],
                }),
            },
        );
        expect(request).toHaveBeenNthCalledWith(
            6,
            "/admin/newcomer-training/reviews/dossier-1/commands/record-decision",
            {
                method: "POST",
                headers: {
                    "Idempotency-Key": "decision-token",
                    "If-Match": 'W/"3"',
                },
                body: JSON.stringify({
                    decision_type: "approve_foundation_ready",
                    expected_dossier_version: 3,
                    snapshot_id: "snapshot-1",
                    reason: "人工确认达标。",
                    competency_keys: ["value_expression"],
                    evidence_ids: ["evidence-1"],
                }),
            },
        );
    });
});
