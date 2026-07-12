"use client";
import type { QuizActivity } from "@/lib/api/types/newcomer-training";
import { AdvancedSettings, NumberField, ResourceSelect } from "./editor-fields";
import type { ActivityEditorProps } from "./types";

export function QuizEditor({ value, disabled, resources, onChange, onQuickCreate }: ActivityEditorProps<QuizActivity>) {
    const patch = (config: Partial<QuizActivity["config"]>) => onChange({ ...value, config: { ...value.config, ...config } });
    return <div className="space-y-4"><ResourceSelect label="试卷" value={value.config.exam_paper_id} options={resources.exam_papers} disabled={disabled} onChange={(exam_paper_id) => patch({ exam_paper_id })} quickCreate="exam_paper" onQuickCreate={onQuickCreate} /><NumberField label="通过分" value={value.config.pass_score} min={0} max={100} disabled={disabled} onChange={(pass_score) => patch({ pass_score: pass_score ?? 0 })} /><AdvancedSettings><NumberField label="最多尝试次数" value={value.config.max_attempts} min={1} disabled={disabled} onChange={(max_attempts) => patch({ max_attempts })} /></AdvancedSettings></div>;
}
