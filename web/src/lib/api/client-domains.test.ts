import { describe, expect, it, vi } from "vitest";

import {
    createAdminSalesTrainerDomain,
    createAuthDomain,
    createPracticeDomain,
    createSalesTrainerDomain,
} from "./client-domains";

describe("client domain factories", () => {
    it("keeps auth login on the shared request seam with session-expiry handling disabled", async () => {
        const request = vi.fn().mockResolvedValue({ token: "token-1" });
        const auth = createAuthDomain({ request });

        await auth.login({ email: "admin@test.com", password: "secret" });

        expect(request).toHaveBeenCalledWith("/auth/login", {
            method: "POST",
            body: JSON.stringify({ email: "admin@test.com", password: "secret" }),
            skipSessionExpiredHandling: true,
        });
    });

    it("loads auth providers through the shared request seam without session-expired handling", async () => {
        const request = vi.fn().mockResolvedValue({ environment: "development" });
        const auth = createAuthDomain({ request });

        await auth.getProviders();

        expect(request).toHaveBeenCalledWith("/auth/providers", {
            method: "GET",
            cache: "no-store",
            skipSessionExpiredHandling: true,
        });
    });

    it("keeps practice lifecycle helpers delegating through the domain lifecycle endpoint", async () => {
        const request = vi.fn().mockResolvedValue({ ok: true });
        const practice = createPracticeDomain({ request });

        await practice.startSession("session-1");
        await practice.pauseSession("session-1");
        await practice.resumeSession("session-1");
        await practice.endSession("session-1");

        expect(request).toHaveBeenNthCalledWith(1, "/practice/sessions/session-1/lifecycle", {
            method: "POST",
            body: JSON.stringify({ action: "start" }),
        });
        expect(request).toHaveBeenNthCalledWith(2, "/practice/sessions/session-1/lifecycle", {
            method: "POST",
            body: JSON.stringify({ action: "pause" }),
        });
        expect(request).toHaveBeenNthCalledWith(3, "/practice/sessions/session-1/lifecycle", {
            method: "POST",
            body: JSON.stringify({ action: "resume" }),
        });
        expect(request).toHaveBeenNthCalledWith(4, "/practice/sessions/session-1/lifecycle", {
            method: "POST",
            body: JSON.stringify({ action: "end" }),
        });
    });

    it("uploads learner sales-trainer audio through multipart form data without client-side duration payload", async () => {
        const request = vi.fn();
        const upload = vi.fn().mockResolvedValue({ submission_id: "submission-1" });
        const salesTrainer = createSalesTrainerDomain({
            request,
            upload,
            resolveApiBaseUrl: () => "http://localhost:3444/api/v1",
        });

        const file = new File(["audio"], "pitch.wav", { type: "audio/wav" });
        await salesTrainer.uploadAudioSubmission({
            file,
            unit_id: "unit-1",
            purpose: "sales_pitch",
            source_page: "sales_trainer_audio_upload",
        });

        expect(upload).toHaveBeenCalledTimes(1);
        expect(upload.mock.calls[0][0]).toBe("/sales-trainer/audio-submissions/upload");
        const formData = upload.mock.calls[0][1] as FormData;
        expect(formData.get("unit_id")).toBe("unit-1");
        expect(formData.get("purpose")).toBe("sales_pitch");
        expect(formData.get("source_page")).toBe("sales_trainer_audio_upload");
        expect(formData.get("auto_process")).toBe("true");
        expect(formData.get("file")).toBe(file);
    });

    it("builds learner and admin authorized sales-trainer audio file URLs without exposing storage keys", () => {
        const request = vi.fn();
        const upload = vi.fn();
        const salesTrainer = createSalesTrainerDomain({
            request,
            upload,
            resolveApiBaseUrl: () => "http://localhost:3444/api/v1",
        });
        const adminSalesTrainer = createAdminSalesTrainerDomain({
            request,
            upload,
            resolveApiBaseUrl: () => "http://localhost:3444/api/v1",
        });

        expect(salesTrainer.getAudioSubmissionFileUrl("submission-1")).toBe(
            "http://localhost:3444/api/v1/sales-trainer/audio-submissions/submission-1/file",
        );
        expect(adminSalesTrainer.getAudioSubmissionFileUrl("submission-1")).toBe(
            "http://localhost:3444/api/v1/admin/sales-trainer/audio-submissions/submission-1/file",
        );
    });

    it("uploads admin sales-trainer material versions through multipart form data", async () => {
        const request = vi.fn();
        const upload = vi.fn().mockResolvedValue({ version_id: "version-1" });
        const adminSalesTrainer = createAdminSalesTrainerDomain({
            request,
            upload,
            resolveApiBaseUrl: () => "http://localhost:3444/api/v1",
        });

        const file = new File(["deck"], "company-master.pptx", {
            type: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        });
        await adminSalesTrainer.uploadMaterialVersion("material-1", {
            file,
            version_label: "v2026.06",
            title: "公司主胶片 2026-06",
            release_notes: "替换错别字",
        });

        expect(upload).toHaveBeenCalledTimes(1);
        expect(upload.mock.calls[0][0]).toBe(
            "/admin/sales-trainer/materials/material-1/versions/upload",
        );
        const formData = upload.mock.calls[0][1] as FormData;
        expect(formData.get("version_label")).toBe("v2026.06");
        expect(formData.get("title")).toBe("公司主胶片 2026-06");
        expect(formData.get("release_notes")).toBe("替换错别字");
        expect(formData.get("file")).toBe(file);
    });

    it("previews and runs admin audio-submission regrade through the shared request seam", async () => {
        const request = vi.fn().mockResolvedValue({ regrade_run_id: "run-1" });
        const adminSalesTrainer = createAdminSalesTrainerDomain({
            request,
            upload: vi.fn(),
            resolveApiBaseUrl: () => "http://localhost:3444/api/v1",
        });

        await adminSalesTrainer.previewAudioSubmissionRegrade("submission-1", {
            target_revision_id: "prompt-revision-2",
        });
        await adminSalesTrainer.runAudioSubmissionRegrade("submission-1", {
            target_revision_id: "prompt-revision-2",
            reason: "评分 prompt 发布新版后追加重评记录",
        });

        expect(request).toHaveBeenNthCalledWith(
            1,
            "/admin/sales-trainer/regrades/audio-submissions/submission-1/preview",
            {
                method: "POST",
                body: JSON.stringify({ target_revision_id: "prompt-revision-2" }),
            },
        );
        expect(request).toHaveBeenNthCalledWith(
            2,
            "/admin/sales-trainer/regrades/audio-submissions/submission-1/run",
            {
                method: "POST",
                body: JSON.stringify({
                    target_revision_id: "prompt-revision-2",
                    reason: "评分 prompt 发布新版后追加重评记录",
                }),
            },
        );
    });
});
