"use client";

import { GlassCard } from "@/components/ui/glass-card";
import { Input } from "@/components/ui/input";
import type {
    SalesTrainerAudioScorePrompt,
    SalesTrainerMaterial,
} from "@/lib/api/types";
import {
    formatTrainingPurpose,
    TRAINING_PURPOSE_OPTIONS,
} from "@/lib/sales-trainer/admin-display";

interface UnitAudioScoringSectionProps {
    readonly audioPurpose: string;
    readonly availablePrompts: readonly SalesTrainerAudioScorePrompt[];
    readonly canEdit: boolean;
    readonly isSubmitting: boolean;
    readonly passThreshold: string;
    readonly promptId: string;
    readonly setAudioPurpose: (value: string) => void;
    readonly setPassThreshold: (value: string) => void;
    readonly setPromptId: (value: string) => void;
}

export function UnitAudioScoringSection({
    audioPurpose,
    availablePrompts,
    canEdit,
    isSubmitting,
    passThreshold,
    promptId,
    setAudioPurpose,
    setPassThreshold,
    setPromptId,
}: UnitAudioScoringSectionProps) {
    const hasKnownPurpose = TRAINING_PURPOSE_OPTIONS.some((option) => option.value === audioPurpose);
    return (
        <GlassCard className="space-y-4 p-6">
            <div>
                <h2 className="text-lg font-bold text-slate-900">录音评分配置</h2>
                <p className="mt-1 text-sm text-slate-500">
                    时长上限、格式和大小限制由后端配置控制，前端这里不写死业务规则。
                </p>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                    <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-audio-purpose">录音用途</label>
                    <select id="sales-trainer-audio-purpose" value={audioPurpose} onChange={(event) => setAudioPurpose(event.target.value)} disabled={isSubmitting || !canEdit} className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm">
                        {TRAINING_PURPOSE_OPTIONS.map((option) => (
                            <option key={option.value} value={option.value}>{option.label}</option>
                        ))}
                        {!hasKnownPurpose && audioPurpose ? (
                            <option value={audioPurpose}>{formatTrainingPurpose(audioPurpose)}</option>
                        ) : null}
                    </select>
                </div>
                <div className="space-y-2">
                    <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-prompt-id">录音评分标准</label>
                    <select id="sales-trainer-prompt-id" value={promptId} onChange={(event) => setPromptId(event.target.value)} disabled={isSubmitting || !canEdit} className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm">
                        <option value="">请选择已发布录音评分标准</option>
                        {availablePrompts.filter((prompt) => prompt.status === "published").map((prompt) => (
                            <option key={prompt.prompt_id} value={prompt.prompt_id}>{prompt.name}</option>
                        ))}
                    </select>
                </div>
                <div className="space-y-2 md:col-span-2">
                    <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-pass-threshold">通过线（可选）</label>
                    <Input id="sales-trainer-pass-threshold" type="number" min={0} max={100} value={passThreshold} onChange={(event) => setPassThreshold(event.target.value)} disabled={isSubmitting || !canEdit} placeholder="留空使用后端默认通过线" />
                </div>
            </div>
        </GlassCard>
    );
}

interface UnitTaskBriefSectionProps {
    readonly canEdit: boolean;
    readonly isSubmitting: boolean;
    readonly name: string;
    readonly setTaskBriefCommonMistakes: (value: string) => void;
    readonly setTaskBriefInstructions: (value: string) => void;
    readonly setTaskBriefPurpose: (value: string) => void;
    readonly setTaskBriefScenario: (value: string) => void;
    readonly setTaskBriefSuccessCriteria: (value: string) => void;
    readonly setTaskBriefTitle: (value: string) => void;
    readonly setTaskBriefUploadGuidance: (value: string) => void;
    readonly taskBriefCommonMistakes: string;
    readonly taskBriefInstructions: string;
    readonly taskBriefPurpose: string;
    readonly taskBriefScenario: string;
    readonly taskBriefSuccessCriteria: string;
    readonly taskBriefTitle: string;
    readonly taskBriefUploadGuidance: string;
}

export function UnitTaskBriefSection({
    canEdit,
    isSubmitting,
    name,
    setTaskBriefCommonMistakes,
    setTaskBriefInstructions,
    setTaskBriefPurpose,
    setTaskBriefScenario,
    setTaskBriefSuccessCriteria,
    setTaskBriefTitle,
    setTaskBriefUploadGuidance,
    taskBriefCommonMistakes,
    taskBriefInstructions,
    taskBriefPurpose,
    taskBriefScenario,
    taskBriefSuccessCriteria,
    taskBriefTitle,
    taskBriefUploadGuidance,
}: UnitTaskBriefSectionProps) {
    return (
        <GlassCard className="space-y-4 p-6">
            <div>
                <h2 className="text-lg font-bold text-slate-900">任务简报</h2>
                <p className="mt-1 text-sm text-slate-500">学员进入录音页时先看到这里配置的训练目标、场景和完成标准。</p>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
                <BriefInput id="sales-trainer-brief-title" label="简报标题" value={taskBriefTitle} onChange={setTaskBriefTitle} disabled={isSubmitting || !canEdit} placeholder={name || "例如 PPT 演练"} />
                <BriefInput id="sales-trainer-brief-purpose" label="训练意义" value={taskBriefPurpose} onChange={setTaskBriefPurpose} disabled={isSubmitting || !canEdit} placeholder="说明这关训练解决什么问题" />
                <BriefTextarea id="sales-trainer-brief-scenario" label="训练场景" rows={3} value={taskBriefScenario} onChange={setTaskBriefScenario} disabled={isSubmitting || !canEdit} span />
                <BriefTextarea id="sales-trainer-brief-instructions" label="任务步骤" rows={5} value={taskBriefInstructions} onChange={setTaskBriefInstructions} disabled={isSubmitting || !canEdit} placeholder="每行一条" />
                <BriefTextarea id="sales-trainer-brief-success" label="完成标准" rows={5} value={taskBriefSuccessCriteria} onChange={setTaskBriefSuccessCriteria} disabled={isSubmitting || !canEdit} placeholder="每行一条" />
                <BriefTextarea id="sales-trainer-brief-mistakes" label="常见扣分点" rows={4} value={taskBriefCommonMistakes} onChange={setTaskBriefCommonMistakes} disabled={isSubmitting || !canEdit} placeholder="每行一条" />
                <BriefTextarea id="sales-trainer-upload-guidance" label="上传说明" rows={4} value={taskBriefUploadGuidance} onChange={setTaskBriefUploadGuidance} disabled={isSubmitting || !canEdit} />
            </div>
        </GlassCard>
    );
}

interface UnitMaterialBindingSectionProps {
    readonly availableMaterials: readonly SalesTrainerMaterial[];
    readonly canEdit: boolean;
    readonly isSubmitting: boolean;
    readonly materialConfirmationRequired: boolean;
    readonly materialId: string;
    readonly materialLearnerNote: string;
    readonly setMaterialConfirmationRequired: (value: boolean) => void;
    readonly setMaterialId: (value: string) => void;
    readonly setMaterialLearnerNote: (value: string) => void;
}

export function UnitMaterialBindingSection({
    availableMaterials,
    canEdit,
    isSubmitting,
    materialConfirmationRequired,
    materialId,
    materialLearnerNote,
    setMaterialConfirmationRequired,
    setMaterialId,
    setMaterialLearnerNote,
}: UnitMaterialBindingSectionProps) {
    return (
        <GlassCard className="space-y-4 p-6">
            <div>
                <h2 className="text-lg font-bold text-slate-900">训练材料绑定</h2>
                <p className="mt-1 text-sm text-slate-500">需要材料的录音评测场景必须绑定训练材料库中的已发布材料，并要求学员确认最新版后上传。</p>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                    <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-material-id">主材料</label>
                    <select id="sales-trainer-material-id" value={materialId} onChange={(event) => setMaterialId(event.target.value)} disabled={isSubmitting || !canEdit} className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm">
                        <option value="">不绑定材料</option>
                        {availableMaterials.filter((material) => material.status === "published").map((material) => (
                            <option key={material.material_id} value={material.material_id}>
                                {material.name} · {material.current_version?.version_label ?? "无发布版本"}
                            </option>
                        ))}
                    </select>
                </div>
                <label className="flex items-center gap-2 pt-8 text-sm text-slate-700">
                    <input type="checkbox" checked={materialConfirmationRequired} onChange={(event) => setMaterialConfirmationRequired(event.target.checked)} disabled={isSubmitting || !canEdit} />
                    上传前要求确认当前版本
                </label>
                <BriefTextarea id="sales-trainer-material-note" label="学员侧材料说明" rows={3} value={materialLearnerNote} onChange={setMaterialLearnerNote} disabled={isSubmitting || !canEdit} span />
            </div>
        </GlassCard>
    );
}

interface BriefInputProps {
    readonly disabled: boolean;
    readonly id: string;
    readonly label: string;
    readonly onChange: (value: string) => void;
    readonly placeholder?: string;
    readonly value: string;
}

function BriefInput({ disabled, id, label, onChange, placeholder, value }: BriefInputProps) {
    return (
        <div className="space-y-2">
            <label className="text-sm font-medium text-slate-700" htmlFor={id}>{label}</label>
            <Input id={id} value={value} onChange={(event) => onChange(event.target.value)} disabled={disabled} placeholder={placeholder} />
        </div>
    );
}

interface BriefTextareaProps extends BriefInputProps {
    readonly rows: number;
    readonly span?: boolean;
}

function BriefTextarea({ disabled, id, label, onChange, placeholder, rows, span = false, value }: BriefTextareaProps) {
    return (
        <div className={`space-y-2 ${span ? "md:col-span-2" : ""}`}>
            <label className="text-sm font-medium text-slate-700" htmlFor={id}>{label}</label>
            <textarea id={id} value={value} onChange={(event) => onChange(event.target.value)} disabled={disabled} rows={rows} className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm" placeholder={placeholder} />
        </div>
    );
}
