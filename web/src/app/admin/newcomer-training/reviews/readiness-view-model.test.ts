import { describe, expect, it } from "vitest";

import type { ReadinessReviewQueueV1 } from "@/lib/api/types/newcomer-training";
import {
    normalizeReadinessState,
    readinessCompetencyStatusLabel,
    readinessEvidenceTypeLabel,
    readinessQueueLearnerName,
    readinessRiskLabel,
} from "./readiness-view-model";

const queueItem = {
    object_id: "dossier-1",
    object_summary: {
        learner: {
            learner_id: "opaque-learner-id",
            name: "",
            cohort_id: "cohort-1",
            cohort_name: "七月新人班",
        },
        path: {
            path_revision_id: "revision-1",
            title: "新人训练",
            revision_label: "首发版",
        },
        status: "ready_for_review",
    },
    queue_reason: "等待人工复核。",
    risk_band: "medium",
    evidence_gaps: [],
    reviewer_id: null,
    due_at: null,
    primary_action: {
        label: "复核训练档案",
        href: "/admin/newcomer-training/reviews/dossier-1",
    },
    capabilities: ["readiness.queue.read"],
    updated_at: "2026-07-18T00:00:00Z",
} satisfies ReadinessReviewQueueV1["items"][number];

describe("readiness review view-model", () => {
    it("maps closed contract values to user language", () => {
        expect(normalizeReadinessState("ready_for_review")).toBe("ready_for_review");
        expect(normalizeReadinessState("unknown_internal_state")).toBe("");
        expect(readinessRiskLabel("high")).toBe("高风险");
        expect(readinessCompetencyStatusLabel("quality_review")).toBe("质量待复核");
        expect(readinessEvidenceTypeLabel("audio_assessment")).toBe("录音讲解");
        expect(readinessEvidenceTypeLabel("future_type")).toBe("训练证据");
    });

    it("does not expose an opaque learner identifier as a display name", () => {
        expect(readinessQueueLearnerName(queueItem)).toBe("未命名学员");
    });
});
