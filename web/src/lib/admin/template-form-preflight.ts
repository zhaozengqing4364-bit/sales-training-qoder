import type { AssetRefPickerOption } from "@/components/admin/asset-ref-picker";
import type { AdminKnowledgeBase } from "@/lib/api/types";

export interface TemplatePreflightContext {
    agentOptions: AssetRefPickerOption[];
    personaOptions: AssetRefPickerOption[];
    runtimeOptions: AssetRefPickerOption[];
    scoringOptions: AssetRefPickerOption[];
    knowledgeBases: AdminKnowledgeBase[];
}

export interface TemplateFormPreflightInput {
    name: string;
    agent_id: string;
    persona_id: string;
    runtime_profile_id: string;
    scoring_ruleset_id: string;
    knowledge_base_refs: string[];
    voice_mode: string;
    case_item_id?: string | null;
    role_profile_id?: string | null;
}

export interface TemplateFormPreflightResult {
    errors: string[];
    fieldErrors: Record<string, string>;
}

export function validateTemplateFormPreflight(
    form: TemplateFormPreflightInput,
    context: TemplatePreflightContext & {
        caseOptions?: AssetRefPickerOption[];
        roleOptions?: AssetRefPickerOption[];
    },
): TemplateFormPreflightResult {
    const errors: string[] = [];
    const fieldErrors: Record<string, string> = {};
    const pushFieldError = (field: string, message: string) => {
        errors.push(message);
        if (!fieldErrors[field]) fieldErrors[field] = message;
    };

    if (!form.name.trim()) {
        pushFieldError("name", "模板名称必填。");
    }
    if (!form.agent_id.trim()) {
        pushFieldError("agent_id", "请选择智能体。");
    } else {
        const agent = context.agentOptions.find((item) => item.id === form.agent_id);
        if (!agent) pushFieldError("agent_id", "所选智能体不存在，请重新选择。");
        else if (!agent.selectable) pushFieldError("agent_id", "所选智能体尚未发布，请先发布后再保存。");
    }
    if (!form.persona_id.trim()) {
        pushFieldError("persona_id", "请选择 Persona 角色。");
    } else {
        const persona = context.personaOptions.find((item) => item.id === form.persona_id);
        if (!persona) pushFieldError("persona_id", "所选 Persona 不存在，请重新选择。");
        else if (!persona.selectable) pushFieldError("persona_id", "所选 Persona 未启用，请先在角色管理中启用。");
    }
    if (!form.runtime_profile_id.trim()) {
        pushFieldError("runtime_profile_id", "请选择语音运行时配置。");
    } else {
        const runtime = context.runtimeOptions.find((item) => item.id === form.runtime_profile_id);
        if (!runtime) pushFieldError("runtime_profile_id", "所选语音运行时配置不存在，请重新选择。");
        else if (!runtime.selectable) pushFieldError("runtime_profile_id", "所选语音运行时配置未启用，请先启用后再保存。");
    }
    if (!form.scoring_ruleset_id.trim()) {
        pushFieldError("scoring_ruleset_id", "请选择评分规则集。");
    } else {
        const scoring = context.scoringOptions.find((item) => item.id === form.scoring_ruleset_id);
        if (!scoring) pushFieldError("scoring_ruleset_id", "所选评分规则集不存在，请重新选择。");
        else if (!scoring.selectable) pushFieldError("scoring_ruleset_id", "所选评分规则集尚未发布，请先发布后再保存。");
    }
    if (form.voice_mode !== "stepfun_realtime") {
        pushFieldError("voice_mode", "课程模板仅支持 stepfun_realtime 语音模式。");
    }
    for (const kbId of form.knowledge_base_refs) {
        const kb = context.knowledgeBases.find((item) => item.id === kbId);
        if (!kb) {
            pushFieldError("knowledge_base_refs", `知识库 ${kbId} 不存在，请从列表重新选择。`);
            continue;
        }
        if (kb.status !== "active" && kb.status !== "published") {
            pushFieldError("knowledge_base_refs", `知识库「${kb.name}」尚未就绪，请先发布文档后再引用。`);
        }
    }
    if (form.case_item_id?.trim()) {
        const caseItem = context.caseOptions?.find((item) => item.id === form.case_item_id);
        if (!caseItem) pushFieldError("case_item_id", "所选训练案例不存在，请重新选择。");
        else if (!caseItem.selectable) pushFieldError("case_item_id", "所选训练案例尚未发布，请先发布后再保存。");
    }
    if (form.role_profile_id?.trim()) {
        const roleProfile = context.roleOptions?.find((item) => item.id === form.role_profile_id);
        if (!roleProfile) pushFieldError("role_profile_id", "所选客户角色不存在，请重新选择。");
        else if (!roleProfile.selectable) pushFieldError("role_profile_id", "所选客户角色尚未发布，请先发布后再保存。");
    }
    return { errors, fieldErrors };
}
