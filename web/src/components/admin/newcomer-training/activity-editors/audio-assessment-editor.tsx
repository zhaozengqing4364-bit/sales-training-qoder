"use client";
import type { AudioAssessmentActivity } from "@/lib/api/types/newcomer-training";
import { AdvancedSettings, NumberField, ResourceSelect } from "./editor-fields";
import type { ActivityEditorProps } from "./types";

export function AudioAssessmentEditor({ value, disabled, resources, onChange, onQuickCreate }: ActivityEditorProps<AudioAssessmentActivity>) {
    const patch = (config: Partial<AudioAssessmentActivity["config"]>) => onChange({ ...value, config: { ...value.config, ...config } });
    return <div className="space-y-4"><ResourceSelect label="评分标准" value={value.config.scoring_rubric_id} options={resources.scoring_rubrics} disabled={disabled} onChange={(scoring_rubric_id) => patch({ scoring_rubric_id })} quickCreate="scoring_rubric" onQuickCreate={onQuickCreate} /><ResourceSelect label="讲解材料" value={value.config.material_id} options={resources.materials} disabled={disabled} onChange={(material_id) => patch({ material_id: material_id || null })} quickCreate="material" onQuickCreate={onQuickCreate} /><NumberField label="通过分" value={value.config.pass_score} min={0} max={100} disabled={disabled} onChange={(pass_score) => patch({ pass_score: pass_score ?? 0 })} /><AdvancedSettings><NumberField label="最多尝试次数" value={value.config.max_attempts} min={1} disabled={disabled} onChange={(max_attempts) => patch({ max_attempts })} /></AdvancedSettings></div>;
}
