"use client";

import { useCallback, useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { api, getApiErrorMessage, getPracticeTemplateErrorDetails } from "@/lib/api/client";
import type { CurriculumPlanStage, PracticeTemplateGateResult, PracticeTemplateMutationRequest, PracticeTemplateRecord } from "@/lib/api/types";
import { debug } from "@/lib/debug";

type FormState = Omit<Required<PracticeTemplateMutationRequest>, "curriculum_plan" | "max_stage_duration_seconds"> & {
    curriculum_plan: NonNullable<PracticeTemplateMutationRequest["curriculum_plan"]>;
    max_stage_duration_seconds: number;
};

function emptyStage(order: number): CurriculumPlanStage {
    return {
        template_stage_key: `template_stage_${order}`,
        order,
        name: `阶段 ${order}`,
        template_ref: {
            asset_type: "practice_template",
            asset_id: "",
            version: 1,
            hash: "",
            snapshot_label: "published",
        },
        completion_policy: {
            min_score: 7,
            min_rounds: 1,
            max_duration_seconds: 600,
        },
        failure_policy: "retry_current",
        prerequisites: [],
    };
}

const EMPTY_FORM: FormState = {
    name: "",
    description: "",
    scenario_type: "sales",
    mode: "customer_roleplay",
    agent_id: "",
    persona_id: "",
    runtime_profile_id: "",
    voice_mode: "stepfun_realtime",
    scoring_ruleset_id: "",
    knowledge_base_refs: [],
    curriculum_plan: {
        name: "",
        description: "",
        max_stage_duration_seconds: 600,
        stages: [emptyStage(1)],
    },
    max_stage_duration_seconds: 600,
};

function statusVariant(status: string): "green" | "orange" | "gray" {
    if (status === "published") return "green";
    if (status === "draft") return "orange";
    return "gray";
}

function formFromTemplate(template: PracticeTemplateRecord): FormState {
    return {
        name: template.name,
        description: template.description ?? "",
        scenario_type: template.scenario_type === "presentation" ? "presentation" : "sales",
        mode: template.mode === "customer_roleplay" ? "customer_roleplay" : template.mode,
        agent_id: template.agent_id,
        persona_id: template.persona_id,
        runtime_profile_id: template.runtime_profile_id,
        voice_mode: template.voice_mode === "legacy" ? "legacy" : "stepfun_realtime",
        scoring_ruleset_id: template.scoring_ruleset_id,
        knowledge_base_refs: template.knowledge_base_refs,
        curriculum_plan: template.curriculum_plan ?? EMPTY_FORM.curriculum_plan,
        max_stage_duration_seconds: template.max_stage_duration_seconds ?? EMPTY_FORM.max_stage_duration_seconds,
    };
}

function refsFromText(value: string): string[] {
    return value.split(",").map((item) => item.trim()).filter(Boolean);
}

function prerequisitesFromText(value: string) {
    return refsFromText(value).map((templateStageKey) => ({
        template_stage_key: templateStageKey,
        required_result: "completed" as const,
    }));
}

function failurePolicyFromValue(value: string): CurriculumPlanStage["failure_policy"] {
    if (value === "fallback_to_previous" || value === "allow_skip") return value;
    return "retry_current";
}

export default function AdminPracticeTemplatesPage() {
    const [items, setItems] = useState<PracticeTemplateRecord[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [actionError, setActionError] = useState<string | null>(null);
    const [gateResults, setGateResults] = useState<PracticeTemplateGateResult[]>([]);
    const [notice, setNotice] = useState<string | null>(null);
    const [busyTemplateId, setBusyTemplateId] = useState<string | null>(null);
    const [editingTemplateId, setEditingTemplateId] = useState<string | null>(null);
    const [form, setForm] = useState<FormState>(EMPTY_FORM);

    const loadTemplates = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const response = await api.admin.listPracticeTemplates();
            setItems(response.items);
        } catch (err) {
            setError(`课程训练模板加载失败：${getApiErrorMessage(err)}`);
            debug.warn("[AdminPracticeTemplatesPage] failed to load templates", { error: err });
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        void Promise.resolve().then(loadTemplates);
    }, [loadTemplates]);

    const handlePublish = async (template: PracticeTemplateRecord) => {
        setNotice(null);
        setActionError(null);
        setBusyTemplateId(template.template_id);
        try {
            const published = await api.admin.publishPracticeTemplate(template.template_id);
            setItems((current) => current.map((item) => (item.template_id === published.template_id ? published : item)));
            setNotice(`发布完成：${published.name} v${published.version}`);
        } catch (err) {
            setGateResults(getPracticeTemplateErrorDetails(err)?.gate_results ?? []);
            setActionError(`发布失败：${getApiErrorMessage(err)}`);
            debug.warn("[AdminPracticeTemplatesPage] failed to publish template", { templateId: template.template_id, error: err });
        } finally {
            setBusyTemplateId(null);
        }
    };

    const handleArchive = async (template: PracticeTemplateRecord) => {
        setNotice(null);
        setActionError(null);
        setGateResults([]);
        setBusyTemplateId(template.template_id);
        try {
            const archived = await api.admin.archivePracticeTemplate(template.template_id);
            setItems((current) => current.map((item) => (item.template_id === archived.template_id ? archived : item)));
            setNotice(`归档完成：${archived.name}`);
        } catch (err) {
            setActionError(`归档失败：${getApiErrorMessage(err)}`);
            debug.warn("[AdminPracticeTemplatesPage] failed to archive template", { templateId: template.template_id, error: err });
        } finally {
            setBusyTemplateId(null);
        }
    };

    const handleEdit = (template: PracticeTemplateRecord) => {
        setNotice(null);
        setActionError(null);
        setGateResults([]);
        setEditingTemplateId(template.template_id);
        setForm(formFromTemplate(template));
    };

    const handleSubmit = async () => {
        setNotice(null);
        setActionError(null);
        setGateResults([]);
        try {
            if (editingTemplateId) {
                const updated = await api.admin.updatePracticeTemplate(editingTemplateId, form);
                setItems((current) => current.map((item) => (item.template_id === updated.template_id ? updated : item)));
                setNotice(`保存完成：${updated.name}`);
                setEditingTemplateId(null);
                setForm(EMPTY_FORM);
                return;
            }

            const created = await api.admin.createPracticeTemplate(form);
            setItems((current) => [created, ...current]);
            setNotice(`创建完成：${created.name}`);
            setForm(EMPTY_FORM);
        } catch (err) {
            setActionError(`保存失败：${getApiErrorMessage(err)}`);
            debug.warn("[AdminPracticeTemplatesPage] failed to save template", { error: err });
        }
    };

    const updateCurriculumPlan = (patch: Partial<NonNullable<FormState["curriculum_plan"]>>) => {
        setForm((current) => ({
            ...current,
            curriculum_plan: {
                ...(current.curriculum_plan ?? EMPTY_FORM.curriculum_plan),
                ...patch,
            },
        }));
    };

    const updateStage = (stageIndex: number, patch: Partial<CurriculumPlanStage>) => {
        setForm((current) => {
            const curriculumPlan = current.curriculum_plan ?? EMPTY_FORM.curriculum_plan;
            return {
                ...current,
                curriculum_plan: {
                    ...curriculumPlan,
                    stages: curriculumPlan.stages.map((stage, index) => (
                        index === stageIndex ? { ...stage, ...patch } : stage
                    )),
                },
            };
        });
    };

    const updateStageCompletionPolicy = (
        stageIndex: number,
        patch: Partial<CurriculumPlanStage["completion_policy"]>,
    ) => {
        setForm((current) => {
            const curriculumPlan = current.curriculum_plan ?? EMPTY_FORM.curriculum_plan;
            return {
                ...current,
                curriculum_plan: {
                    ...curriculumPlan,
                    stages: curriculumPlan.stages.map((stage, index) => (
                        index === stageIndex
                            ? { ...stage, completion_policy: { ...stage.completion_policy, ...patch } }
                            : stage
                    )),
                },
            };
        });
    };

    const updateStageTemplateRef = (
        stageIndex: number,
        patch: Partial<CurriculumPlanStage["template_ref"]>,
    ) => {
        setForm((current) => {
            const curriculumPlan = current.curriculum_plan ?? EMPTY_FORM.curriculum_plan;
            return {
                ...current,
                curriculum_plan: {
                    ...curriculumPlan,
                    stages: curriculumPlan.stages.map((stage, index) => (
                        index === stageIndex
                            ? { ...stage, template_ref: { ...stage.template_ref, ...patch } }
                            : stage
                    )),
                },
            };
        });
    };

    const addStage = () => {
        setForm((current) => {
            const curriculumPlan = current.curriculum_plan ?? EMPTY_FORM.curriculum_plan;
            return {
                ...current,
                curriculum_plan: {
                    ...curriculumPlan,
                    stages: [...curriculumPlan.stages, emptyStage(curriculumPlan.stages.length + 1)],
                },
            };
        });
    };

    const removeStage = (stageIndex: number) => {
        setForm((current) => {
            const curriculumPlan = current.curriculum_plan ?? EMPTY_FORM.curriculum_plan;
            const nextStages = curriculumPlan.stages.filter((_, index) => index !== stageIndex);
            return {
                ...current,
                curriculum_plan: {
                    ...curriculumPlan,
                    stages: nextStages.length > 0 ? nextStages : [emptyStage(1)],
                },
            };
        });
    };

    if (loading) {
        return <div className="rounded-2xl border border-slate-100 bg-white/80 p-8 text-slate-600">正在加载课程训练模板...</div>;
    }

    if (error) {
        return (
            <GlassCard className="space-y-4 border border-amber-200 bg-amber-50/80 p-8">
                <h1 className="text-2xl font-black text-slate-900">课程训练模板</h1>
                <p className="text-sm text-amber-800">{error}</p>
                <Button onClick={loadTemplates}>重试加载</Button>
            </GlassCard>
        );
    }

    return (
        <div className="space-y-8 pb-20">
            <header className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
                <div>
                    <h1 className="text-3xl font-black tracking-tight text-slate-900">课程训练模板</h1>
                    <p className="mt-2 max-w-3xl text-sm text-slate-600">
                        管理 PRD #46 最小 PracticeTemplate 骨架、发布门禁和运行时引用。当前页面覆盖模板创建、编辑、列表与发布入口。
                    </p>
                </div>
                <Button variant="outline" onClick={loadTemplates}>刷新模板</Button>
            </header>

            {notice && <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">{notice}</div>}
            {actionError && (
                <div className="space-y-2 rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
                    <p>{actionError}</p>
                    {gateResults.length > 0 && (
                        <div className="space-y-2">
                            {gateResults.some((result) => result.gate_name.startsWith("curriculum_plan")) && (
                                <Badge variant="red">Stage validation errors</Badge>
                            )}
                            <ul className="list-disc space-y-1 pl-5">
                                {gateResults.map((result) => (
                                    <li key={`${result.gate_name}-${result.reason_code}-${result.message}`}>
                                        <span className="font-semibold">{result.reason_code}</span>：{result.message}
                                    </li>
                                ))}
                            </ul>
                        </div>
                    )}
                </div>
            )}

            <GlassCard className="space-y-4 p-6">
                <h2 className="text-xl font-black text-slate-900">{editingTemplateId ? "编辑模板" : "创建模板"}</h2>
                <div className="grid gap-4 md:grid-cols-2">
                    <label className="space-y-1 text-sm font-medium text-slate-700">
                        <span>模板名称</span>
                        <input className="w-full rounded-xl border border-slate-200 px-3 py-2" value={form.name} onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))} />
                    </label>
                    <label className="space-y-1 text-sm font-medium text-slate-700">
                        <span>描述</span>
                        <input className="w-full rounded-xl border border-slate-200 px-3 py-2" value={form.description ?? ""} onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))} />
                    </label>
                    <label className="space-y-1 text-sm font-medium text-slate-700">
                        <span>Agent ID</span>
                        <input className="w-full rounded-xl border border-slate-200 px-3 py-2" value={form.agent_id} onChange={(event) => setForm((current) => ({ ...current, agent_id: event.target.value }))} />
                    </label>
                    <label className="space-y-1 text-sm font-medium text-slate-700">
                        <span>Persona ID</span>
                        <input className="w-full rounded-xl border border-slate-200 px-3 py-2" value={form.persona_id} onChange={(event) => setForm((current) => ({ ...current, persona_id: event.target.value }))} />
                    </label>
                    <label className="space-y-1 text-sm font-medium text-slate-700">
                        <span>Runtime Profile ID</span>
                        <input className="w-full rounded-xl border border-slate-200 px-3 py-2" value={form.runtime_profile_id} onChange={(event) => setForm((current) => ({ ...current, runtime_profile_id: event.target.value }))} />
                    </label>
                    <label className="space-y-1 text-sm font-medium text-slate-700">
                        <span>Scoring Ruleset ID</span>
                        <input className="w-full rounded-xl border border-slate-200 px-3 py-2" value={form.scoring_ruleset_id} onChange={(event) => setForm((current) => ({ ...current, scoring_ruleset_id: event.target.value }))} />
                    </label>
                    <label className="space-y-1 text-sm font-medium text-slate-700">
                        <span>Knowledge Base Refs</span>
                        <input className="w-full rounded-xl border border-slate-200 px-3 py-2" value={form.knowledge_base_refs.join(",")} onChange={(event) => setForm((current) => ({ ...current, knowledge_base_refs: refsFromText(event.target.value) }))} />
                    </label>
                </div>

                <div className="space-y-4 rounded-2xl border border-slate-100 bg-slate-50/70 p-4">
                    <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                        <div>
                            <h3 className="text-lg font-black text-slate-900">CurriculumPlan</h3>
                            <p className="text-xs text-slate-500">配置多阶段模板图、完成策略和失败策略。</p>
                        </div>
                        <Button variant="outline" onClick={addStage}>添加 Stage</Button>
                    </div>
                    <div className="grid gap-4 md:grid-cols-2">
                        <label className="space-y-1 text-sm font-medium text-slate-700">
                            <span>CurriculumPlan Name</span>
                            <input className="w-full rounded-xl border border-slate-200 px-3 py-2" value={form.curriculum_plan?.name ?? ""} onChange={(event) => updateCurriculumPlan({ name: event.target.value })} />
                        </label>
                        <label className="space-y-1 text-sm font-medium text-slate-700">
                            <span>Max Stage Duration Seconds</span>
                            <input
                                type="number"
                                className="w-full rounded-xl border border-slate-200 px-3 py-2"
                                value={form.max_stage_duration_seconds ?? 0}
                                onChange={(event) => {
                                    const duration = Number(event.target.value);
                                    setForm((current) => ({ ...current, max_stage_duration_seconds: duration }));
                                    updateCurriculumPlan({ max_stage_duration_seconds: duration });
                                }}
                            />
                        </label>
                    </div>
                    <div className="space-y-3">
                        {(form.curriculum_plan?.stages ?? []).map((stage, index) => (
                            <div key={`${stage.template_stage_key}-${index}`} className="space-y-3 rounded-2xl border border-white bg-white/80 p-4">
                                <div className="flex items-center justify-between gap-3">
                                    <Badge variant="blue">Stage {index + 1}</Badge>
                                    <Button variant="outline" onClick={() => { removeStage(index); }}>移除 Stage</Button>
                                </div>
                                <div className="grid gap-4 md:grid-cols-2">
                                    <label className="space-y-1 text-sm font-medium text-slate-700">
                                        <span>{`Stage Key ${index + 1}`}</span>
                                        <input className="w-full rounded-xl border border-slate-200 px-3 py-2" value={stage.template_stage_key} onChange={(event) => updateStage(index, { template_stage_key: event.target.value })} />
                                    </label>
                                    <label className="space-y-1 text-sm font-medium text-slate-700">
                                        <span>{`Stage Name ${index + 1}`}</span>
                                        <input className="w-full rounded-xl border border-slate-200 px-3 py-2" value={stage.name} onChange={(event) => updateStage(index, { name: event.target.value })} />
                                    </label>
                                    <label className="space-y-1 text-sm font-medium text-slate-700">
                                        <span>{`Stage Template Asset ID ${index + 1}`}</span>
                                        <input className="w-full rounded-xl border border-slate-200 px-3 py-2" value={stage.template_ref.asset_id} onChange={(event) => updateStageTemplateRef(index, { asset_id: event.target.value })} />
                                    </label>
                                    <label className="space-y-1 text-sm font-medium text-slate-700">
                                        <span>{`Stage Template Hash ${index + 1}`}</span>
                                        <input className="w-full rounded-xl border border-slate-200 px-3 py-2" value={stage.template_ref.hash} onChange={(event) => updateStageTemplateRef(index, { hash: event.target.value })} />
                                    </label>
                                    <label className="space-y-1 text-sm font-medium text-slate-700">
                                        <span>{`Stage Min Score ${index + 1}`}</span>
                                        <input type="number" className="w-full rounded-xl border border-slate-200 px-3 py-2" value={stage.completion_policy.min_score} onChange={(event) => updateStageCompletionPolicy(index, { min_score: Number(event.target.value) })} />
                                    </label>
                                    <label className="space-y-1 text-sm font-medium text-slate-700">
                                        <span>{`Stage Min Rounds ${index + 1}`}</span>
                                        <input type="number" className="w-full rounded-xl border border-slate-200 px-3 py-2" value={stage.completion_policy.min_rounds} onChange={(event) => updateStageCompletionPolicy(index, { min_rounds: Number(event.target.value) })} />
                                    </label>
                                    <label className="space-y-1 text-sm font-medium text-slate-700">
                                        <span>{`Stage Max Duration Seconds ${index + 1}`}</span>
                                        <input type="number" className="w-full rounded-xl border border-slate-200 px-3 py-2" value={stage.completion_policy.max_duration_seconds} onChange={(event) => updateStageCompletionPolicy(index, { max_duration_seconds: Number(event.target.value) })} />
                                    </label>
                                    <label className="space-y-1 text-sm font-medium text-slate-700">
                                        <span>{`Stage Failure Policy ${index + 1}`}</span>
                                        <select className="w-full rounded-xl border border-slate-200 px-3 py-2" value={stage.failure_policy ?? "retry_current"} onChange={(event) => updateStage(index, { failure_policy: failurePolicyFromValue(event.target.value) })}>
                                            <option value="retry_current">retry_current</option>
                                            <option value="fallback_to_previous">fallback_to_previous</option>
                                            <option value="allow_skip">allow_skip</option>
                                        </select>
                                    </label>
                                    <label className="space-y-1 text-sm font-medium text-slate-700 md:col-span-2">
                                        <span>{`Stage Prerequisites ${index + 1}`}</span>
                                        <input className="w-full rounded-xl border border-slate-200 px-3 py-2" value={(stage.prerequisites ?? []).map((item) => item.template_stage_key).join(",")} onChange={(event) => updateStage(index, { prerequisites: prerequisitesFromText(event.target.value) })} />
                                    </label>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
                <div className="flex gap-3">
                    <Button onClick={() => { void handleSubmit(); }}>{editingTemplateId ? "保存模板" : "创建模板"}</Button>
                    {editingTemplateId && <Button variant="outline" onClick={() => { setEditingTemplateId(null); setForm(EMPTY_FORM); }}>取消编辑</Button>}
                </div>
            </GlassCard>

            <GlassCard className="space-y-4 p-6">
                <div className="flex items-center justify-between">
                    <h2 className="text-xl font-black text-slate-900">模板列表</h2>
                    <Badge variant="gray">{items.length} templates</Badge>
                </div>
                <div className="grid gap-3">
                    {items.map((item) => (
                        <div key={item.template_id} className="rounded-2xl border border-slate-100 bg-white/80 p-4">
                            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                                <div>
                                    <div className="flex flex-wrap items-center gap-2">
                                        <h3 className="font-bold text-slate-900">{item.name}</h3>
                                        <Badge variant={statusVariant(item.status)}>{item.status} · v{item.version}</Badge>
                                    </div>
                                    <p className="mt-1 text-sm text-slate-600">{item.mode} · {item.scenario_type}</p>
                                    <p className="mt-1 text-xs text-slate-500">
                                        agent: {item.agent_id} · persona: {item.persona_id} · runtime: {item.runtime_profile_id}
                                    </p>
                                    {item.description ? <p className="mt-2 text-sm text-slate-600">{item.description}</p> : null}
                                </div>
                                <div className="flex gap-2">
                                    {item.status === "draft" ? (
                                        <Button variant="outline" onClick={() => { handleEdit(item); }}>编辑模板</Button>
                                    ) : (
                                        <span className="self-center text-xs text-slate-500">仅 draft 模板可编辑</span>
                                    )}
                                    <Button
                                        onClick={() => { void handlePublish(item); }}
                                        disabled={item.status === "published" || busyTemplateId !== null}
                                    >
                                        {busyTemplateId === item.template_id ? "发布中..." : "发布模板"}
                                    </Button>
                                    {item.status !== "archived" && (
                                        <Button
                                            variant="outline"
                                            onClick={() => { void handleArchive(item); }}
                                            disabled={busyTemplateId !== null}
                                        >
                                            {busyTemplateId === item.template_id ? "归档中..." : "归档模板"}
                                        </Button>
                                    )}
                                </div>
                            </div>
                        </div>
                    ))}
                    {items.length === 0 && <p className="text-sm text-slate-500">暂无课程训练模板。</p>}
                </div>
            </GlassCard>
        </div>
    );
}
