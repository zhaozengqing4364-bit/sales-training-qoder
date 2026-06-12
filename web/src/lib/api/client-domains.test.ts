import { describe, expect, it, vi } from "vitest";

import {
    createAdminNewcomerTrainingDomain,
    createAdminSalesTrainerDomain,
    createAuthDomain,
    createNewcomerTrainingDomain,
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

    it("submits AI coach turn answers to the backend per-turn submit endpoint", async () => {
        const request = vi.fn().mockResolvedValue({ ok: true });
        const newcomerTraining = createNewcomerTrainingDomain({ request });

        await newcomerTraining.submitAiCoachTurn(
            "session-1",
            "turn-1",
            { answer_payload: { variant: "choice", option_ids: ["A"] } },
        );

        expect(request).toHaveBeenCalledWith(
            "/newcomer-training/ai-coach/sessions/session-1/turns/turn-1/submit",
            {
                method: "POST",
                body: JSON.stringify({
                    answer_payload: { variant: "choice", option_ids: ["A"] },
                }),
            },
        );
    });

    it("reads admin AI coach responses from the shared unwrapped data seam", async () => {
        const aiCoach = {
            enabled: true,
            chat_enabled: true,
            coach_mode: "mixed_drill",
            allowed_interaction_types: ["single_choice", "multiple_choice"],
            allowed_ui_event_types: [
                "quiz_card",
                "explanation_card",
                "summary_card",
                "followup_prompt",
            ],
            max_cards_per_message: 3,
            proactive_coaching_enabled: true,
            session_start_behavior: "plan_and_first_card",
            auto_advance_enabled: true,
            max_auto_steps_per_session: 5,
            correct_streak_to_increase_difficulty: 2,
            incorrect_streak_to_remediate: 1,
            incorrect_streak_to_pause: 2,
            remediation_strategy: "explain_then_retry",
            summary_when_mastery_reached: true,
            allowed_next_actions: [
                "continue_drill",
                "increase_difficulty",
                "remediate",
                "switch_scenario",
                "summarize",
                "ask_user_choice",
                "end_session",
            ],
            chat_welcome_message: "你好，我是商务技巧 AI 教练。",
            min_turns: 3,
            max_turns: 10,
            mastery_threshold: 80,
            prompt_template_id: "11111111-1111-1111-1111-111111111111",
            prompt_revision_id: null,
            prompt_contract_hash: null,
            scoring_prompt_template_id: null,
            scoring_prompt_revision_id: null,
            scoring_contract_hash: null,
            output_schema_version: "ai_coach_interaction_v1",
        };
        const request = vi.fn()
            .mockResolvedValueOnce({ module_key: "business_skills", ai_coach: aiCoach })
            .mockResolvedValueOnce({
                module_key: "business_skills",
                ai_coach: { ...aiCoach, mastery_threshold: 90 },
                revision_id: "revision-1",
            })
            .mockResolvedValueOnce({
                module_key: "business_skills",
                active_revision_id: "revision-1",
                active_revision_no: 7,
                previous_revision_id: null,
                change_class: "scoring_high_risk",
                impact_scope: "future_learners_only",
            });
        const adminNewcomerTraining = createAdminNewcomerTrainingDomain({
            request,
        });

        await expect(adminNewcomerTraining.getAiCoachConfig("business_skills"))
            .resolves.toEqual(aiCoach);
        await expect(adminNewcomerTraining.saveAiCoachConfig("business_skills", aiCoach))
            .resolves.toMatchObject({ ai_coach: { mastery_threshold: 90 } });
        await expect(adminNewcomerTraining.publishAiCoachConfig("business_skills"))
            .resolves.toMatchObject({ active_revision_no: 7 });
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
