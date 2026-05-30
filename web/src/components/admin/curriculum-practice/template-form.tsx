"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { AdminAssetRefPicker, type AssetRefPickerOption } from "@/components/admin/asset-ref-picker";
import { AdminContextBar } from "@/components/admin/admin-layout-shells";
import { AdminKbMultiRefPicker } from "@/components/admin/kb-multi-ref-picker";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { api, getApiErrorMessage, getPracticeTemplateErrorDetails } from "@/lib/api/client";
import { validateTemplateFormPreflight } from "@/lib/admin/template-form-preflight";
import type {
    AdminAgent,
    AdminKnowledgeBase,
    AdminPersona,
    AdminVoiceRuntimeProfile,
    CaseItemRecord,
    CurriculumPlanStage,
    PracticeTemplateGateResult,
    PracticeTemplateMutationRequest,
    PracticeTemplateRecord,
    RoleplaySituationPack,
    RoleProfileRecord,
    ScoringRulesetRecord,
} from "@/lib/api/types";
import { debug } from "@/lib/debug";

type FormState = Omit<Required<PracticeTemplateMutationRequest>, "curriculum_plan" | "max_stage_duration_seconds"> & {
    curriculum_plan: PracticeTemplateMutationRequest["curriculum_plan"];
    max_stage_duration_seconds: number | null;
};

type TemplateBindingRefs = {
    case_item_id: string | null;
    role_profile_id: string | null;
};

function bindingRefsFromForm(form: FormState): TemplateBindingRefs {
    return {
        case_item_id: form.case_item_id ?? null,
        role_profile_id: form.role_profile_id ?? null,
    };
}

function bindingRefsFromTemplate(template: PracticeTemplateRecord): TemplateBindingRefs {
    return {
        case_item_id: template.case_item_id ?? null,
        role_profile_id: template.role_profile_id ?? null,
    };
}

function refsChanged(initial: TemplateBindingRefs, current: TemplateBindingRefs): boolean {
    return initial.case_item_id !== current.case_item_id
        || initial.role_profile_id !== current.role_profile_id;
}

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

function createDefaultCurriculumPlan(): NonNullable<FormState["curriculum_plan"]> {
    return {
        name: "",
        description: "",
        max_stage_duration_seconds: 600,
        stages: [emptyStage(1)],
    };
}

function createEmptyForm(): FormState {
    return {
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
        case_item_id: null,
        role_profile_id: null,
        situation_pack_code: null,
        curriculum_plan: null,
        max_stage_duration_seconds: null,
    };
}

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
        knowledge_base_refs: [...template.knowledge_base_refs],
        case_item_id: template.case_item_id ?? null,
        role_profile_id: template.role_profile_id ?? null,
        situation_pack_code: template.situation_pack_code ?? null,
        curriculum_plan: template.curriculum_plan ?? null,
        max_stage_duration_seconds: template.max_stage_duration_seconds ?? null,
    };
}

function refsFromText(value: string): string[] {
    return value.split(/[，,\n]/).map((item) => item.trim()).filter(Boolean);
}

function refsToText(values: string[]): string {
    return values.join("\n");
}

function agentOptions(agents: AdminAgent[]): AssetRefPickerOption[] {
    return agents.map((agent) => ({
        id: agent.id,
        label: agent.name,
        subtitle: agent.category,
        status: agent.status,
        editHref: `/admin/agents/${agent.id}`,
        selectable: agent.status === "published",
    }));
}

function personaOptions(personas: AdminPersona[]): AssetRefPickerOption[] {
    return personas.map((persona) => ({
        id: persona.id,
        label: persona.name,
        subtitle: persona.category,
        status: persona.status === "active" ? "启用中" : "已停用",
        editHref: `/admin/personas/${persona.id}`,
        selectable: persona.status === "active",
    }));
}

function runtimeOptions(profiles: AdminVoiceRuntimeProfile[]): AssetRefPickerOption[] {
    return profiles.map((profile) => ({
        id: profile.id,
        label: profile.name,
        subtitle: profile.voice_mode,
        status: profile.is_active ? "已启用" : "未启用",
        editHref: "/admin/voice-runtime",
        selectable: profile.is_active,
    }));
}

function scoringOptions(rulesets: ScoringRulesetRecord[]): AssetRefPickerOption[] {
    return rulesets
        .filter((item) => item.ruleset_id)
        .map((ruleset) => ({
            id: ruleset.ruleset_id as string,
            label: ruleset.display_name,
            subtitle: ruleset.version,
            status: ruleset.status,
            editHref: "/admin/scoring-rulesets",
            selectable: ruleset.status === "published",
        }));
}

function caseItemOptions(items: CaseItemRecord[]): AssetRefPickerOption[] {
    return items.map((item) => ({
        id: item.case_item_id,
        label: `${item.industry} · ${item.customer_role}`,
        subtitle: item.company_profile,
        status: item.status,
        editHref: "/admin/curriculum-practice/case-items",
        selectable: item.status === "published",
    }));
}

function roleProfileOptions(items: RoleProfileRecord[]): AssetRefPickerOption[] {
    return items.map((item) => ({
        id: item.role_profile_id,
        label: item.role_name,
        subtitle: item.pressure_level,
        status: item.status,
        editHref: "/admin/curriculum-practice/role-profiles",
        selectable: item.status === "published",
    }));
}

function situationPackOptions(
    items: RoleplaySituationPack[],
    context: { mode: string; scenarioType: string },
): AssetRefPickerOption[] {
    return items.map((item) => {
        const modeCompatible = item.compatible_practice_modes.length === 0
            || item.compatible_practice_modes.includes(context.mode);
        const scenarioCompatible = item.compatible_scenario_types.length === 0
            || item.compatible_scenario_types.includes(context.scenarioType);
        const selectable = item.status === "published" && modeCompatible && scenarioCompatible;
        return {
            id: item.code,
            label: item.label || item.code,
            subtitle: item.code,
            status: item.status,
            editHref: "/admin/curriculum-practice/roleplay-situation-packs",
            selectable,
        };
    });
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
export interface TemplateFormProps {
    mode: "create" | "edit";
    templateId?: string;
    initialTemplate?: PracticeTemplateRecord;
    onSaved: (template: PracticeTemplateRecord) => void;
    onCancel: () => void;
}

export function TemplateForm({ mode, templateId, initialTemplate, onSaved, onCancel }: TemplateFormProps) {
    const [form, setForm] = useState<FormState>(() => (
        initialTemplate ? formFromTemplate(initialTemplate) : createEmptyForm()
    ));
    const [caseItems, setCaseItems] = useState<CaseItemRecord[]>([]);
    const [roleProfiles, setRoleProfiles] = useState<RoleProfileRecord[]>([]);
    const [agents, setAgents] = useState<AdminAgent[]>([]);
    const [personas, setPersonas] = useState<AdminPersona[]>([]);
    const [runtimeProfiles, setRuntimeProfiles] = useState<AdminVoiceRuntimeProfile[]>([]);
    const [scoringRulesets, setScoringRulesets] = useState<ScoringRulesetRecord[]>([]);
    const [situationPacks, setSituationPacks] = useState<RoleplaySituationPack[]>([]);
    const [knowledgeBases, setKnowledgeBases] = useState<AdminKnowledgeBase[]>([]);
    const [pickerLoading, setPickerLoading] = useState(true);
    const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
    const [actionError, setActionError] = useState<string | null>(null);
    const [gateResults, setGateResults] = useState<PracticeTemplateGateResult[]>([]);
    const [submitting, setSubmitting] = useState(false);
    const [initialRefs, setInitialRefs] = useState<TemplateBindingRefs>(() => (
        initialTemplate ? bindingRefsFromTemplate(initialTemplate) : { case_item_id: null, role_profile_id: null }
    ));

    const bindingRefsChanged = useMemo(() => {
        if (initialTemplate?.status === "archived") return false;
        return refsChanged(initialRefs, bindingRefsFromForm(form));
    }, [form, initialRefs, initialTemplate?.status]);

    const agentPickerOptions = useMemo(() => agentOptions(agents), [agents]);
    const personaPickerOptions = useMemo(() => personaOptions(personas), [personas]);
    const runtimePickerOptions = useMemo(() => runtimeOptions(runtimeProfiles), [runtimeProfiles]);
    const scoringPickerOptions = useMemo(() => scoringOptions(scoringRulesets), [scoringRulesets]);
    const situationPackPickerOptions = useMemo(() => situationPackOptions(
        situationPacks,
        { mode: form.mode, scenarioType: form.scenario_type },
    ), [form.mode, form.scenario_type, situationPacks]);
    const casePickerOptions = useMemo(() => caseItemOptions(caseItems), [caseItems]);
    const rolePickerOptions = useMemo(() => roleProfileOptions(roleProfiles), [roleProfiles]);

    const loadPickers = useCallback(async () => {
        setPickerLoading(true);
        try {
            const [
                caseItemResponse,
                roleProfileResponse,
                agentResponse,
                personaResponse,
                runtimeResponse,
                scoringResponse,
                situationPackResponse,
                knowledgeResponse,
            ] = await Promise.all([
                api.admin.listCaseItems(),
                api.admin.listRoleProfiles(),
                api.admin.getAgents({ page_size: 200 }),
                api.admin.getPersonas({ page_size: 200 }),
                api.admin.getVoiceRuntimeProfiles(),
                api.admin.listScoringRulesets("sales"),
                api.admin.listRoleplaySituationPacks(),
                api.admin.getKnowledgeBases({ page: 1, page_size: 200 }),
            ]);
            setCaseItems(caseItemResponse.items);
            setRoleProfiles(roleProfileResponse.items);
            setAgents(agentResponse.items);
            setPersonas(personaResponse.items);
            setRuntimeProfiles(runtimeResponse.items);
            setScoringRulesets(scoringResponse.items);
            setSituationPacks(situationPackResponse.items);
            setKnowledgeBases(knowledgeResponse.items);
        } catch (err) {
            setActionError(`加载引用资产失败：${getApiErrorMessage(err)}`);
        } finally {
            setPickerLoading(false);
        }
    }, []);

    useEffect(() => {
        void loadPickers();
    }, [loadPickers]);

    useEffect(() => {
        if (initialTemplate) {
            setForm(formFromTemplate(initialTemplate));
            setInitialRefs(bindingRefsFromTemplate(initialTemplate));
        }
    }, [initialTemplate]);

    const handleSubmit = async () => {
        setActionError(null);
        setGateResults([]);
        setFieldErrors({});
        const preflight = validateTemplateFormPreflight(form, {
            agentOptions: agentPickerOptions,
            personaOptions: personaPickerOptions,
            runtimeOptions: runtimePickerOptions,
            scoringOptions: scoringPickerOptions,
            situationPackOptions: situationPackPickerOptions,
            knowledgeBases,
            caseOptions: casePickerOptions,
            roleOptions: rolePickerOptions,
        });
        if (preflight.errors.length > 0) {
            setFieldErrors(preflight.fieldErrors);
            setActionError(`保存前预检未通过：${preflight.errors.join(" ")}`);
            return;
        }
        const payload: PracticeTemplateMutationRequest = form.curriculum_plan
            ? form
            : { ...form, curriculum_plan: null, max_stage_duration_seconds: null };
        setSubmitting(true);
        try {
            if (mode === "edit" && templateId) {
                const updated = await api.admin.updatePracticeTemplate(templateId, payload);
                onSaved(updated);
                return;
            }
            const created = await api.admin.createPracticeTemplate(payload as Required<PracticeTemplateMutationRequest>);
            onSaved(created);
        } catch (err) {
            setGateResults(getPracticeTemplateErrorDetails(err)?.gate_results ?? []);
            setActionError(`保存失败：${getApiErrorMessage(err)}`);
            debug.warn("[TemplateForm] failed to save template", { error: err });
        } finally {
            setSubmitting(false);
        }
    };

    const updateCurriculumPlan = (patch: Partial<NonNullable<FormState["curriculum_plan"]>>) => {
        setForm((current) => ({
            ...current,
            curriculum_plan: {
                ...(current.curriculum_plan ?? createDefaultCurriculumPlan()),
                ...patch,
            },
        }));
    };

    const updateStage = (stageIndex: number, patch: Partial<CurriculumPlanStage>) => {
        setForm((current) => {
            const curriculumPlan = current.curriculum_plan ?? createDefaultCurriculumPlan();
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
            const curriculumPlan = current.curriculum_plan ?? createDefaultCurriculumPlan();
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
            const curriculumPlan = current.curriculum_plan ?? createDefaultCurriculumPlan();
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
            const curriculumPlan = current.curriculum_plan ?? createDefaultCurriculumPlan();
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
            const curriculumPlan = current.curriculum_plan ?? createDefaultCurriculumPlan();
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

    return (
        <GlassCard className="space-y-4 p-6">
            <h2 className="text-xl font-black text-slate-900">{mode === "edit" ? "编辑模板" : "创建模板"}</h2>
            {bindingRefsChanged ? (
                <AdminContextBar>
                    <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                        引用资产已变更。保存草稿后，需重新发布模板，学员端才会使用新绑定；已发布版本仍指向旧资产直至重发。
                    </div>
                </AdminContextBar>
            ) : null}
            {actionError && (
                <div className="space-y-2 rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
                    <p>{actionError}</p>
                    {gateResults.length > 0 && (
                        <ul className="list-disc space-y-1 pl-5">
                            {gateResults.map((result) => (
                                <li key={`${result.gate_name}-${result.reason_code}-${result.message}`}>
                                    <span className="font-semibold">{result.reason_code}</span>：{result.message}
                                </li>
                            ))}
                        </ul>
                    )}
                </div>
            )}
                <div className="grid gap-4 md:grid-cols-2">
                    <label className="space-y-1 text-sm font-medium text-slate-700">
                        <span>模板名称</span>
                        <input className="w-full rounded-xl border border-slate-200 px-3 py-2" value={form.name} onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))} />
                    </label>
                    <label className="space-y-1 text-sm font-medium text-slate-700">
                        <span>描述</span>
                        <input className="w-full rounded-xl border border-slate-200 px-3 py-2" value={form.description ?? ""} onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))} />
                    </label>
                    <AdminAssetRefPicker
                        label="智能体"
                        value={form.agent_id}
                        onChange={(agentId) => setForm((current) => ({ ...current, agent_id: agentId }))}
                        options={agentPickerOptions}
                        loading={pickerLoading}
                        placeholder="搜索智能体…"
                        error={fieldErrors.agent_id}
                    />
                    <AdminAssetRefPicker
                        label="Persona 角色"
                        value={form.persona_id}
                        onChange={(personaId) => setForm((current) => ({ ...current, persona_id: personaId }))}
                        options={personaPickerOptions}
                        loading={pickerLoading}
                        placeholder="搜索 Persona…"
                        error={fieldErrors.persona_id}
                    />
                    <AdminAssetRefPicker
                        label="Situation Pack"
                        value={form.situation_pack_code ?? ""}
                        onChange={(code) => setForm((current) => ({ ...current, situation_pack_code: code || null }))}
                        options={situationPackPickerOptions}
                        loading={pickerLoading}
                        placeholder="搜索 Situation Pack…"
                        emptyMessage="暂无已发布且兼容的 Situation Pack"
                        error={fieldErrors.situation_pack_code}
                    />
                    <AdminAssetRefPicker
                        label="语音运行时配置"
                        value={form.runtime_profile_id}
                        onChange={(runtimeId) => setForm((current) => ({ ...current, runtime_profile_id: runtimeId }))}
                        options={runtimePickerOptions}
                        loading={pickerLoading}
                        placeholder="搜索语音配置…"
                        error={fieldErrors.runtime_profile_id}
                    />
                    <AdminAssetRefPicker
                        label="评分规则集"
                        value={form.scoring_ruleset_id}
                        onChange={(rulesetId) => setForm((current) => ({ ...current, scoring_ruleset_id: rulesetId }))}
                        options={scoringPickerOptions}
                        loading={pickerLoading}
                        placeholder="搜索评分规则集…"
                        error={fieldErrors.scoring_ruleset_id}
                    />
                    <AdminKbMultiRefPicker
                        label="知识库引用"
                        value={form.knowledge_base_refs}
                        onChange={(refs) => setForm((current) => ({ ...current, knowledge_base_refs: refs }))}
                        error={fieldErrors.knowledge_base_refs}
                    />
                    <AdminAssetRefPicker
                        label="训练案例（可选）"
                        value={form.case_item_id ?? ""}
                        onChange={(caseId) => setForm((current) => ({ ...current, case_item_id: caseId || null }))}
                        options={casePickerOptions}
                        loading={pickerLoading}
                        placeholder="搜索训练案例…"
                        emptyMessage="暂无训练案例"
                        error={fieldErrors.case_item_id}
                    />
                    <AdminAssetRefPicker
                        label="客户角色库（可选）"
                        value={form.role_profile_id ?? ""}
                        onChange={(roleId) => setForm((current) => ({ ...current, role_profile_id: roleId || null }))}
                        options={rolePickerOptions}
                        loading={pickerLoading}
                        placeholder="搜索客户角色…"
                        emptyMessage="暂无客户角色"
                        error={fieldErrors.role_profile_id}
                    />
                    <p className="md:col-span-2 text-xs text-slate-500">
                        草稿资产会灰显并附带
                        {" "}
                        <Link href="/admin/curriculum-practice/case-items" className="font-medium text-amber-700 hover:text-amber-900">去发布</Link>
                        {" "}
                        链接；保存前预检会校验必选引用是否已发布/启用。
                    </p>
                </div>

                <div className="space-y-4 rounded-2xl border border-slate-100 bg-slate-50/70 p-4">
                    <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                        <div>
                            <h3 className="text-lg font-black text-slate-900">CurriculumPlan</h3>
                            <p className="text-xs text-slate-500">配置多阶段模板图、完成策略和失败策略。</p>
                        </div>
                        {form.curriculum_plan ? (
                            <Button variant="outline" onClick={addStage}>添加 Stage</Button>
                        ) : (
                            <Button variant="outline" onClick={() => { setForm((current) => ({ ...current, curriculum_plan: createDefaultCurriculumPlan(), max_stage_duration_seconds: 600 })); }}>启用 CurriculumPlan</Button>
                        )}
                    </div>
                    {form.curriculum_plan ? (
                        <>
                            <div className="grid gap-4 md:grid-cols-2">
                                <label className="space-y-1 text-sm font-medium text-slate-700">
                                    <span>CurriculumPlan Name</span>
                                    <input className="w-full rounded-xl border border-slate-200 px-3 py-2" value={form.curriculum_plan.name} onChange={(event) => updateCurriculumPlan({ name: event.target.value })} />
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
                                {form.curriculum_plan.stages.map((stage, index) => (
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
                                        <textarea
                                            className="min-h-20 w-full rounded-xl border border-slate-200 px-3 py-2"
                                            value={refsToText((stage.prerequisites ?? []).map((item) => item.template_stage_key))}
                                            onChange={(event) => updateStage(index, { prerequisites: prerequisitesFromText(event.target.value) })}
                                            placeholder="每行一个前置 Stage Key，也兼容逗号粘贴"
                                        />
                                    </label>
                                </div>
                            </div>
                                ))}
                            </div>
                        </>
                    ) : (
                        <p className="rounded-xl border border-dashed border-slate-200 bg-white/70 p-3 text-sm text-slate-500">未启用 CurriculumPlan；普通模板保存时不会提交默认阶段配置。</p>
                    )}
                </div>
            <div className="flex gap-3">
                <Button onClick={() => { void handleSubmit(); }} disabled={submitting}>
                    {submitting ? "保存中..." : mode === "edit" ? "保存模板" : "创建模板"}
                </Button>
                <Button variant="outline" onClick={onCancel}>取消</Button>
            </div>
        </GlassCard>
    );
}
