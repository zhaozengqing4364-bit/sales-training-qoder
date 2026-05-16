"use client";

import { useCallback, useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { api, getApiErrorMessage, getExaminerAgentErrorDetails } from "@/lib/api/client";
import type {
    ExaminerAgentCreateRequest,
    ExaminerAgentGateResult,
    ExaminerAgentLearnerLevel,
    ExaminerAgentLearnerLevelStrategy,
    ExaminerAgentRecord,
    ExaminerAgentSimulationRequest,
    ExaminerAgentSimulationResponse,
    ExaminerAgentUpdateRequest,
} from "@/lib/api/types";
import { debug } from "@/lib/debug";

const LEARNER_LEVEL_OPTIONS: Array<{ value: ExaminerAgentLearnerLevel; label: string }> = [
    { value: "conservative", label: "保守" },
    { value: "beginner", label: "初级" },
    { value: "intermediate", label: "中级" },
    { value: "advanced", label: "高级" },
];

interface JsonFieldState {
    text: string;
    parsed: Record<string, unknown> | null;
    error: string | null;
}

interface FormState {
    name: string;
    description: string;
    question_source_ids_text: string;
    learner_default_level: ExaminerAgentLearnerLevel;
    learner_allowed_levels_text: string;
    scoring_policy_id: string;
    timeout_max_seconds: number;
    safety_config: JsonFieldState;
    prompt_config: JsonFieldState;
    simulation_config: JsonFieldState;
}

function emptyJsonField(): JsonFieldState {
    return { text: "{}", parsed: {}, error: null };
}

function createEmptyForm(): FormState {
    return {
        name: "",
        description: "",
        question_source_ids_text: "",
        learner_default_level: "intermediate",
        learner_allowed_levels_text: "conservative, beginner, intermediate, advanced",
        scoring_policy_id: "",
        timeout_max_seconds: 30,
        safety_config: emptyJsonField(),
        prompt_config: emptyJsonField(),
        simulation_config: emptyJsonField(),
    };
}

function parseJsonField(text: string): JsonFieldState {
    const trimmed = text.trim();
    if (!trimmed) return { text: trimmed, parsed: {}, error: null };
    try {
        const parsed = JSON.parse(trimmed);
        if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
            return { text: trimmed, parsed: null, error: "值必须是 JSON object。" };
        }
        return { text: trimmed, parsed: parsed as Record<string, unknown>, error: null };
    } catch (err) {
        return {
            text: trimmed,
            parsed: null,
            error: err instanceof Error ? err.message : "JSON 格式无效。",
        };
    }
}

function questionSourceIdsFromText(value: string): string[] {
    return value
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean);
}

function statusVariant(status: string): "green" | "orange" | "gray" {
    if (status === "published") return "green";
    if (status === "draft") return "orange";
    return "gray";
}

function statusLabel(status: string): string {
    if (status === "published") return "已发布";
    if (status === "draft") return "草稿";
    if (status === "archived") return "已归档";
    return status;
}

function learnerLevelLabel(level: string): string {
    const found = LEARNER_LEVEL_OPTIONS.find((option) => option.value === level);
    return found?.label ?? level;
}

function strategySummary(strategy: { default_level: string; allowed_levels: string[] }): string {
    const levels = strategy.allowed_levels.map((l) => learnerLevelLabel(l)).join(", ");
    return `默认：${learnerLevelLabel(strategy.default_level)} · 允许：${levels || "无"}`;
}

function formatDateTime(value?: string | null): string {
    if (!value) return "未记录";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "未记录";
    return date.toLocaleString("zh-CN", {
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
    });
}

function formFromRecord(record: ExaminerAgentRecord): FormState {
    return {
        name: record.name,
        description: record.description ?? "",
        question_source_ids_text: record.question_source_ids.join(", "),
        learner_default_level: record.learner_level_strategy.default_level,
        learner_allowed_levels_text: record.learner_level_strategy.allowed_levels.join(", "),
        scoring_policy_id: record.scoring_policy_id ?? "",
        timeout_max_seconds: record.timeout_config.max_seconds ?? 30,
        safety_config: {
            text: JSON.stringify(record.safety_config, null, 2),
            parsed: record.safety_config,
            error: null,
        },
        prompt_config: {
            text: JSON.stringify(record.prompt_config, null, 2),
            parsed: record.prompt_config,
            error: null,
        },
        simulation_config: {
            text: JSON.stringify(record.simulation_config, null, 2),
            parsed: record.simulation_config,
            error: null,
        },
    };
}

function buildStrategyObject(form: FormState): ExaminerAgentLearnerLevelStrategy {
    return {
        default_level: form.learner_default_level,
        allowed_levels: questionSourceIdsFromText(form.learner_allowed_levels_text) as ExaminerAgentLearnerLevel[],
    };
}

function buildCreatePayload(form: FormState): ExaminerAgentCreateRequest {
    return {
        name: form.name,
        description: form.description || null,
        question_source_ids: questionSourceIdsFromText(form.question_source_ids_text),
        learner_level_strategy: buildStrategyObject(form),
        scoring_policy_id: form.scoring_policy_id || null,
        timeout_config: { max_seconds: form.timeout_max_seconds },
        safety_config: form.safety_config.parsed ?? {},
        prompt_config: form.prompt_config.parsed ?? {},
        simulation_config: form.simulation_config.parsed ?? {},
    };
}

function buildUpdatePayload(form: FormState): ExaminerAgentUpdateRequest {
    return {
        name: form.name,
        description: form.description || null,
        question_source_ids: questionSourceIdsFromText(form.question_source_ids_text),
        learner_level_strategy: buildStrategyObject(form),
        scoring_policy_id: form.scoring_policy_id || null,
        timeout_config: { max_seconds: form.timeout_max_seconds },
        safety_config: form.safety_config.parsed ?? {},
        prompt_config: form.prompt_config.parsed ?? {},
        simulation_config: form.simulation_config.parsed ?? {},
    };
}

export default function AdminExaminerAgentsPage() {
    const [items, setItems] = useState<ExaminerAgentRecord[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [actionError, setActionError] = useState<string | null>(null);
    const [gateResults, setGateResults] = useState<ExaminerAgentGateResult[]>([]);
    const [notice, setNotice] = useState<string | null>(null);
    const [busyAgentId, setBusyAgentId] = useState<string | null>(null);
    const [editingAgentId, setEditingAgentId] = useState<string | null>(null);
    const [form, setForm] = useState<FormState>(() => createEmptyForm());
    const [statusFilter, setStatusFilter] = useState<string>("");
    const [simulationResult, setSimulationResult] = useState<ExaminerAgentSimulationResponse | null>(null);
    const [simSampleAnswer, setSimSampleAnswer] = useState("");
    const [simLearnerLevel, setSimLearnerLevel] = useState("");
    const [simQuestionId, setSimQuestionId] = useState("");

    const loadAgents = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const response = await api.admin.listExaminerAgents(statusFilter || undefined);
            setItems(response.items);
        } catch (err) {
            setError(`ExamAgent 加载失败：${getApiErrorMessage(err)}`);
            debug.warn("[AdminExaminerAgentsPage] failed to load agents", { error: err });
        } finally {
            setLoading(false);
        }
    }, [statusFilter]);

    useEffect(() => {
        void Promise.resolve().then(loadAgents);
    }, [loadAgents]);

    const handlePublish = async (record: ExaminerAgentRecord) => {
        setNotice(null);
        setActionError(null);
        setGateResults([]);
        setBusyAgentId(record.examiner_agent_id);
        try {
            const published = await api.admin.publishExaminerAgent(record.examiner_agent_id);
            setItems((current) =>
                current.map((item) => (item.examiner_agent_id === published.examiner_agent_id ? published : item)),
            );
            setNotice(`发布完成：${published.name} v${published.version}`);
        } catch (err) {
            const details = getExaminerAgentErrorDetails(err);
            setGateResults(details?.gate_results ?? []);
            setActionError(`发布失败：${getApiErrorMessage(err)}`);
            debug.warn("[AdminExaminerAgentsPage] failed to publish agent", {
                agentId: record.examiner_agent_id,
                error: err,
            });
        } finally {
            setBusyAgentId(null);
        }
    };

    const handleArchive = async (record: ExaminerAgentRecord) => {
        setNotice(null);
        setActionError(null);
        setGateResults([]);
        setSimulationResult(null);
        setBusyAgentId(record.examiner_agent_id);
        try {
            const archived = await api.admin.archiveExaminerAgent(record.examiner_agent_id);
            setItems((current) =>
                current.map((item) => (item.examiner_agent_id === archived.examiner_agent_id ? archived : item)),
            );
            setNotice(`归档完成：${archived.name}`);
        } catch (err) {
            setActionError(`归档失败：${getApiErrorMessage(err)}`);
            debug.warn("[AdminExaminerAgentsPage] failed to archive agent", {
                agentId: record.examiner_agent_id,
                error: err,
            });
        } finally {
            setBusyAgentId(null);
        }
    };

    const handleSimulate = async (record: ExaminerAgentRecord) => {
        setNotice(null);
        setActionError(null);
        setGateResults([]);
        setSimulationResult(null);

        const trimmedAnswer = simSampleAnswer.trim();
        if (!trimmedAnswer) {
            setActionError("模拟回答（sample_answer）不能为空，请输入一段模拟回答。");
            return;
        }

        setBusyAgentId(record.examiner_agent_id);
        try {
            const payload: ExaminerAgentSimulationRequest = {
                sample_answer: trimmedAnswer,
            };
            if (simLearnerLevel) {
                payload.learner_level = simLearnerLevel as ExaminerAgentLearnerLevel;
            }
            if (simQuestionId.trim()) {
                payload.question_id = simQuestionId.trim();
            }
            const result = await api.admin.simulateExaminerAgent(record.examiner_agent_id, payload);
            setSimulationResult(result);
            setNotice(`模拟完成：${result.mode}`);
        } catch (err) {
            setActionError(`模拟失败：${getApiErrorMessage(err)}`);
            debug.warn("[AdminExaminerAgentsPage] failed to simulate agent", {
                agentId: record.examiner_agent_id,
                error: err,
            });
        } finally {
            setBusyAgentId(null);
        }
    };

    const handleEdit = (record: ExaminerAgentRecord) => {
        setNotice(null);
        setActionError(null);
        setGateResults([]);
        setSimulationResult(null);
        setEditingAgentId(record.examiner_agent_id);
        setForm(formFromRecord(record));
    };

    const handleSubmit = async () => {
        setNotice(null);
        setActionError(null);
        setGateResults([]);
        setSimulationResult(null);

        const jsonErrors = [form.safety_config, form.prompt_config, form.simulation_config]
            .map((field, index) => {
                const names = ["安全配置", "提示词配置", "模拟配置"];
                return field.error ? `${names[index]} JSON 格式错误：${field.error}` : null;
            })
            .filter(Boolean);

        if (jsonErrors.length > 0) {
            setActionError(jsonErrors.join("；"));
            return;
        }

        const allowedLevels = questionSourceIdsFromText(form.learner_allowed_levels_text);
        if (allowedLevels.length === 0) {
            setActionError("允许等级不能为空，请至少填入一个等级。");
            return;
        }
        if (!allowedLevels.includes(form.learner_default_level)) {
            setActionError(`默认等级「${learnerLevelLabel(form.learner_default_level)}」不在允许等级列表中，请修正。`);
            return;
        }

        try {
            if (editingAgentId) {
                const updated = await api.admin.updateExaminerAgent(editingAgentId, buildUpdatePayload(form));
                setItems((current) =>
                    current.map((item) => (item.examiner_agent_id === updated.examiner_agent_id ? updated : item)),
                );
                setNotice(`保存完成：${updated.name}`);
                setEditingAgentId(null);
                setForm(createEmptyForm());
                return;
            }

            const created = await api.admin.createExaminerAgent(buildCreatePayload(form));
            setItems((current) => [created, ...current]);
            setNotice(`创建完成：${created.name}`);
            setForm(createEmptyForm());
        } catch (err) {
            setActionError(`保存失败：${getApiErrorMessage(err)}`);
            debug.warn("[AdminExaminerAgentsPage] failed to save agent", { error: err });
        }
    };

    if (loading) {
        return (
            <div className="rounded-2xl border border-slate-100 bg-white/80 p-8 text-slate-600">
                正在加载 ExamAgent 列表...
            </div>
        );
    }

    if (error) {
        return (
            <GlassCard className="space-y-4 border border-amber-200 bg-amber-50/80 p-8">
                <h1 className="text-2xl font-black text-slate-900">考试智能体管理</h1>
                <p className="text-sm text-amber-800">{error}</p>
                <Button onClick={loadAgents}>重试加载</Button>
            </GlassCard>
        );
    }

    return (
        <div className="space-y-8 pb-20">
            <header className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
                <div>
                    <h1 className="text-3xl font-black tracking-tight text-slate-900">考试智能体管理</h1>
                    <p className="mt-2 max-w-3xl text-sm text-slate-600">
                        管理 ExaminerAgent 配置，覆盖创建草稿、编辑、发布门禁、归档和干跑模拟测试。
                    </p>
                </div>
                <div className="flex gap-3">
                    <select
                        className="rounded-xl border border-slate-200 px-3 py-2 text-sm"
                        value={statusFilter}
                        onChange={(event) => setStatusFilter(event.target.value)}
                    >
                        <option value="">全部状态</option>
                        <option value="draft">草稿</option>
                        <option value="published">已发布</option>
                        <option value="archived">已归档</option>
                    </select>
                    <Button variant="outline" onClick={loadAgents}>
                        刷新列表
                    </Button>
                </div>
            </header>

            {notice && (
                <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">
                    {notice}
                </div>
            )}

            {actionError && (
                <div className="space-y-2 rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
                    <p>{actionError}</p>
                    {gateResults.length > 0 && (
                        <div className="space-y-2">
                            <ul className="list-disc space-y-1 pl-5">
                                {gateResults.map((result) => (
                                    <li key={`${result.gate_name}-${result.reason_code}-${result.message}`}>
                                        <span className="font-semibold">{result.reason_code}</span>
                                        ：{result.message}
                                    </li>
                                ))}
                            </ul>
                        </div>
                    )}
                </div>
            )}

            {simulationResult && (
                <GlassCard className="space-y-3 border border-blue-200 bg-blue-50/80 p-4">
                    <h3 className="text-lg font-black text-slate-900">模拟结果</h3>
                    <div className="grid gap-2 text-sm text-slate-700 md:grid-cols-3">
                        <div>
                            <span className="font-medium">模式：</span>
                            {simulationResult.mode}
                        </div>
                        <div>
                            <span className="font-medium">mutates_records：</span>
                            {String(simulationResult.mutates_records)}
                        </div>
                        <div>
                            <span className="font-medium">ExamAgent ID：</span>
                            {simulationResult.examiner_agent_id}
                        </div>
                        {simulationResult.selected_question_id && (
                            <div>
                                <span className="font-medium">选题 ID：</span>
                                {simulationResult.selected_question_id}
                            </div>
                        )}
                        <div>
                            <span className="font-medium">学员等级：</span>
                            {learnerLevelLabel(simulationResult.learner_level)}
                        </div>
                        {simulationResult.scoring_policy_id && (
                            <div>
                                <span className="font-medium">评分策略 ID：</span>
                                {simulationResult.scoring_policy_id}
                            </div>
                        )}
                        <div>
                            <span className="font-medium">超时秒数：</span>
                            {simulationResult.timeout_seconds}
                        </div>
                    </div>
                    {simulationResult.result && (
                        <div className="grid gap-2 text-sm text-slate-700 md:grid-cols-3">
                            <div>
                                <span className="font-medium">得分：</span>
                                {simulationResult.result.score ?? "无"}
                            </div>
                            <div>
                                <span className="font-medium">通过：</span>
                                {simulationResult.result.passed ? "是" : "否"}
                            </div>
                            {simulationResult.result.feedback && (
                                <div>
                                    <span className="font-medium">反馈：</span>
                                    {simulationResult.result.feedback}
                                </div>
                            )}
                        </div>
                    )}
                </GlassCard>
            )}

            <GlassCard className="space-y-4 p-6">
                <h2 className="text-xl font-black text-slate-900">
                    {editingAgentId ? "编辑 ExamAgent" : "创建 ExamAgent"}
                </h2>
                <div className="grid gap-4 md:grid-cols-2">
                    <label className="space-y-1 text-sm font-medium text-slate-700">
                        <span>名称</span>
                        <input
                            className="w-full rounded-xl border border-slate-200 px-3 py-2"
                            value={form.name}
                            onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
                        />
                    </label>
                    <label className="space-y-1 text-sm font-medium text-slate-700">
                        <span>描述</span>
                        <input
                            className="w-full rounded-xl border border-slate-200 px-3 py-2"
                            value={form.description}
                            onChange={(event) =>
                                setForm((current) => ({ ...current, description: event.target.value }))
                            }
                        />
                    </label>
                    <label className="space-y-1 text-sm font-medium text-slate-700">
                        <span>题目来源 ID（逗号分隔）</span>
                        <input
                            className="w-full rounded-xl border border-slate-200 px-3 py-2"
                            value={form.question_source_ids_text}
                            onChange={(event) =>
                                setForm((current) => ({ ...current, question_source_ids_text: event.target.value }))
                            }
                            placeholder="category-1, category-2"
                        />
                    </label>
                    <label className="space-y-1 text-sm font-medium text-slate-700">
                        <span>默认等级</span>
                        <select
                            className="w-full rounded-xl border border-slate-200 px-3 py-2"
                            value={form.learner_default_level}
                            onChange={(event) =>
                                setForm((current) => ({
                                    ...current,
                                    learner_default_level: event.target.value as ExaminerAgentLearnerLevel,
                                }))
                            }
                        >
                            {LEARNER_LEVEL_OPTIONS.map((option) => (
                                <option key={option.value} value={option.value}>
                                    {option.label}
                                </option>
                            ))}
                        </select>
                    </label>
                    <label className="space-y-1 text-sm font-medium text-slate-700">
                        <span>允许等级（逗号分隔）</span>
                        <input
                            className="w-full rounded-xl border border-slate-200 px-3 py-2"
                            value={form.learner_allowed_levels_text}
                            onChange={(event) =>
                                setForm((current) => ({
                                    ...current,
                                    learner_allowed_levels_text: event.target.value,
                                }))
                            }
                            placeholder="conservative, beginner, intermediate"
                        />
                    </label>
                    <label className="space-y-1 text-sm font-medium text-slate-700">
                        <span>评分策略 ID</span>
                        <input
                            className="w-full rounded-xl border border-slate-200 px-3 py-2"
                            value={form.scoring_policy_id}
                            onChange={(event) =>
                                setForm((current) => ({ ...current, scoring_policy_id: event.target.value }))
                            }
                        />
                    </label>
                    <label className="space-y-1 text-sm font-medium text-slate-700">
                        <span>超时上限（秒）</span>
                        <input
                            type="number"
                            className="w-full rounded-xl border border-slate-200 px-3 py-2"
                            value={form.timeout_max_seconds}
                            onChange={(event) =>
                                setForm((current) => ({
                                    ...current,
                                    timeout_max_seconds: Number(event.target.value),
                                }))
                            }
                        />
                    </label>
                </div>

                <div className="space-y-4">
                    {(["safety_config", "prompt_config", "simulation_config"] as const).map((key) => {
                        const label =
                            key === "safety_config"
                                ? "安全配置 (JSON)"
                                : key === "prompt_config"
                                  ? "提示词配置 (JSON)"
                                  : "模拟配置 (JSON)";
                        const field = form[key];
                        return (
                            <label key={key} className="space-y-1 block text-sm font-medium text-slate-700">
                                <span>{label}</span>
                                <textarea
                                    className="w-full rounded-xl border border-slate-200 px-3 py-2 font-mono text-xs"
                                    rows={3}
                                    value={field.text}
                                    onChange={(event) => {
                                        const updated = parseJsonField(event.target.value);
                                        setForm((current) => ({ ...current, [key]: updated }));
                                    }}
                                />
                                {field.error && (
                                    <p className="mt-1 text-xs text-red-600">{field.error}</p>
                                )}
                            </label>
                        );
                    })}
                </div>

                <div className="flex gap-3">
                    <Button onClick={() => void handleSubmit()}>
                        {editingAgentId ? "保存修改" : "创建草稿"}
                    </Button>
                    {editingAgentId && (
                        <Button
                            variant="outline"
                            onClick={() => {
                                setEditingAgentId(null);
                                setForm(createEmptyForm());
                            }}
                        >
                            取消编辑
                        </Button>
                    )}
                </div>
            </GlassCard>

            <GlassCard className="space-y-4 p-6">
                <h2 className="text-xl font-black text-slate-900">模拟配置</h2>
                <p className="text-xs text-slate-500">
                    点击列表行的「模拟」按钮前，可在此配置模拟参数。sample_answer 必填。
                </p>
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
                            {LEARNER_LEVEL_OPTIONS.map((option) => (
                                <option key={option.value} value={option.value}>
                                    {option.label}
                                </option>
                            ))}
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
            </GlassCard>

            <GlassCard className="space-y-4 p-6">
                <div className="flex items-center justify-between">
                    <h2 className="text-xl font-black text-slate-900">ExamAgent 列表</h2>
                    <Badge variant="gray">{items.length} agents</Badge>
                </div>
                <div className="grid gap-3">
                    {items.map((item) => (
                        <div
                            key={item.examiner_agent_id}
                            className="rounded-2xl border border-slate-100 bg-white/80 p-4"
                        >
                            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                                <div className="flex-1">
                                    <div className="flex flex-wrap items-center gap-2">
                                        <h3 className="font-bold text-slate-900">{item.name}</h3>
                                        <Badge variant={statusVariant(item.status)}>
                                            {statusLabel(item.status)} · v{item.version}
                                        </Badge>
                                    </div>
                                    <p className="mt-1 text-sm text-slate-600">
                                        等级策略：{strategySummary(item.learner_level_strategy)}
                                        {item.scoring_policy_id
                                            ? ` · 评分策略：${item.scoring_policy_id}`
                                            : ""}
                                    </p>
                                    {item.description && (
                                        <p className="mt-1 text-sm text-slate-500">{item.description}</p>
                                    )}
                                    <p className="mt-1 text-xs text-slate-500">
                                        题目来源：{item.question_source_ids.join(", ") || "无"}
                                        {" · "}超时：{item.timeout_config.max_seconds}s
                                    </p>
                                    <p className="mt-1 text-xs text-slate-400">
                                        创建：{formatDateTime(item.created_at)}
                                        {item.published_at ? ` · 发布：${formatDateTime(item.published_at)}` : ""}
                                    </p>
                                </div>
                                <div className="flex gap-2">
                                    {item.status === "draft" ? (
                                        <Button variant="outline" onClick={() => handleEdit(item)}>
                                            编辑
                                        </Button>
                                    ) : (
                                        <span className="self-center text-xs text-slate-500">
                                            仅草稿可编辑
                                        </span>
                                    )}
                                    <Button
                                        onClick={() => void handlePublish(item)}
                                        disabled={item.status === "published" || busyAgentId !== null}
                                    >
                                        {busyAgentId === item.examiner_agent_id ? "处理中..." : "发布"}
                                    </Button>
                                    {item.status !== "archived" && (
                                        <Button
                                            variant="outline"
                                            onClick={() => void handleArchive(item)}
                                            disabled={busyAgentId !== null}
                                        >
                                            {busyAgentId === item.examiner_agent_id ? "处理中..." : "归档"}
                                        </Button>
                                    )}
                                    <Button
                                        variant="outline"
                                        onClick={() => void handleSimulate(item)}
                                        disabled={busyAgentId !== null}
                                    >
                                        {busyAgentId === item.examiner_agent_id ? "处理中..." : "模拟"}
                                    </Button>
                                </div>
                            </div>
                        </div>
                    ))}
                    {items.length === 0 && (
                        <p className="text-sm text-slate-500">暂无 ExamAgent 记录。</p>
                    )}
                </div>
            </GlassCard>
        </div>
    );
}
