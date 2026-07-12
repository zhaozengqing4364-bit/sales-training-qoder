"use client";
import type { AiCoachActivity } from "@/lib/api/types/newcomer-training";
import { AdvancedSettings, ResourceSelect, controlClass } from "./editor-fields";
import type { ActivityEditorProps } from "./types";

export function AiCoachEditor({ value, disabled, resources, onChange }: ActivityEditorProps<AiCoachActivity>) {
    const patch = (config: Partial<AiCoachActivity["config"]>) => onChange({ ...value, config: { ...value.config, ...config } });
    return <div className="space-y-4"><ResourceSelect label="教练方案" value={value.config.coach_profile_id} options={resources.coach_profiles} disabled={disabled} onChange={(coach_profile_id) => patch({ coach_profile_id })} /><AdvancedSettings><label className="block text-sm font-medium text-slate-700">完成条件<select className={controlClass} value={value.config.completion_mode} disabled={disabled} onChange={(event) => patch({ completion_mode: event.target.value as AiCoachActivity["config"]["completion_mode"] })}><option value="session_completed">完成辅导会话</option><option value="goal_reached">达到辅导目标</option></select></label></AdvancedSettings></div>;
}
