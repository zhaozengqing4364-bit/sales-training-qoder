"use client";

import { PersonaRefPicker } from "@/components/admin/persona-ref-picker";

import type { RoleProfileFormState } from "./content-asset-utils";

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

export interface RoleProfileFormProps {
    form: RoleProfileFormState;
    onChange: (next: RoleProfileFormState) => void;
    personaRefError?: string | null;
    onPersonaRefChange?: () => void;
    showVoiceCloneFields?: boolean;
}

export function RoleProfileForm({
    form,
    onChange,
    personaRefError,
    onPersonaRefChange,
    showVoiceCloneFields = false,
}: RoleProfileFormProps) {
    const update = (patch: Partial<RoleProfileFormState>) => onChange({ ...form, ...patch });
    return (
        <div className="grid gap-4 md:grid-cols-2">
            <TextField label="角色名称" value={form.role_name} onChange={(value) => update({ role_name: value })} />
            <PersonaRefPicker
                value={form.persona_ref}
                onChange={(value) => {
                    onPersonaRefChange?.();
                    update({ persona_ref: value });
                }}
                error={personaRefError}
            />
            <label className="space-y-1 text-sm font-medium text-slate-700">
                <span>压力等级</span>
                <select
                    className="w-full rounded-xl border border-slate-200 px-3 py-2"
                    value={form.pressure_level}
                    onChange={(event) => update({ pressure_level: event.target.value as RoleProfileFormState["pressure_level"] })}
                >
                    <option value="low">low</option>
                    <option value="medium">medium</option>
                    <option value="high">high</option>
                </select>
            </label>
            <TextField label="知识边界（逗号分隔）" value={form.knowledge_boundary} onChange={(value) => update({ knowledge_boundary: value })} />
            <TextField label="行为规则（逗号分隔）" value={form.behavior_rules} onChange={(value) => update({ behavior_rules: value })} />
            <TextField label="声音风格提示" value={form.voice_style_hint} onChange={(value) => update({ voice_style_hint: value })} />
            <TextAreaField label="沟通风格" value={form.communication_style} onChange={(value) => update({ communication_style: value })} />
            <TextField label="Content Hash" value={form.content_hash} onChange={(value) => update({ content_hash: value })} />
            {showVoiceCloneFields ? (
                <>
                    <TextField label="声音名称" value={form.voice_name} onChange={(value) => update({ voice_name: value })} />
                    <TextField label="声音样本 URL" value={form.voice_sample_url} onChange={(value) => update({ voice_sample_url: value })} />
                    <TextField label="声音音频 Base64" value={form.voice_audio_base64} onChange={(value) => update({ voice_audio_base64: value })} />
                    <TextField label="声音内容类型" value={form.voice_content_type} onChange={(value) => update({ voice_content_type: value })} />
                </>
            ) : null}
        </div>
    );
}
