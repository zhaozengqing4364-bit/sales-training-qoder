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
            resolveApiBaseUrl: () => "http://localhost:3444/api/v1",
        });

        expect(salesTrainer.getAudioSubmissionFileUrl("submission-1")).toBe(
            "http://localhost:3444/api/v1/sales-trainer/audio-submissions/submission-1/file",
        );
        expect(adminSalesTrainer.getAudioSubmissionFileUrl("submission-1")).toBe(
            "http://localhost:3444/api/v1/admin/sales-trainer/audio-submissions/submission-1/file",
        );
    });
});
