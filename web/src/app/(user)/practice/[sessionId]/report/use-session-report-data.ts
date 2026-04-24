import { useCallback, useEffect, useState } from "react";

import { api, getApiErrorMessage } from "@/lib/api/client";
import type { PracticeSessionReport } from "@/lib/api/types";
import { debug } from "@/lib/debug";

export interface SessionReportDataState {
    loading: boolean;
    report: PracticeSessionReport | null;
    error: string | null;
    reload: () => Promise<void>;
}

export function useSessionReportData(sessionId: string): SessionReportDataState {
    const [loading, setLoading] = useState(true);
    const [report, setReport] = useState<PracticeSessionReport | null>(null);
    const [error, setError] = useState<string | null>(null);

    const reload = useCallback(async () => {
        setLoading(true);
        setError(null);

        try {
            const data = await api.sessions.getReport(sessionId);
            setReport(data);
            debug.log("[Report] Loaded unified evidence contract", {
                sessionId,
                scenarioType: data.scenario_type,
                overallScore: data.overall_score,
                evaluable: data.evaluable,
                notEvaluableReason: data.not_evaluable_reason,
                evidenceComplete: data.evidence_completeness?.complete,
                presentationReviewAvailable: Boolean(data.presentation_review),
            });
        } catch (err) {
            setReport(null);
            setError(`统一训练证据加载失败：${getApiErrorMessage(err)}`);
            debug.error("[Report] Unified evidence contract load failed", {
                sessionId,
                error: err,
            });
        } finally {
            setLoading(false);
        }
    }, [sessionId]);

    useEffect(() => {
        void reload();
    }, [reload]);

    return {
        loading,
        report,
        error,
        reload,
    };
}
