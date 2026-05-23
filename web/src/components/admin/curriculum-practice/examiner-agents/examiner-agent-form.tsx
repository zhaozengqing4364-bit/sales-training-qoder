"use client";

import { JsonEditorWithValidation } from "@/components/ui/json-editor-with-validation";

import {
    LEARNER_LEVEL_OPTIONS,
    parseJsonField,
    type ExaminerAgentFormState,
} from "./examiner-agent-utils";

export interface ExaminerAgentFormProps {
    form: ExaminerAgentFormState;
    onChange: (next: ExaminerAgentFormState) => void;
}

export function ExaminerAgentForm({ form, onChange }: ExaminerAgentFormProps) {
    const setForm = (patch: Partial<ExaminerAgentFormState>) => onChange({ ...form, ...patch });

    return (
        <div className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
                <label className="space-y-1 text-sm font-medium text-slate-700">
                    <span>名称</span>
                    <input
                        className="w-full rounded-xl border border-slate-200 px-3 py-2"
                        value={form.name}
                        onChange={(event) => setForm({ name: event.target.value })}
                    />
                </label>
                <label className="space-y-1 text-sm font-medium text-slate-700">
                    <span>描述</span>
                    <input
                        className="w-full rounded-xl border border-slate-200 px-3 py-2"
                        value={form.description}
                        onChange={(event) => setForm({ description: event.target.value })}
                    />
                </label>
                <label className="space-y-1 text-sm font-medium text-slate-700">
                    <span>题目来源 ID（逗号分隔）</span>
                    <input
                        className="w-full rounded-xl border border-slate-200 px-3 py-2"
                        value={form.question_source_ids_text}
                        onChange={(event) => setForm({ question_source_ids_text: event.target.value })}
                        placeholder="category-1, category-2"
                    />
                </label>
                <label className="space-y-1 text-sm font-medium text-slate-700">
                    <span>默认等级</span>
                    <select
                        className="w-full rounded-xl border border-slate-200 px-3 py-2"
                        value={form.learner_default_level}
                        onChange={(event) => setForm({
                            learner_default_level: event.target.value as ExaminerAgentFormState["learner_default_level"],
                        })}
                    >
                        {LEARNER_LEVEL_OPTIONS.map((option) => (
                            <option key={option.value} value={option.value}>{option.label}</option>
                        ))}
                    </select>
                </label>
                <label className="space-y-1 text-sm font-medium text-slate-700">
                    <span>允许等级（逗号分隔）</span>
                    <input
                        className="w-full rounded-xl border border-slate-200 px-3 py-2"
                        value={form.learner_allowed_levels_text}
                        onChange={(event) => setForm({ learner_allowed_levels_text: event.target.value })}
                        placeholder="conservative, beginner, intermediate"
                    />
                </label>
                <label className="space-y-1 text-sm font-medium text-slate-700">
                    <span>评分策略 ID</span>
                    <input
                        className="w-full rounded-xl border border-slate-200 px-3 py-2"
                        value={form.scoring_policy_id}
                        onChange={(event) => setForm({ scoring_policy_id: event.target.value })}
                    />
                </label>
                <label className="space-y-1 text-sm font-medium text-slate-700">
                    <span>超时上限（秒）</span>
                    <input
                        type="number"
                        className="w-full rounded-xl border border-slate-200 px-3 py-2"
                        value={form.timeout_max_seconds}
                        onChange={(event) => setForm({ timeout_max_seconds: Number(event.target.value) })}
                    />
                </label>
            </div>

            <div className="space-y-4">
                {(["safety_config", "prompt_config", "simulation_config"] as const).map((key) => {
                    const label = key === "safety_config"
                        ? "安全配置 (JSON)"
                        : key === "prompt_config"
                            ? "提示词配置 (JSON)"
                            : "模拟配置 (JSON)";
                    const field = form[key];
                    return (
                        <JsonEditorWithValidation
                            key={key}
                            label={label}
                            value={field.text}
                            rows={4}
                            onChange={(value) => {
                                const updated = parseJsonField(value);
                                setForm({ [key]: updated });
                            }}
                            isValid={!field.error}
                            validationMessage={field.error ? `JSON 格式错误：${field.error}` : "JSON 对象格式有效。"}
                            helpText="必须是 JSON 对象；留空会按空对象提交。"
                        />
                    );
                })}
            </div>
        </div>
    );
}
