import type {
    SalesTrainerUnitQuestionBinding,
    SalesTrainerUnitType,
} from "@/lib/api/types";

interface ValidateUnitFormInput {
    readonly audioPurpose: string;
    readonly canEdit: boolean;
    readonly materialId: string;
    readonly name: string;
    readonly promptId: string;
    readonly selectedQuestions: readonly SalesTrainerUnitQuestionBinding[];
    readonly unitType: SalesTrainerUnitType;
}

export function validateUnitForm(input: ValidateUnitFormInput): string | null {
    if (!input.name.trim()) {
        return "训练单元名称不能为空。";
    }
    if (!input.canEdit) {
        return "已归档训练单元仅用于审计追溯；需要恢复使用时请在历史版本中回滚。";
    }
    if (input.unitType === "quiz" && input.selectedQuestions.length === 0) {
        return "做题训练单元至少需要绑定一道题。";
    }
    if (input.unitType === "audio_scoring" && !input.promptId) {
        return "音频评分训练单元必须绑定录音评分标准。";
    }
    if (input.unitType === "audio_scoring" && !input.audioPurpose.trim()) {
        return "录音用途不能为空。";
    }
    if (input.unitType === "audio_scoring" && input.audioPurpose.trim() === "ppt_pitch" && !input.materialId) {
        return "PPT 演练任务必须绑定已发布训练材料。";
    }
    return null;
}

export function listToText(values: unknown): string {
    return Array.isArray(values) ? values.map((item) => String(item)).join("\n") : "";
}

export function textToList(text: string): string[] {
    return text.split(/[\n,，]/).map((item) => item.trim()).filter(Boolean);
}

export function textToGuidanceTemplates(text: string): Record<string, string> {
    return Object.fromEntries(
        text
            .split("\n")
            .map((line) => {
                const [key, ...rest] = line.split(":");
                return [key?.trim(), rest.join(":").trim()];
            })
            .filter(([key, value]) => key && value),
    );
}

export function parseOptionalNumber(
    value: string,
    label: string,
    options: { readonly min?: number; readonly max?: number; readonly integer?: boolean } = {},
): number | undefined {
    const trimmed = value.trim();
    if (!trimmed) {
        return undefined;
    }
    const parsed = Number(trimmed);
    if (!Number.isFinite(parsed)) {
        throw new Error(`${label}必须是数字。`);
    }
    if (options.integer && !Number.isInteger(parsed)) {
        throw new Error(`${label}必须是整数。`);
    }
    if (options.min !== undefined && parsed < options.min) {
        throw new Error(`${label}不能小于 ${options.min}。`);
    }
    if (options.max !== undefined && parsed > options.max) {
        throw new Error(`${label}不能大于 ${options.max}。`);
    }
    return parsed;
}
