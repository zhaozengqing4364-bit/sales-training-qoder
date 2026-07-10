import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";

import { describe, expect, it, vi } from "vitest";

import {
    createAdminNewcomerTrainingDomain,
    createAdminSalesTrainerDomain,
    createAuthDomain,
    createNewcomerTrainingDomain,
    createPracticeDomain,
    createSalesTrainerDomain,
    createSupportRuntimeDomain,
} from "./client-domains";

function collectSourceFiles(directory: string): string[] {
    return readdirSync(directory).flatMap((entry) => {
        const path = join(directory, entry);
        const stats = statSync(path);
        if (stats.isDirectory()) {
            return collectSourceFiles(path);
        }
        return /\.(ts|tsx)$/.test(entry) ? [path] : [];
    });
}

describe("client domain factories", () => {
    it("keeps auth login on the shared request seam with session-expiry handling disabled", async () => {
        const request = vi.fn().mockResolvedValue({ token: "token-1" });
        const auth = createAuthDomain({ request });

        await auth.login({ email: "admin@test.com", password: "secret" });

        expect(request).toHaveBeenCalledWith("/auth/login", {
            method: "POST",
            body: JSON.stringify({ email: "admin@test.com", password: "secret" }),
            skipSessionExpiredHandling: true,
            timeoutMs: 8000,
            timeoutMessage: "登录超时，请重试。",
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
            timeoutMs: 8000,
            timeoutMessage: "登录配置加载超时，请刷新页面后重试。",
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

    it("loads admin sales-trainer capabilities through the domain facade", async () => {
        const request = vi.fn().mockResolvedValue({
            role: "support",
            role_label: "培训负责人",
            capabilities: {
                admin_full_access: false,
                manage_content: false,
                manage_questions: true,
                manage_modules: false,
                manage_prompts: false,
                review_readiness: true,
                view_records: true,
                view_global_records: false,
                retry_jobs: false,
                regrade_history: false,
                view_logs: true,
                view_settings: true,
            },
            capability_keys: [
                "manage_questions",
                "review_readiness",
                "view_records",
                "view_logs",
                "view_settings",
            ],
        });
        const adminSalesTrainer = createAdminSalesTrainerDomain({
            request,
            upload: vi.fn(),
            resolveApiBaseUrl: () => "http://localhost:3444/api/v1",
        });

        const result = await adminSalesTrainer.getCapabilities();

        expect(request).toHaveBeenCalledWith("/admin/sales-trainer/capabilities");
        expect(result.capabilities.view_records).toBe(true);
        expect(result.capabilities.review_readiness).toBe(true);
    });

    it("loads support runtime faults through the extracted domain normalizer", async () => {
        const request = vi.fn().mockResolvedValue({
            generated_at: "2026-06-13T00:00:00Z",
            items: [
                {
                    source: "session",
                    severity: "warning",
                    kind: "asset_changed",
                    summary: "配置资产变更后存在异常。",
                    detected_at: "2026-06-13T00:01:00Z",
                    session_id: "session-1",
                    scenario_type: "sales",
                    session_status: "completed",
                    report_status: "completed",
                    diagnostics: {
                        linked_asset_changes: [
                            {
                                asset_type: "voice_runtime_profile",
                                asset_label: "语音策略",
                                asset_id: "asset-1",
                                asset_name: "默认策略",
                                admin_path: "/admin/voice-runtime",
                                latest_change_label: "发布新版",
                                latest_change_type: "publish",
                                change_count_7d: "2",
                            },
                            {
                                asset_name: "",
                                admin_path: "",
                                latest_change_label: "",
                            },
                        ],
                    },
                },
            ],
            count: "1",
            limit: "20",
            severity: "warning",
        });
        const supportRuntime = createSupportRuntimeDomain({ request });

        const result = await supportRuntime.getFaults({
            limit: 20,
            severity: "warning",
        });

        expect(request).toHaveBeenCalledWith("/support/runtime/faults?limit=20&severity=warning");
        expect(result.count).toBe(1);
        expect(result.items[0].diagnostics.linked_asset_changes).toHaveLength(1);
        expect(result.items[0].diagnostics.linked_asset_changes[0].change_count_7d).toBe(2);
    });

    it("submits AI coach turn answers to the backend per-turn submit endpoint", async () => {
        const request = vi.fn().mockResolvedValue({ ok: true });
        const stream = vi.fn();
        const newcomerTraining = createNewcomerTrainingDomain({ request, stream });

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

    it("starts business-etiquette retraining sessions through the learner facade", async () => {
        const request = vi.fn().mockResolvedValue({ session_id: "session-retrain-1" });
        const stream = vi.fn();
        const newcomerTraining = createNewcomerTrainingDomain({ request, stream });

        const result = await newcomerTraining.startBusinessEtiquetteRetrainingSession({
            reason: "学员自愿切换新版重练",
        });

        expect(request).toHaveBeenCalledWith(
            "/newcomer-training/business-etiquette/retraining-sessions",
            {
                method: "POST",
                body: JSON.stringify({ reason: "学员自愿切换新版重练" }),
            },
        );
        expect(result.session_id).toBe("session-retrain-1");
    });

    it("loads learner business-etiquette quiz attempts through the unit-scoped endpoint", async () => {
        const request = vi.fn().mockResolvedValue({ items: [], total: 0 });
        const stream = vi.fn();
        const newcomerTraining = createNewcomerTrainingDomain({ request, stream });

        await newcomerTraining.listMyBusinessEtiquetteUnitQuizAttempts(
            "trust_foundation",
            { limit: 10, offset: 20 },
        );

        expect(request).toHaveBeenCalledWith(
            "/newcomer-training/business-etiquette/learning-units/trust_foundation/quiz-attempts?limit=10&offset=20",
        );
    });

    it("previews, publishes, and assigns business-etiquette releases through admin newcomer facade", async () => {
        const request = vi.fn()
            .mockResolvedValueOnce({ summary: { changed_chapters: 2 } })
            .mockResolvedValueOnce({ active_revision_no: 3 })
            .mockResolvedValueOnce({ created_session_ids: ["session-1"] });
        const adminNewcomerTraining = createAdminNewcomerTrainingDomain({
            request,
            upload: vi.fn(),
        });

        await adminNewcomerTraining.getBusinessEtiquetteReleaseImpact({
            training_pack_key: "business_etiquette_v1",
            target_revision_id: "revision-2",
        });
        await adminNewcomerTraining.publishBusinessEtiquetteRelease({
            training_pack_key: "business_etiquette_v1",
            strategy: "allow_voluntary_switch",
            assigned_user_ids: [],
            reason: "月度更新",
        });
        await adminNewcomerTraining.assignBusinessEtiquetteRetraining({
            user_ids: ["user-1"],
            reason: "指定新人重练",
        });

        expect(request).toHaveBeenNthCalledWith(
            1,
            "/admin/newcomer-training/business-etiquette/release-impact?training_pack_key=business_etiquette_v1&target_revision_id=revision-2",
        );
        expect(request).toHaveBeenNthCalledWith(
            2,
            "/admin/newcomer-training/business-etiquette/release",
            {
                method: "POST",
                body: JSON.stringify({
                    training_pack_key: "business_etiquette_v1",
                    strategy: "allow_voluntary_switch",
                    assigned_user_ids: [],
                    reason: "月度更新",
                }),
            },
        );
        expect(request).toHaveBeenNthCalledWith(
            3,
            "/admin/newcomer-training/business-etiquette/retraining-assignments",
            {
                method: "POST",
                body: JSON.stringify({
                    user_ids: ["user-1"],
                    reason: "指定新人重练",
                }),
            },
        );
    });

    it("keeps business-etiquette admin methods on sales-trainer as a compatibility facade", async () => {
        const request = vi.fn().mockResolvedValue({ summary: { changed_chapters: 1 } });
        const adminSalesTrainer = createAdminSalesTrainerDomain({
            request,
            upload: vi.fn(),
            resolveApiBaseUrl: () => "http://localhost:3444/api/v1",
        });

        await adminSalesTrainer.getBusinessEtiquetteReleaseImpact({
            training_pack_key: "business_etiquette_v1",
        });

        expect(request).toHaveBeenCalledWith(
            "/admin/newcomer-training/business-etiquette/release-impact?training_pack_key=business_etiquette_v1",
        );
    });

    it("reads admin AI coach responses from the shared unwrapped data seam", async () => {
        const aiCoach = {
            enabled: true,
            chat_enabled: true,
            streaming_enabled: true,
            entry_resume_policy: "latest_active_or_new",
            generation_timeout_seconds: 30,
            coach_mode: "mixed_drill",
            allowed_interaction_types: ["single_choice", "multiple_choice"],
            allowed_training_card_types: ["scenario_judgment"],
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
            empty_response_recovery_message: "我没有拿到可操作的训练卡片。",
            empty_response_recovery_prompts: ["继续下一题", "换个场景", "总结本轮"],
            generation_failure_recovery_message: "我已保留当前训练局。",
            generation_failure_recovery_prompts: ["重试下一题", "换主题", "总结一下"],
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
            upload: vi.fn(),
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

    it("keeps UI layers importing the public api facade instead of domain internals", () => {
        const roots = ["src/app", "src/components", "src/hooks"]
            .map((root) => join(process.cwd(), root));
        const forbiddenImport = /from\s+["'](?:@\/lib\/api\/(?:client-domains|domains\/[^"']+)|(?:\.\.?\/)+.*api\/(?:client-domains|domains\/[^"']+))["']/;
        const offenders = roots
            .flatMap(collectSourceFiles)
            .filter((path) => forbiddenImport.test(readFileSync(path, "utf8")))
            .map((path) => relative(process.cwd(), path));

        expect(offenders).toEqual([]);
    });
});
