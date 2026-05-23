import type {
    CaseItemMutationRequest,
    CaseItemRecord,
    RoleProfileMutationRequest,
    RoleProfileRecord,
} from "@/lib/api/types";

export type ContentAssetType = "case-item" | "role-profile";
export type AssetRecord = CaseItemRecord | RoleProfileRecord;

export interface CsvRowError {
    row: number;
    message: string;
}

export interface CsvParseResult {
    caseRows: Array<{ row: number; payload: CaseItemMutationRequest }>;
    roleRows: Array<{ row: number; payload: RoleProfileMutationRequest }>;
    errors: CsvRowError[];
}

export interface CaseItemFormState {
    industry: string;
    company_profile: string;
    customer_role: string;
    pain_points: string;
    objections: string;
    hidden_information: string;
    success_criteria: string;
    allowed_disclosure_phases: string;
    content_hash: string;
}

export interface RoleProfileFormState {
    role_name: string;
    persona_ref: string;
    communication_style: string;
    pressure_level: "low" | "medium" | "high";
    knowledge_boundary: string;
    behavior_rules: string;
    voice_style_hint: string;
    content_hash: string;
    voice_name: string;
    voice_sample_url: string;
    voice_audio_base64: string;
    voice_content_type: string;
}

export const CONTENT_ASSET_META = {
    "case-item": {
        title: "训练案例库",
        description: "管理客户行业、痛点、异议、隐藏信息和披露策略，发布后可绑定到课程训练模板。",
        basePath: "/admin/curriculum-practice/case-items",
    },
    "role-profile": {
        title: "客户角色库",
        description: "管理客户行为画像、可选 Persona 弱关联、压力等级、行为边界和 voice clone 字段。",
        basePath: "/admin/curriculum-practice/role-profiles",
    },
} as const;

export function statusVariant(status: string): "green" | "orange" | "gray" {
    if (status === "published") return "green";
    if (status === "draft") return "orange";
    return "gray";
}

export function formatAssetStatus(status: string): string {
    switch (status) {
        case "draft": return "草稿";
        case "published": return "已发布";
        case "archived": return "已归档";
        default: return status;
    }
}

export function refsFromText(value: string): string[] {
    return value.split(",").map((item) => item.trim()).filter(Boolean);
}

export function listFromCsvCell(value: string): string[] {
    return value.split(/[;|]/).map((item) => item.trim()).filter(Boolean);
}

export function emptyCaseItemForm(): CaseItemFormState {
    return {
        industry: "",
        company_profile: "",
        customer_role: "",
        pain_points: "",
        objections: "",
        hidden_information: "",
        success_criteria: "",
        allowed_disclosure_phases: "discovery,proposal",
        content_hash: "",
    };
}

export function emptyRoleProfileForm(): RoleProfileFormState {
    return {
        role_name: "",
        persona_ref: "",
        communication_style: "",
        pressure_level: "medium",
        knowledge_boundary: "",
        behavior_rules: "",
        voice_style_hint: "",
        content_hash: "",
        voice_name: "",
        voice_sample_url: "",
        voice_audio_base64: "",
        voice_content_type: "audio/wav",
    };
}

export function casePayload(form: CaseItemFormState): CaseItemMutationRequest {
    return {
        industry: form.industry,
        company_profile: form.company_profile,
        customer_role: form.customer_role,
        pain_points: refsFromText(form.pain_points),
        objections: refsFromText(form.objections),
        hidden_information: form.hidden_information,
        success_criteria: refsFromText(form.success_criteria),
        allowed_disclosure_policy: { phases: refsFromText(form.allowed_disclosure_phases) },
        content_hash: form.content_hash,
    };
}

export function rolePayload(form: RoleProfileFormState): RoleProfileMutationRequest {
    return {
        role_type: "customer",
        role_name: form.role_name,
        persona_ref: form.persona_ref.trim() || null,
        communication_style: form.communication_style,
        pressure_level: form.pressure_level,
        knowledge_boundary: refsFromText(form.knowledge_boundary),
        behavior_rules: refsFromText(form.behavior_rules),
        voice_style_hint: form.voice_style_hint,
        content_hash: form.content_hash,
    };
}

export function parseCsvRows(csvText: string, isCase: boolean): CsvParseResult {
    const result: CsvParseResult = { caseRows: [], roleRows: [], errors: [] };
    csvText.split(/\r?\n/).forEach((line, index) => {
        if (!line.trim()) return;
        const row = index + 1;
        const cells = line.split(",").map((cell) => cell.trim());
        if (isCase) {
            if (cells.length < 8 || cells.slice(0, 8).some((cell) => cell.length === 0)) {
                result.errors.push({
                    row,
                    message: "CaseItem 需要 8 列：industry,company_profile,customer_role,pain_points,objections,hidden_information,success_criteria,content_hash。",
                });
                return;
            }
            result.caseRows.push({
                row,
                payload: {
                    industry: cells[0],
                    company_profile: cells[1],
                    customer_role: cells[2],
                    pain_points: listFromCsvCell(cells[3]),
                    objections: listFromCsvCell(cells[4]),
                    hidden_information: cells[5],
                    success_criteria: listFromCsvCell(cells[6]),
                    allowed_disclosure_policy: { phases: ["discovery"] },
                    content_hash: cells[7],
                },
            });
            return;
        }

        if (cells.length < 7 || cells.slice(0, 7).some((cell) => cell.length === 0)) {
            result.errors.push({
                row,
                message: "RoleProfile 需要 7 列：role_name,communication_style,pressure_level,knowledge_boundary,behavior_rules,voice_style_hint,content_hash。",
            });
            return;
        }
        const pressureLevel = cells[2];
        if (pressureLevel !== "low" && pressureLevel !== "medium" && pressureLevel !== "high") {
            result.errors.push({ row, message: "pressure_level 必须是 low、medium 或 high。" });
            return;
        }
        result.roleRows.push({
            row,
            payload: {
                role_type: "customer",
                role_name: cells[0],
                communication_style: cells[1],
                pressure_level: pressureLevel,
                knowledge_boundary: listFromCsvCell(cells[3]),
                behavior_rules: listFromCsvCell(cells[4]),
                voice_style_hint: cells[5],
                content_hash: cells[6],
            },
        });
    });
    return result;
}

export function caseFormFromRecord(item: CaseItemRecord): CaseItemFormState {
    const phases = Array.isArray(item.allowed_disclosure_policy.phases)
        ? item.allowed_disclosure_policy.phases.map(String)
        : [];
    return {
        industry: item.industry,
        company_profile: item.company_profile,
        customer_role: item.customer_role,
        pain_points: item.pain_points.join(","),
        objections: item.objections.join(","),
        hidden_information: item.hidden_information,
        success_criteria: item.success_criteria.join(","),
        allowed_disclosure_phases: phases.join(","),
        content_hash: item.content_hash,
    };
}

export function roleFormFromRecord(item: RoleProfileRecord): RoleProfileFormState {
    return {
        role_name: item.role_name,
        persona_ref: item.persona_ref ?? "",
        communication_style: item.communication_style,
        pressure_level: item.pressure_level,
        knowledge_boundary: item.knowledge_boundary.join(","),
        behavior_rules: item.behavior_rules.join(","),
        voice_style_hint: item.voice_style_hint,
        content_hash: item.content_hash,
        voice_name: item.voice_id ?? "",
        voice_sample_url: item.voice_sample_url ?? "",
        voice_audio_base64: "",
        voice_content_type: "audio/wav",
    };
}

export function recordStatus(item: AssetRecord): string {
    return `${formatAssetStatus(item.status)} · v${item.version}`;
}

export function isCaseItem(item: AssetRecord): item is CaseItemRecord {
    return "case_item_id" in item;
}

export function recordId(item: AssetRecord): string {
    return isCaseItem(item) ? item.case_item_id : item.role_profile_id;
}

export function recordTitle(item: AssetRecord): string {
    return isCaseItem(item) ? `${item.industry} · ${item.customer_role}` : item.role_name;
}

export function recordSubtitle(item: AssetRecord): string {
    return isCaseItem(item)
        ? `痛点 ${item.pain_points.length} · 异议 ${item.objections.length}`
        : `${item.role_type} · 压力等级 ${item.pressure_level} · 角色画像 ${item.persona_ref ?? "未绑定"}`;
}

export async function validateRoleProfilePersonaRef(
    getPersona: (id: string) => Promise<{ status: string }>,
    personaRef: string,
): Promise<string | null> {
    const trimmed = personaRef.trim();
    if (!trimmed) return null;
    try {
        const persona = await getPersona(trimmed);
        if (persona.status !== "active") {
            return "所选 Persona 未启用，请先在角色管理中启用。";
        }
        return null;
    } catch {
        return "所选 Persona 不存在，请重新选择。";
    }
}
