import type { AdminPersonaPolicy } from "@/lib/api/types";
import { ApiRequestError } from "@/lib/api/client";

export interface AdminPersonaRoleAnchorFormState {
    enabled: boolean;
    identityTemplate: string;
    bottomLine: string;
    mustDo: string;
    mustNot: string;
}

export interface PersonaPolicyValidationErrorItem {
    field: string;
    reason_code: string;
    message: string;
}

export type RoleAnchorFieldKey = keyof AdminPersonaRoleAnchorFormState;

const DEFAULT_IDENTITY_TEMPLATE =
    "你是{role_name}，{relationship_stage}。{bottom_line}。";

const ROLE_ANCHOR_FIELD_MAP: Record<string, RoleAnchorFieldKey> = {
    "persona_policy.role_anchor.bottom_line": "bottomLine",
    "persona_policy.role_anchor.identity_template": "identityTemplate",
    "persona_policy.role_anchor.must_do": "mustDo",
    "persona_policy.role_anchor.must_not": "mustNot",
    "persona_policy.role_anchor": "enabled",
};

export const ROLE_ANCHOR_REASON_LABELS: Record<string, string> = {
    role_anchor_bottom_line_required: "底线描述必填，且至少 10 个字符。",
    role_anchor_identity_template_invalid_vars:
        "身份模板仅允许变量 {role_name}、{relationship_stage}、{bottom_line}。",
    role_anchor_must_do_too_long: "must_do 不能超过 200 字符。",
    role_anchor_must_not_too_long: "must_not 不能超过 200 字符。",
    role_anchor_invalid_type: "role_anchor 必须是结构化对象。",
};

export function emptyRoleAnchorFormState(): AdminPersonaRoleAnchorFormState {
    return {
        enabled: false,
        identityTemplate: DEFAULT_IDENTITY_TEMPLATE,
        bottomLine: "",
        mustDo: "",
        mustNot: "",
    };
}

export function buildRoleAnchorFormState(
    personaPolicy?: AdminPersonaPolicy | null,
): AdminPersonaRoleAnchorFormState {
    const roleAnchor = personaPolicy?.role_anchor;
    if (!roleAnchor || typeof roleAnchor !== "object" || Array.isArray(roleAnchor)) {
        return emptyRoleAnchorFormState();
    }

    const record = roleAnchor as Record<string, unknown>;
    const bottomLine = String(record.bottom_line || "").trim();
    const identityTemplate = String(record.identity_template || "").trim();
    const mustDo = String(record.must_do || "").trim();
    const mustNot = String(record.must_not || "").trim();
    const enabled = Boolean(bottomLine || identityTemplate || mustDo || mustNot);

    return {
        enabled,
        identityTemplate: identityTemplate || DEFAULT_IDENTITY_TEMPLATE,
        bottomLine,
        mustDo,
        mustNot,
    };
}

export function buildRoleAnchorPayload(
    form: AdminPersonaRoleAnchorFormState,
): Record<string, string> | undefined {
    if (!form.enabled) {
        return undefined;
    }

    return {
        version: "1",
        identity_template: form.identityTemplate.trim() || DEFAULT_IDENTITY_TEMPLATE,
        bottom_line: form.bottomLine.trim(),
        must_do: form.mustDo.trim(),
        must_not: form.mustNot.trim(),
    };
}

export function mapPersonaPolicyValidationField(field: string): RoleAnchorFieldKey | null {
    return ROLE_ANCHOR_FIELD_MAP[field] ?? null;
}

export function mapPersonaPolicyValidationErrors(
    errors: PersonaPolicyValidationErrorItem[],
): Partial<Record<RoleAnchorFieldKey, string>> {
    const fieldErrors: Partial<Record<RoleAnchorFieldKey, string>> = {};
    for (const item of errors) {
        const key = mapPersonaPolicyValidationField(item.field);
        if (!key || fieldErrors[key]) {
            continue;
        }
        const label = ROLE_ANCHOR_REASON_LABELS[item.reason_code];
        fieldErrors[key] = label ? `${label}（${item.reason_code}）` : item.message;
    }
    return fieldErrors;
}

export function parsePersonaPolicyValidationErrors(
    error: unknown,
): PersonaPolicyValidationErrorItem[] | null {
    if (!(error instanceof ApiRequestError)) {
        return null;
    }
    if (error.errorCode !== "[PERSONA_POLICY_VALIDATION_FAILED]") {
        return null;
    }
    if (!error.details || typeof error.details !== "object" || Array.isArray(error.details)) {
        return null;
    }
    const rawErrors = (error.details as { errors?: unknown }).errors;
    if (!Array.isArray(rawErrors)) {
        return null;
    }

    const parsed: PersonaPolicyValidationErrorItem[] = [];
    for (const item of rawErrors) {
        if (!item || typeof item !== "object") {
            continue;
        }
        const record = item as Record<string, unknown>;
        const field = String(record.field || "").trim();
        const reasonCode = String(record.reason_code || "").trim();
        const message = String(record.message || "").trim();
        if (!field || !reasonCode) {
            continue;
        }
        parsed.push({
            field,
            reason_code: reasonCode,
            message: message || reasonCode,
        });
    }
    return parsed.length > 0 ? parsed : null;
}

export function previewRoleAnchorText(
    form: AdminPersonaRoleAnchorFormState,
    personaName: string,
    relationshipStage = "这是你们首次正式见面",
): string {
    if (!form.enabled) {
        return "";
    }

    const bottomLine = form.bottomLine.trim();
    if (!bottomLine) {
        return "";
    }

    const template = form.identityTemplate.trim() || DEFAULT_IDENTITY_TEMPLATE;
    let identityText = template;
    identityText = identityText.replaceAll("{role_name}", personaName.trim() || "角色");
    identityText = identityText.replaceAll("{relationship_stage}", relationshipStage);
    identityText = identityText.replaceAll("{bottom_line}", bottomLine);

    const parts = [`【角色锚】\n${identityText}`];
    const mustDo = form.mustDo.trim();
    const mustNot = form.mustNot.trim();
    if (mustDo) {
        parts.push(`必须：${mustDo}。`);
    }
    if (mustNot) {
        parts.push(`禁止：${mustNot}。`);
    }
    return parts.join("\n");
}
