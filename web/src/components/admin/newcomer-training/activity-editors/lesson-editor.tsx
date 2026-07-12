"use client";
import type { LessonActivity } from "@/lib/api/types/newcomer-training";
import { AdvancedSettings, ResourceSelect, controlClass } from "./editor-fields";
import type { ActivityEditorProps } from "./types";

export function LessonEditor({ value, disabled, resources, onChange, onQuickCreate }: ActivityEditorProps<LessonActivity>) {
    const patch = (config: Partial<LessonActivity["config"]>) => onChange({ ...value, config: { ...value.config, ...config } });
    return <div className="space-y-4"><ResourceSelect label="学习内容" value={value.config.learning_content_id} options={resources.learning_contents} disabled={disabled} onChange={(learning_content_id) => patch({ learning_content_id })} quickCreate="learning_content" onQuickCreate={onQuickCreate} /><AdvancedSettings><label className="block text-sm font-medium text-slate-700">完成条件<select className={controlClass} value={value.config.completion_mode} disabled={disabled} onChange={(event) => patch({ completion_mode: event.target.value as LessonActivity["config"]["completion_mode"] })}><option value="all_chapters">完成全部章节</option><option value="learner_confirmed">学员确认完成</option></select></label></AdvancedSettings></div>;
}
