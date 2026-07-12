"use client";
import type { RealtimeRoleplayActivity } from "@/lib/api/types/newcomer-training";
import { AdvancedSettings, ResourceSelect, controlClass } from "./editor-fields";
import type { ActivityEditorProps } from "./types";

export function RealtimeRoleplayEditor({ value, disabled, resources, onChange }: ActivityEditorProps<RealtimeRoleplayActivity>) {
    const patch = (config: Partial<RealtimeRoleplayActivity["config"]>) => onChange({ ...value, config: { ...value.config, ...config } });
    return <div className="space-y-4"><ResourceSelect label="对练模板" value={value.config.practice_template_id} options={resources.practice_templates} disabled={disabled} onChange={(practice_template_id) => patch({ practice_template_id })} /><ResourceSelect label="语音方案" value={value.config.runtime_profile_id} options={resources.runtime_profiles} disabled={disabled} onChange={(runtime_profile_id) => patch({ runtime_profile_id })} /><AdvancedSettings><label className="block text-sm font-medium text-slate-700">完成条件<select className={controlClass} value={value.config.completion_mode} disabled={disabled} onChange={(event) => patch({ completion_mode: event.target.value as RealtimeRoleplayActivity["config"]["completion_mode"] })}><option value="session_completed">完成一次对练</option><option value="scored">获得有效评分</option></select></label></AdvancedSettings></div>;
}
