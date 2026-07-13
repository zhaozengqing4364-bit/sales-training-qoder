"use client";

import type { AudioAssessmentActivity } from "@/lib/api/types/newcomer-training";
import {
    AdvancedSettings,
    controlClass,
    NumberField,
    ResourceSelect,
} from "./editor-fields";
import type { ActivityEditorProps } from "./types";

export function AudioAssessmentEditor({
    value,
    disabled,
    resources,
    onChange,
    onQuickCreate,
}: ActivityEditorProps<AudioAssessmentActivity>) {
    const patch = (config: Partial<AudioAssessmentActivity["config"]>) =>
        onChange({ ...value, config: { ...value.config, ...config } });

    return (
        <div className="space-y-4">
            <ResourceSelect
                label="评分标准"
                value={value.config.scoring_rubric_id}
                options={resources.scoring_rubrics}
                disabled={disabled}
                onChange={(scoring_rubric_id) => patch({ scoring_rubric_id })}
                quickCreate="scoring_rubric"
                onQuickCreate={onQuickCreate}
            />
            <ResourceSelect
                label="讲解材料"
                value={value.config.material_id}
                options={resources.materials}
                disabled={disabled}
                onChange={(material_id) => patch({ material_id: material_id || null })}
                quickCreate="material"
                onQuickCreate={onQuickCreate}
            />
            <label className="block text-sm font-medium text-slate-700">
                优秀讲解示例（文字版）
                <textarea
                    aria-label="优秀讲解示例（文字版）"
                    aria-describedby="audio-example-transcript-help"
                    className={`${controlClass} min-h-40 resize-y leading-6`}
                    value={value.config.example_transcript ?? ""}
                    disabled={disabled}
                    maxLength={8000}
                    placeholder="例如：先说明客户面临的问题，再结合材料讲清方案价值……"
                    onChange={(event) =>
                        patch({ example_transcript: event.target.value || null })
                    }
                />
            </label>
            <p id="audio-example-transcript-help" className="-mt-2 text-xs leading-5 text-slate-500">
                学员会在录音前看到这段文字，请提供一份可模仿的完整讲解。
            </p>
            <NumberField
                label="通过分"
                value={value.config.pass_score}
                min={0}
                max={100}
                disabled={disabled}
                onChange={(pass_score) => patch({ pass_score: pass_score ?? 0 })}
            />
            <AdvancedSettings>
                <NumberField
                    label="最多尝试次数"
                    value={value.config.max_attempts}
                    min={1}
                    disabled={disabled}
                    onChange={(max_attempts) => patch({ max_attempts })}
                />
            </AdvancedSettings>
        </div>
    );
}
