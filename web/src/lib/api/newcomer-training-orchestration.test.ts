import { describe, expect, it, vi } from "vitest";

import {
    createAdminNewcomerTrainingDomain,
    createNewcomerTrainingDomain,
} from "./domains/newcomer-training";

describe("newcomer training orchestration API", () => {
    it("uses activity identity for learner actions", async () => {
        const request = vi.fn().mockResolvedValue({ activity: { activity_id: "activity-1" } });
        const upload = vi.fn().mockResolvedValue({ activity: { activity_id: "activity-1" } });
        const stream = vi.fn();
        const domain = createNewcomerTrainingDomain({ request, upload, stream });

        await domain.getJourney();
        await domain.completeLessonChapter("activity-1", "chapter-1", "token-1");
        const file = new File(["audio"], "demo.wav", { type: "audio/wav" });
        await domain.submitAudio("activity-1", { file, client_token: "token-2" });

        expect(request).toHaveBeenNthCalledWith(1, "/newcomer-training/journey");
        expect(request).toHaveBeenNthCalledWith(
            2,
            "/newcomer-training/activities/activity-1/lesson/chapters/chapter-1/complete",
            { method: "POST", body: JSON.stringify({ client_token: "token-1" }) },
        );
        expect(upload.mock.calls[0][0]).toBe(
            "/newcomer-training/activities/activity-1/audio/submissions",
        );
        expect(upload.mock.calls[0][1].get("client_token")).toBe("token-2");
        expect(upload.mock.calls[0][1].get("file")).toBe(file);
    });

    it("uses one canonical path revision API for administrators", async () => {
        const request = vi.fn().mockResolvedValue({});
        const domain = createAdminNewcomerTrainingDomain({ request });

        await domain.getPath();
        const candidate = { schema_version: "newcomer_training_orchestration_v1" as const, title: "新人训练", description: null, phases: [] };
        await domain.saveDraft(candidate, "保存", "revision-1");
        await domain.validateCandidate(candidate);
        await domain.publishCandidate(candidate, "允许新人开始学习", "revision-2");
        await domain.restoreRevision("revision-2", "恢复上一版", "revision-current");

        expect(request).toHaveBeenNthCalledWith(1, "/admin/newcomer-training/path/");
        expect(request).toHaveBeenNthCalledWith(2, "/admin/newcomer-training/path/draft", {
            method: "PUT",
            body: JSON.stringify({ payload: candidate, reason: "保存", expected_revision_id: "revision-1" }),
        });
        expect(request).toHaveBeenNthCalledWith(3, "/admin/newcomer-training/path/validate-candidate", {
            method: "POST",
            body: JSON.stringify({ payload: candidate }),
        });
        expect(request).toHaveBeenNthCalledWith(4, "/admin/newcomer-training/path/publish-candidate", {
            method: "POST",
            body: JSON.stringify({ payload: candidate, reason: "允许新人开始学习", expected_revision_id: "revision-2" }),
        });
        expect(request).toHaveBeenNthCalledWith(
            5,
            "/admin/newcomer-training/path/revisions/revision-2/restore",
            { method: "POST", body: JSON.stringify({ reason: "恢复上一版", expected_revision_id: "revision-current" }) },
        );
    });
});
