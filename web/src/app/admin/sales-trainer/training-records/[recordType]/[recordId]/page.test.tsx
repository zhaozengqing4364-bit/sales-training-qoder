import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SalesTrainerTrainingRecordDetailPage from "./page";
import type { SalesTrainerTrainingRecordType } from "@/lib/api/types";

const {
    getTrainingRecordDetailMock,
    navigationState,
} = vi.hoisted(() => ({
    getTrainingRecordDetailMock: vi.fn(),
    navigationState: {
        params: {
            recordType: "audio_submission",
            recordId: "audio-1",
        },
        pathname: "/admin/sales-trainer/training-records/audio_submission/audio-1",
    },
}));

vi.mock("next/link", () => ({
    default: ({ href, children }: { href: string; children: ReactNode }) => <a href={href}>{children}</a>,
}));

vi.mock("next/navigation", () => ({
    useParams: () => navigationState.params,
    usePathname: () => navigationState.pathname,
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            admin: {
                ...actual.api.admin,
                salesTrainer: {
                    ...actual.api.admin.salesTrainer,
                    getTrainingRecordDetail: getTrainingRecordDetailMock,
                },
            },
        },
    };
});

function recordPayload(recordType: SalesTrainerTrainingRecordType, recordId: string) {
    const rawPayloads = {
        audio_submission: {
            audio_submission: {
                submission_id: recordId,
                original_filename: "ppt.wav",
                transcript: "介绍产品价值。",
            },
            quiz_attempt: null,
            ai_coach_session: null,
            unit_type: "audio_scoring",
        },
        quiz_attempt: {
            audio_submission: null,
            quiz_attempt: {
                attempt_id: recordId,
                paper_id: "paper-1",
                answer_count: 3,
            },
            ai_coach_session: null,
            unit_type: "quiz",
        },
        ai_coach_session: {
            audio_submission: null,
            quiz_attempt: null,
            ai_coach_session: {
                session_id: recordId,
                coach_mode: "mixed_drill",
            },
            unit_type: "ai_coach",
        },
    }[recordType];

    return {
        record_id: recordId,
        record_type: recordType,
        path_key: "newcomer_training_path_v1",
        path_revision_id: "path-revision-1",
        path_revision_no: 1,
        module_key: "business_skills",
        legacy_snapshot_only: false,
        unit_id: "unit-1",
        unit_name: "商务技巧训练",
        user_id: "user-1",
        user_name: "张三",
        user_email: "zhangsan@example.com",
        user_department: "销售一部",
        status: "scored",
        score: 16,
        max_score: 20,
        passed: false,
        submitted_at: "2026-05-28T00:00:00Z",
        material_snapshot: null,
        score_scheme_snapshot: null,
        task_brief_snapshot: null,
        effective_score: {
            score: 18,
            max_score: 20,
            passed: true,
            source: "latest_regrade",
            original_score: 16,
            original_max_score: 20,
            original_passed: false,
            score_delta: 2,
            latest_regrade_run_id: "run-1",
            history_overwrite: false,
        },
        latest_regrade: {
            regrade_run_id: "run-1",
            status: "completed",
        },
        score_explanation: {
            basis: "sales_trainer_phase2_projection_v1",
            summary: "重评后结构更清晰。",
            dimensions: [
                {
                    key: "structure",
                    label: "结构表达",
                    score: 8,
                    max_score: 10,
                    is_weak: false,
                },
            ],
            evidence: [
                {
                    type: "quote",
                    text: "引用了客户案例。",
                },
            ],
            issues: [
                {
                    type: "weak_detail",
                    text: "客户痛点不够具体。",
                },
            ],
            next_actions: [],
        },
        ability_profile: {
            basis: "sales_trainer_phase2_projection_v1",
            overall_score: 18,
            overall_passed: true,
            dimensions: [],
            weak_dimensions: [],
            evidence_count: 1,
        },
        remediation: {
            needed: true,
            reason: "需要补强结构表达。",
            action_label: "安排弱项复习",
            target_path: "/admin/sales-trainer/training-records",
            priority: "medium",
            weak_dimension_keys: ["structure"],
        },
        operation_logs: [
            {
                log_id: "log-1",
                action: "historical_regrade.completed",
                actor_role: "admin",
                created_at: "2026-05-28T01:00:00Z",
            },
        ],
        ...rawPayloads,
    };
}

describe("SalesTrainerTrainingRecordDetailPage", () => {
    beforeEach(() => {
        getTrainingRecordDetailMock.mockReset();
        getTrainingRecordDetailMock.mockImplementation((recordType: SalesTrainerTrainingRecordType, recordId: string) =>
            Promise.resolve(recordPayload(recordType, recordId)),
        );
    });

    it.each([
        ["audio_submission", "audio-1", /ppt\.wav/],
        ["quiz_attempt", "attempt-1", /paper-1/],
        ["ai_coach_session", "coach-1", /mixed_drill/],
    ] as const)("loads %s through the unified detail API", async (recordType, recordId, rawText) => {
        navigationState.params = { recordType, recordId };
        navigationState.pathname = `/admin/sales-trainer/training-records/${recordType}/${recordId}`;

        render(<SalesTrainerTrainingRecordDetailPage />);

        await waitFor(() => {
            expect(getTrainingRecordDetailMock).toHaveBeenCalledWith(recordType, recordId);
        });

        expect(await screen.findByText("训练记录详情")).toBeTruthy();
        expect(screen.getByText("张三 · 销售一部")).toBeTruthy();
        expect(screen.getAllByText("18 / 20").length).toBeGreaterThan(0);
        expect(screen.getByText("原始分 16 / 20")).toBeTruthy();
        expect(screen.getByText("run-1")).toBeTruthy();
        expect(screen.getAllByText("安排弱项复习").length).toBeGreaterThan(0);
        expect(screen.getByText("重评后结构更清晰。")).toBeTruthy();
        expect(screen.getByText("结构表达")).toBeTruthy();
        expect(screen.getByText("客户痛点不够具体。")).toBeTruthy();
        expect(screen.getByText("引用了客户案例。")).toBeTruthy();
        expect(screen.getByText("historical_regrade.completed")).toBeTruthy();
        expect(screen.getByText(rawText)).toBeTruthy();
    });
});
