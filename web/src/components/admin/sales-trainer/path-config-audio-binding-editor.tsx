"use client";

import Link from "next/link";

import type {
    SalesTrainerAudioScorePrompt,
    SalesTrainerMaterial,
} from "@/lib/api/types";
import type {
    AudioEditableModuleKey,
    PathAudioBindingValue,
} from "@/lib/sales-trainer/path-config-editing";
import { audioEvaluationScenarioForModule } from "@/lib/sales-trainer/audio-evaluation-scenarios";

interface PathConfigAudioBindingEditorProps {
    readonly availableMaterials: readonly SalesTrainerMaterial[];
    readonly availablePrompts: readonly SalesTrainerAudioScorePrompt[];
    readonly disabled: boolean;
    readonly moduleKey: AudioEditableModuleKey;
    readonly moduleTitle: string;
    readonly onChange: (value: PathAudioBindingValue) => void;
    readonly value: PathAudioBindingValue;
}

export function PathConfigAudioBindingEditor({
    availableMaterials,
    availablePrompts,
    disabled,
    moduleKey,
    moduleTitle,
    onChange,
    value,
}: PathConfigAudioBindingEditorProps) {
    const scenario = audioEvaluationScenarioForModule(moduleKey);
    const purpose = scenario.purposeKey;
    const materials = availableMaterials.filter((material) => (
        material.status === "published" && Boolean(material.current_version_id)
    ));
    const prompts = availablePrompts.filter((prompt) => prompt.status === "published");
    return (
        <div className="rounded-2xl border border-blue-100 bg-white p-4">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                <div>
                    <p className="text-sm font-black text-slate-900">优先绑定已有发布资源</p>
                    <p className="mt-1 text-sm text-slate-500">
                        {scenario.materialRequired
                            ? "该场景必须绑定已发布材料和评分标准；如果没有合适资源，可以先去管理页创建。"
                            : "该场景必须绑定评分标准，材料可按企业训练包选配。"}
                    </p>
                </div>
                <div className="flex flex-wrap gap-3 text-sm font-semibold text-blue-700">
                    <Link
                        href={`/admin/sales-trainer/audio/score-standards?module=${moduleKey}&purpose=${purpose}`}
                        className="underline"
                    >
                        管理评分标准
                    </Link>
                    <Link
                        href={`/admin/sales-trainer/audio/materials?module=${moduleKey}&purpose=${purpose}`}
                        className="underline"
                    >
                        管理材料库
                    </Link>
                </div>
            </div>
            <div className="mt-4 grid gap-3 md:grid-cols-2">
                <div className="space-y-2">
                    <label className="text-sm font-medium text-slate-700" htmlFor={`${moduleKey}-material`}>
                        {scenario.materialRequired ? "主材料" : "选配材料"}（{moduleTitle}）
                    </label>
                    <select
                        id={`${moduleKey}-material`}
                        value={value.materialId}
                        onChange={(event) => {
                            const material = materials.find((item) => item.material_id === event.target.value);
                            onChange({
                                ...value,
                                materialId: event.target.value,
                                materialVersionId: material?.current_version_id ?? "",
                            });
                        }}
                        disabled={disabled}
                        className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm"
                    >
                        <option value="">请选择已发布材料</option>
                        {materials.map((material) => (
                            <option key={material.material_id} value={material.material_id}>
                                {material.name} · {material.current_version?.version_label ?? "当前版本"}
                            </option>
                        ))}
                    </select>
                </div>
                <div className="space-y-2">
                    <label className="text-sm font-medium text-slate-700" htmlFor={`${moduleKey}-prompt`}>
                        录音评分标准（{moduleTitle}）
                    </label>
                    <select
                        id={`${moduleKey}-prompt`}
                        value={value.scoringPromptId}
                        onChange={(event) => onChange({ ...value, scoringPromptId: event.target.value })}
                        disabled={disabled}
                        className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm"
                    >
                        <option value="">请选择已发布评分标准</option>
                        {prompts.map((prompt) => (
                            <option key={prompt.prompt_id} value={prompt.prompt_id}>
                                {prompt.name} v{prompt.version}
                            </option>
                        ))}
                    </select>
                </div>
            </div>
        </div>
    );
}
