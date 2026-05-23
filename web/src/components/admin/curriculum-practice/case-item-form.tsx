"use client";

import type { CaseItemFormState } from "./content-asset-utils";

function TextField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
    return (
        <label className="space-y-1 text-sm font-medium text-slate-700">
            <span>{label}</span>
            <input
                className="w-full rounded-xl border border-slate-200 px-3 py-2"
                value={value}
                onChange={(event) => onChange(event.target.value)}
            />
        </label>
    );
}

function TextAreaField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
    return (
        <label className="space-y-1 text-sm font-medium text-slate-700 md:col-span-2">
            <span>{label}</span>
            <textarea
                className="min-h-24 w-full rounded-xl border border-slate-200 px-3 py-2"
                value={value}
                onChange={(event) => onChange(event.target.value)}
            />
        </label>
    );
}

export interface CaseItemFormProps {
    form: CaseItemFormState;
    onChange: (next: CaseItemFormState) => void;
}

export function CaseItemForm({ form, onChange }: CaseItemFormProps) {
    const update = (patch: Partial<CaseItemFormState>) => onChange({ ...form, ...patch });
    return (
        <div className="grid gap-4 md:grid-cols-2">
            <TextField label="行业" value={form.industry} onChange={(value) => update({ industry: value })} />
            <TextField
                label="案例内客户描述（文本剧本，非角色库）"
                value={form.customer_role}
                onChange={(value) => update({ customer_role: value })}
            />
            <TextAreaField label="公司画像" value={form.company_profile} onChange={(value) => update({ company_profile: value })} />
            <TextAreaField label="隐藏信息" value={form.hidden_information} onChange={(value) => update({ hidden_information: value })} />
            <TextField label="痛点（逗号分隔）" value={form.pain_points} onChange={(value) => update({ pain_points: value })} />
            <TextField label="异议（逗号分隔）" value={form.objections} onChange={(value) => update({ objections: value })} />
            <TextField label="成功标准（逗号分隔）" value={form.success_criteria} onChange={(value) => update({ success_criteria: value })} />
            <TextField label="允许披露阶段（逗号分隔）" value={form.allowed_disclosure_phases} onChange={(value) => update({ allowed_disclosure_phases: value })} />
            <TextField label="Content Hash" value={form.content_hash} onChange={(value) => update({ content_hash: value })} />
        </div>
    );
}
