"use client";

import { Button } from "@/components/ui/button";
import { PublishedGovernanceNotice } from "@/components/admin/sales-trainer/published-governance-notice";
import {
    UnitAudioScoringSection,
    UnitMaterialBindingSection,
    UnitTaskBriefSection,
} from "@/components/admin/sales-trainer/unit-audio-config-sections";
import { UnitBasicInfoSection } from "@/components/admin/sales-trainer/unit-basic-info-section";
import { UnitPathConfigSection } from "@/components/admin/sales-trainer/unit-path-config-section";
import { UnitQuestionBindingSection } from "@/components/admin/sales-trainer/unit-question-binding-section";
import { useSalesTrainerUnitForm } from "@/components/admin/sales-trainer/unit-form-state";
import type {
    QuestionItem,
    SalesTrainerAudioScorePrompt,
    SalesTrainerMaterial,
    SalesTrainerQuestion,
    SalesTrainerUnit,
    SalesTrainerUnitCreateRequest,
    SalesTrainerUnitUpdateRequest,
} from "@/lib/api/types";

interface SalesTrainerUnitFormProps {
    mode: "create" | "edit";
    initialUnit?: SalesTrainerUnit | null;
    availableQuestions: Array<QuestionItem | SalesTrainerQuestion>;
    availablePrompts: SalesTrainerAudioScorePrompt[];
    availableMaterials?: SalesTrainerMaterial[];
    isSubmitting: boolean;
    onSubmit: (
        payload: SalesTrainerUnitCreateRequest | SalesTrainerUnitUpdateRequest,
    ) => Promise<void> | void;
}

export function SalesTrainerUnitForm({
    mode,
    initialUnit,
    availableQuestions,
    availablePrompts,
    availableMaterials = [],
    isSubmitting,
    onSubmit,
}: SalesTrainerUnitFormProps) {
    const form = useSalesTrainerUnitForm({ initialUnit, onSubmit });

    return (
        <form className="space-y-6" noValidate onSubmit={form.handleSubmit}>
            <UnitBasicInfoSection
                canEdit={form.canEdit}
                description={form.description}
                isEditMode={mode === "edit"}
                isSubmitting={isSubmitting}
                name={form.name}
                setDescription={form.setDescription}
                setName={form.setName}
                setUnitType={form.setUnitType}
                unitType={form.unitType}
            />

            {form.unitType === "quiz" ? (
                <UnitQuestionBindingSection
                    availableQuestions={availableQuestions}
                    canEdit={form.canEdit}
                    isSubmitting={isSubmitting}
                    selectedQuestionIds={form.selectedQuestionIds}
                    selectedQuestions={form.selectedQuestions}
                    toggleQuestion={form.toggleQuestion}
                    updateQuestionPoints={form.updateQuestionPoints}
                />
            ) : (
                <UnitAudioScoringSection
                    audioPurpose={form.audioPurpose}
                    availablePrompts={availablePrompts}
                    canEdit={form.canEdit}
                    isSubmitting={isSubmitting}
                    passThreshold={form.passThreshold}
                    promptId={form.promptId}
                    setAudioPurpose={form.setAudioPurpose}
                    setPassThreshold={form.setPassThreshold}
                    setPromptId={form.setPromptId}
                />
            )}

            {form.unitType === "audio_scoring" ? (
                <UnitTaskBriefSection
                    canEdit={form.canEdit}
                    isSubmitting={isSubmitting}
                    name={form.name}
                    setTaskBriefCommonMistakes={form.setTaskBriefCommonMistakes}
                    setTaskBriefInstructions={form.setTaskBriefInstructions}
                    setTaskBriefPurpose={form.setTaskBriefPurpose}
                    setTaskBriefScenario={form.setTaskBriefScenario}
                    setTaskBriefSuccessCriteria={form.setTaskBriefSuccessCriteria}
                    setTaskBriefTitle={form.setTaskBriefTitle}
                    setTaskBriefUploadGuidance={form.setTaskBriefUploadGuidance}
                    taskBriefCommonMistakes={form.taskBriefCommonMistakes}
                    taskBriefInstructions={form.taskBriefInstructions}
                    taskBriefPurpose={form.taskBriefPurpose}
                    taskBriefScenario={form.taskBriefScenario}
                    taskBriefSuccessCriteria={form.taskBriefSuccessCriteria}
                    taskBriefTitle={form.taskBriefTitle}
                    taskBriefUploadGuidance={form.taskBriefUploadGuidance}
                />
            ) : null}

            {form.unitType === "audio_scoring" ? (
                <UnitMaterialBindingSection
                    availableMaterials={availableMaterials}
                    canEdit={form.canEdit}
                    isSubmitting={isSubmitting}
                    materialConfirmationRequired={form.materialConfirmationRequired}
                    materialId={form.materialId}
                    materialLearnerNote={form.materialLearnerNote}
                    setMaterialConfirmationRequired={form.setMaterialConfirmationRequired}
                    setMaterialId={form.setMaterialId}
                    setMaterialLearnerNote={form.setMaterialLearnerNote}
                />
            ) : null}

            <UnitPathConfigSection
                canEdit={form.canEdit}
                completionRule={form.completionRule}
                goalTitle={form.goalTitle}
                guidanceTemplates={form.guidanceTemplates}
                isSubmitting={isSubmitting}
                levelDescription={form.levelDescription}
                levelTitle={form.levelTitle}
                name={form.name}
                pathEnabled={form.pathEnabled}
                pathKey={form.pathKey}
                pathOrderIndex={form.pathOrderIndex}
                pathTitle={form.pathTitle}
                primaryActionLabel={form.primaryActionLabel}
                retryActionLabel={form.retryActionLabel}
                reviewActionLabel={form.reviewActionLabel}
                setCompletionRule={form.setCompletionRule}
                setGoalTitle={form.setGoalTitle}
                setGuidanceTemplates={form.setGuidanceTemplates}
                setLevelDescription={form.setLevelDescription}
                setLevelTitle={form.setLevelTitle}
                setPathEnabled={form.setPathEnabled}
                setPathKey={form.setPathKey}
                setPathOrderIndex={form.setPathOrderIndex}
                setPathTitle={form.setPathTitle}
                setPrimaryActionLabel={form.setPrimaryActionLabel}
                setRetryActionLabel={form.setRetryActionLabel}
                setReviewActionLabel={form.setReviewActionLabel}
                setUnlockAfterUnitIds={form.setUnlockAfterUnitIds}
                unlockAfterUnitIds={form.unlockAfterUnitIds}
            />

            {form.error ? (
                <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                    {form.error}
                </div>
            ) : null}

            {initialUnit?.status === "published" || !form.canEdit ? (
                <PublishedGovernanceNotice
                    status={initialUnit?.status}
                />
            ) : null}

            <div className="flex justify-end">
                <Button
                    type="submit"
                    disabled={isSubmitting || !form.canEdit}
                    className="rounded-full bg-slate-900 text-white"
                >
                    {isSubmitting ? "保存中..." : mode === "create" ? "创建训练单元" : "保存训练单元"}
                </Button>
            </div>
        </form>
    );
}
