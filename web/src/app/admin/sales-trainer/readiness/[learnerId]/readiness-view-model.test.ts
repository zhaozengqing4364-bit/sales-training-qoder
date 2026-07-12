import { describe, expect, it } from "vitest";

import type {
    ReadinessDossier,
    ReadinessDossierEvidence,
    ReadinessDossierRetrainingTask,
} from "@/lib/api/types/training-journey";

import {
    defaultCapabilitySelection,
    defaultEvidenceSelection,
    evidenceLabel,
    evidenceResultSummary,
    readinessDisplayMessage,
    recordTypeLabel,
    retrainingTaskResultText,
    statusLabel,
} from "./readiness-view-model";

describe("readiness view model", () => {
    it("maps evidence and unknown enums to user language", () => {
        const evidence = {
            evidence_id: "audio_submission:1",
            module_title: "产品讲解",
            record_type: "unknown_internal_type",
            status: "unknown_internal_status",
            score: 88,
            max_score: 100,
        } as ReadinessDossierEvidence;

        expect(evidenceLabel(evidence)).toBe("产品讲解");
        expect(evidenceResultSummary(evidence)).toBe("待确认，得分 88 / 100。");
        expect(recordTypeLabel(evidence.record_type)).toBe("训练证据");
        expect(statusLabel(evidence.status)).toBe("待确认");
    });

    it("redacts internal diagnostic vocabulary", () => {
        expect(
            readinessDisplayMessage(
                "[NEWCOMER_MODULE_BINDING_MISSING] runtime binding target_unit_id terminal (trace_id:abc)",
            ),
        ).toBe("真实语音对练后台接入配置缺失，请先处理训练路径配置。");
    });

    it("selects risk evidence and capability defaults before passing evidence", () => {
        const dossier = {
            competencies: [
                { capability_key: "pitch", status: "ai_failed" },
                { capability_key: "closing", status: "ai_passed" },
            ],
            evidence: [
                { evidence_id: "failed-1", passed: false, status: "failed" },
                { evidence_id: "passed-1", passed: true, status: "passed" },
            ],
        } as ReadinessDossier;

        expect(defaultCapabilitySelection(dossier)).toEqual(["pitch"]);
        expect(defaultEvidenceSelection(dossier)).toEqual(["failed-1"]);
    });

    it("formats retraining comparison without leaking raw status", () => {
        const task = {
            status: "completed",
            comparison: {
                after_passed: false,
                after_score: 60,
                after_max_score: 100,
            },
        } as ReadinessDossierRetrainingTask;

        expect(retrainingTaskResultText(task)).toBe("重练后结果：未通过，得分 60 / 100。");
    });
});
