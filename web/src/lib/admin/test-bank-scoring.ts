export function parseScoringCriteria(raw: string): Record<string, unknown> | null {
    const trimmed = raw.trim();
    if (!trimmed) return {};
    try {
        const parsed = JSON.parse(trimmed);
        if (typeof parsed !== "object" || Array.isArray(parsed) || parsed === null) {
            return null;
        }
        return parsed as Record<string, unknown>;
    } catch {
        return null;
    }
}

export function listFromLines(value: string): string[] {
    return value.split(/\r?\n/).map((item) => item.trim()).filter(Boolean);
}

export function linesFromList(items: string[]): string {
    return items.join("\n");
}

export function getScoringCriteriaValidation(raw: string): { ok: boolean; message: string } {
    const trimmed = raw.trim();
    if (!trimmed) {
        return { ok: true, message: "未填写评分标准，将按空对象提交。" };
    }
    const parsed = parseScoringCriteria(raw);
    if (parsed === null) {
        return { ok: false, message: '评分标准格式无效，请输入 JSON 对象，例如 {"dimensions":["clarity"]}。' };
    }
    return { ok: true, message: "评分标准 JSON 对象格式有效。" };
}
