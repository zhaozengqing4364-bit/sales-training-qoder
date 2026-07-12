"use client";

import { useState } from "react";
import type { ActivityConfig, ModuleConfig, TrainingPathPayload } from "@/lib/api/types/newcomer-training";

const inputClass = "mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100";

function csv(values: string[]): string { return values.join(", "); }
function parseCsv(value: string): string[] { return [...new Set(value.split(/[,，\n]/).map((item) => item.trim()).filter(Boolean))]; }

function CsvField({ label, initialValue, placeholder, onCommit }: { label: string; initialValue: string[]; placeholder: string; onCommit: (values: string[]) => void }) {
    const [text, setText] = useState(csv(initialValue));
    return <label className="text-sm font-medium text-slate-700">{label}<input aria-label={label} className={inputClass} value={text} placeholder={placeholder} onChange={(event) => setText(event.target.value)} onBlur={() => onCommit(parseCsv(text))} /></label>;
}

export function PathRuleEditor({ path, value, onPatch }: {
    path: TrainingPathPayload;
    value: ModuleConfig | ActivityConfig;
    onPatch: (patch: Record<string, unknown>) => void;
}) {
    const isModule = "activities" in value;
    const dependencyOptions = isModule
        ? path.phases.flatMap((phase) => phase.modules).filter((item) => item.module_id !== value.module_id).map((item) => ({ id: item.module_id, title: item.title }))
        : path.phases.flatMap((phase) => phase.modules).flatMap((moduleConfig) => moduleConfig.activities).filter((item) => item.activity_id !== value.activity_id).map((item) => ({ id: item.activity_id, title: item.title }));

    return <details open className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
        <summary className="cursor-pointer font-medium text-slate-800">适用范围、前置条件与完成规则</summary>
        <div className="mt-4 space-y-4">
            {isModule ? <div className="grid gap-3">
                <CsvField label="适用部门" initialValue={value.audience_rule.departments} placeholder="例如：华东销售, 华南销售；留空表示不限" onCommit={(departments) => onPatch({ audience_rule: { ...value.audience_rule, departments } })} />
                <CsvField label="适用角色" initialValue={value.audience_rule.roles} placeholder="留空表示不限" onCommit={(roles) => onPatch({ audience_rule: { ...value.audience_rule, roles } })} />
                <CsvField label="适用学员级别" initialValue={value.audience_rule.learner_levels} placeholder="留空表示不限" onCommit={(learner_levels) => onPatch({ audience_rule: { ...value.audience_rule, learner_levels } })} />
            </div> : null}
            <fieldset><legend className="text-sm font-medium text-slate-700">前置{isModule ? "模块" : "活动"}</legend><div className="mt-2 max-h-36 space-y-1 overflow-auto rounded-xl border border-slate-200 bg-white p-2">{dependencyOptions.length ? dependencyOptions.map((option) => <label key={option.id} className="flex min-h-9 items-center gap-2 rounded-lg px-2 text-sm hover:bg-slate-50"><input type="checkbox" checked={value.prerequisites.includes(option.id)} onChange={(event) => onPatch({ prerequisites: event.target.checked ? [...value.prerequisites, option.id] : value.prerequisites.filter((id) => id !== option.id) })} />{option.title}</label>) : <p className="p-2 text-sm text-slate-500">当前没有可选的前置对象。</p>}</div></fieldset>
            {isModule ? <div className="grid gap-3 sm:grid-cols-2"><label className="text-sm font-medium text-slate-700">完成规则<select aria-label="完成规则" className={inputClass} value={value.completion_policy.mode} onChange={(event) => onPatch({ completion_policy: { ...value.completion_policy, mode: event.target.value, count: event.target.value === "all_required" ? null : value.completion_policy.count ?? 1 } })}><option value="all_required">完成全部必修活动</option><option value="at_least_count">至少完成指定数量</option></select></label>{value.completion_policy.mode === "at_least_count" ? <label className="text-sm font-medium text-slate-700">至少完成活动数<input aria-label="至少完成活动数" type="number" min={1} max={Math.max(1, value.activities.length)} className={inputClass} value={value.completion_policy.count ?? ""} onChange={(event) => onPatch({ completion_policy: { ...value.completion_policy, count: event.target.value === "" ? null : Math.max(1, Number(event.target.value)) } })} /></label> : null}</div> : null}
        </div>
    </details>;
}
