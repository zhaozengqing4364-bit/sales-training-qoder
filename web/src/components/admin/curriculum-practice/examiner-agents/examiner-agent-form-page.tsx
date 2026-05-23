"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { AdminFormShell } from "@/components/admin/admin-layout-shells";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type { ExaminerAgentRecord } from "@/lib/api/types";
import { debug } from "@/lib/debug";

import { ExaminerAgentForm } from "./examiner-agent-form";
import {
    buildCreatePayload,
    buildUpdatePayload,
    createEmptyExaminerAgentForm,
    formFromRecord,
    validateExaminerAgentForm,
    type ExaminerAgentFormState,
} from "./examiner-agent-utils";

const BASE_PATH = "/admin/curriculum-practice/examiner-agents";

export interface ExaminerAgentFormPageProps {
    mode: "create" | "edit";
    agentId?: string;
}

export function ExaminerAgentFormPage({ mode, agentId }: ExaminerAgentFormPageProps) {
    const router = useRouter();
    const searchParams = useSearchParams();
    const sourceId = searchParams.get("from");
    const isEdit = mode === "edit";
    const [loading, setLoading] = useState(isEdit || Boolean(sourceId));
    const [loadError, setLoadError] = useState<string | null>(null);
    const [form, setForm] = useState<ExaminerAgentFormState>(() => createEmptyExaminerAgentForm());
    const [editTitle, setEditTitle] = useState("");
    const [actionError, setActionError] = useState<string | null>(null);
    const [prefillNotice, setPrefillNotice] = useState<string | null>(null);
    const [busy, setBusy] = useState(false);

    useEffect(() => {
        let cancelled = false;

        async function loadActiveScoringPolicy() {
            try {
                const ruleset = await api.admin.getActiveScoringRuleset("sales");
                const rulesetId = ruleset.ruleset_id ?? "";
                if (!rulesetId || cancelled || isEdit) return;
                setForm((current) => {
                    if (current.scoring_policy_id) return current;
                    return { ...current, scoring_policy_id: rulesetId };
                });
            } catch (err) {
                debug.warn("[ExaminerAgentFormPage] failed to load active scoring ruleset", { error: err });
            }
        }

        void loadActiveScoringPolicy();
        return () => {
            cancelled = true;
        };
    }, [isEdit]);

    useEffect(() => {
        if (isEdit && agentId) {
            void (async () => {
                setLoading(true);
                setLoadError(null);
                try {
                    const record = await api.admin.getExaminerAgent(agentId);
                    if (record.status !== "draft") {
                        setLoadError("仅草稿 ExamAgent 可编辑。");
                        return;
                    }
                    setForm(formFromRecord(record));
                    setEditTitle(record.name);
                } catch (err) {
                    setLoadError(getApiErrorMessage(err));
                } finally {
                    setLoading(false);
                }
            })();
            return;
        }

        if (!isEdit && sourceId) {
            void (async () => {
                setLoading(true);
                setLoadError(null);
                try {
                    const record = await api.admin.getExaminerAgent(sourceId);
                    const nextForm = formFromRecord(record);
                    nextForm.name = nextForm.name.endsWith(" (副本)")
                        ? nextForm.name
                        : `${nextForm.name} (副本)`;
                    setForm(nextForm);
                    setPrefillNotice("已基于已发布 ExamAgent 预填。推荐使用列表中的「复制为新草稿」由服务端自动计算配置。");
                } catch (err) {
                    setLoadError(getApiErrorMessage(err));
                } finally {
                    setLoading(false);
                }
            })();
        }
    }, [agentId, isEdit, sourceId]);

    const handleSubmit = async () => {
        setActionError(null);
        const validationError = validateExaminerAgentForm(form);
        if (validationError) {
            setActionError(validationError);
            return;
        }

        setBusy(true);
        try {
            if (isEdit && agentId) {
                await api.admin.updateExaminerAgent(agentId, buildUpdatePayload(form));
            } else {
                await api.admin.createExaminerAgent(buildCreatePayload(form));
            }
            router.push(BASE_PATH);
        } catch (err) {
            setActionError(`保存失败：${getApiErrorMessage(err)}`);
            debug.warn("[ExaminerAgentFormPage] failed to save agent", { error: err });
        } finally {
            setBusy(false);
        }
    };

    if (loading) {
        return <GlassCard className="p-8 text-slate-600">正在加载 ExamAgent...</GlassCard>;
    }

    if (loadError) {
        return (
            <GlassCard className="space-y-4 p-8">
                <p className="text-red-700">{loadError}</p>
                <Button variant="outline" onClick={() => router.push(BASE_PATH)}>返回列表</Button>
            </GlassCard>
        );
    }

    return (
        <AdminFormShell
            backHref={BASE_PATH}
            backLabel="返回列表"
            title={isEdit ? `编辑 ExamAgent：${editTitle || "草稿"}` : "新建 ExamAgent"}
            description="配置题目来源、学员等级策略、评分策略与 JSON 策略块。"
        >
            {actionError && <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">{actionError}</div>}
            {prefillNotice && <div className="rounded-2xl border border-blue-200 bg-blue-50 p-4 text-sm text-blue-800">{prefillNotice}</div>}

            <GlassCard className="space-y-4 p-6">
                <ExaminerAgentForm form={form} onChange={setForm} />
                <div className="flex gap-3">
                    <Button onClick={() => { void handleSubmit(); }} disabled={busy}>
                        {busy ? "保存中..." : isEdit ? "保存修改" : "创建草稿"}
                    </Button>
                    <Button variant="outline" onClick={() => router.push(BASE_PATH)} disabled={busy}>取消</Button>
                </div>
            </GlassCard>
        </AdminFormShell>
    );
}

export interface ExaminerAgentSimulationPageProps {
    agentId: string;
}

export function ExaminerAgentSimulationPage({ agentId }: ExaminerAgentSimulationPageProps) {
    const router = useRouter();
    const [agent, setAgent] = useState<ExaminerAgentRecord | null>(null);
    const [loading, setLoading] = useState(true);
    const [loadError, setLoadError] = useState<string | null>(null);
    const [simSampleAnswer, setSimSampleAnswer] = useState("");
    const [simLearnerLevel, setSimLearnerLevel] = useState("");
    const [simQuestionId, setSimQuestionId] = useState("");
    const [simulationResult, setSimulationResult] = useState<import("@/lib/api/types").ExaminerAgentSimulationResponse | null>(null);
    const [actionError, setActionError] = useState<string | null>(null);
    const [notice, setNotice] = useState<string | null>(null);
    const [busy, setBusy] = useState(false);

    useEffect(() => {
        void (async () => {
            setLoading(true);
            setLoadError(null);
            try {
                const record = await api.admin.getExaminerAgent(agentId);
                setAgent(record);
            } catch (err) {
                setLoadError(getApiErrorMessage(err));
            } finally {
                setLoading(false);
            }
        })();
    }, [agentId]);

    const handleSimulate = async () => {
        setNotice(null);
        setActionError(null);
        setSimulationResult(null);

        const trimmedAnswer = simSampleAnswer.trim();
        if (!trimmedAnswer) {
            setActionError("模拟回答（sample_answer）不能为空，请输入一段模拟回答。");
            return;
        }

        setBusy(true);
        try {
            const payload: import("@/lib/api/types").ExaminerAgentSimulationRequest = {
                sample_answer: trimmedAnswer,
            };
            if (simLearnerLevel) {
                payload.learner_level = simLearnerLevel as import("@/lib/api/types").ExaminerAgentLearnerLevel;
            }
            if (simQuestionId.trim()) {
                payload.question_id = simQuestionId.trim();
            }
            const result = await api.admin.simulateExaminerAgent(agentId, payload);
            setSimulationResult(result);
            setNotice(`模拟完成：${result.mode}`);
        } catch (err) {
            setActionError(`模拟失败：${getApiErrorMessage(err)}`);
        } finally {
            setBusy(false);
        }
    };

    if (loading) {
        return <GlassCard className="p-8 text-slate-600">正在加载 ExamAgent...</GlassCard>;
    }

    if (loadError || !agent) {
        return (
            <GlassCard className="space-y-4 p-8">
                <p className="text-red-700">{loadError || "无法加载 ExamAgent"}</p>
                <Button variant="outline" onClick={() => router.push(BASE_PATH)}>返回列表</Button>
            </GlassCard>
        );
    }

    return (
        <AdminFormShell
            backHref={BASE_PATH}
            backLabel="返回列表"
            title={`模拟测试：${agent.name}`}
            description="干跑模拟不会写入训练记录。sample_answer 必填。"
        >
            {notice && <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">{notice}</div>}
            {actionError && <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">{actionError}</div>}

            <GlassCard className="space-y-4 p-6">
                <div className="grid gap-4 md:grid-cols-3">
                    <label className="space-y-1 text-sm font-medium text-slate-700">
                        <span>模拟回答（sample_answer）</span>
                        <textarea
                            className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm"
                            rows={2}
                            value={simSampleAnswer}
                            onChange={(event) => setSimSampleAnswer(event.target.value)}
                            placeholder="输入一段模拟销售回答..."
                        />
                    </label>
                    <label className="space-y-1 text-sm font-medium text-slate-700">
                        <span>学员等级（可选）</span>
                        <select
                            className="w-full rounded-xl border border-slate-200 px-3 py-2"
                            value={simLearnerLevel}
                            onChange={(event) => setSimLearnerLevel(event.target.value)}
                        >
                            <option value="">不指定</option>
                            <option value="conservative">保守</option>
                            <option value="beginner">初级</option>
                            <option value="intermediate">中级</option>
                            <option value="advanced">高级</option>
                        </select>
                    </label>
                    <label className="space-y-1 text-sm font-medium text-slate-700">
                        <span>题目 ID（可选）</span>
                        <input
                            className="w-full rounded-xl border border-slate-200 px-3 py-2"
                            value={simQuestionId}
                            onChange={(event) => setSimQuestionId(event.target.value)}
                            placeholder="q-xxx"
                        />
                    </label>
                </div>
                <Button onClick={() => { void handleSimulate(); }} disabled={busy}>
                    {busy ? "模拟中..." : "运行模拟"}
                </Button>
            </GlassCard>

            {simulationResult && (
                <GlassCard className="space-y-3 border border-blue-200 bg-blue-50/80 p-4">
                    <h3 className="text-lg font-black text-slate-900">模拟结果</h3>
                    <div className="grid gap-2 text-sm text-slate-700 md:grid-cols-3">
                        <div><span className="font-medium">模式：</span>{simulationResult.mode}</div>
                        <div><span className="font-medium">mutates_records：</span>{String(simulationResult.mutates_records)}</div>
                        <div><span className="font-medium">ExamAgent ID：</span>{simulationResult.examiner_agent_id}</div>
                        {simulationResult.selected_question_id ? (
                            <div><span className="font-medium">选题 ID：</span>{simulationResult.selected_question_id}</div>
                        ) : null}
                        <div><span className="font-medium">学员等级：</span>{simulationResult.learner_level}</div>
                        {simulationResult.scoring_policy_id ? (
                            <div><span className="font-medium">评分策略 ID：</span>{simulationResult.scoring_policy_id}</div>
                        ) : null}
                        <div><span className="font-medium">超时秒数：</span>{simulationResult.timeout_seconds}</div>
                    </div>
                    {simulationResult.result ? (
                        <div className="grid gap-2 text-sm text-slate-700 md:grid-cols-3">
                            <div><span className="font-medium">得分：</span>{simulationResult.result.score ?? "无"}</div>
                            <div><span className="font-medium">通过：</span>{simulationResult.result.passed ? "是" : "否"}</div>
                            {simulationResult.result.feedback ? (
                                <div><span className="font-medium">反馈：</span>{simulationResult.result.feedback}</div>
                            ) : null}
                        </div>
                    ) : null}
                </GlassCard>
            )}
        </AdminFormShell>
    );
}
