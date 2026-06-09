import { useMemo, useState, type FormEvent } from "react";

import {
    buildUnitFormPayload,
    initialUnitFormModel,
    type QuestionSelection,
} from "@/components/admin/sales-trainer/unit-form-model";
import { type SalesTrainerCompletionRule } from "@/components/admin/sales-trainer/unit-path-config-section";
import { validateUnitForm } from "@/components/admin/sales-trainer/unit-form-utils";
import type {
    SalesTrainerStatus,
    SalesTrainerUnit,
    SalesTrainerUnitCreateRequest,
    SalesTrainerUnitType,
    SalesTrainerUnitUpdateRequest,
} from "@/lib/api/types";

interface UnitFormStateInput {
    readonly initialUnit?: SalesTrainerUnit | null;
    readonly onSubmit: (
        payload: SalesTrainerUnitCreateRequest | SalesTrainerUnitUpdateRequest,
    ) => Promise<void> | void;
}

function canEditUnitRevision(status: SalesTrainerStatus | undefined): boolean {
    return status === undefined || status !== "archived";
}

export function useSalesTrainerUnitForm({
    initialUnit,
    onSubmit,
}: UnitFormStateInput) {
    const initialModel = initialUnitFormModel(initialUnit);
    const [name, setName] = useState(initialUnit?.name ?? "");
    const [description, setDescription] = useState(initialUnit?.description ?? "");
    const [unitType, setUnitType] = useState<SalesTrainerUnitType>(
        initialUnit?.unit_type ?? "quiz",
    );
    const [promptId, setPromptId] = useState(initialModel.promptId);
    const [passThreshold, setPassThreshold] = useState(initialModel.passThreshold);
    const [audioPurpose, setAudioPurpose] = useState(initialModel.audioPurpose);
    const [taskBriefTitle, setTaskBriefTitle] = useState(initialModel.taskBriefTitle);
    const [taskBriefPurpose, setTaskBriefPurpose] = useState(initialModel.taskBriefPurpose);
    const [taskBriefScenario, setTaskBriefScenario] = useState(initialModel.taskBriefScenario);
    const [taskBriefInstructions, setTaskBriefInstructions] = useState(initialModel.taskBriefInstructions);
    const [taskBriefSuccessCriteria, setTaskBriefSuccessCriteria] = useState(initialModel.taskBriefSuccessCriteria);
    const [taskBriefCommonMistakes, setTaskBriefCommonMistakes] = useState(initialModel.taskBriefCommonMistakes);
    const [taskBriefUploadGuidance, setTaskBriefUploadGuidance] = useState(initialModel.taskBriefUploadGuidance);
    const [materialId, setMaterialId] = useState(initialModel.materialId);
    const [materialConfirmationRequired, setMaterialConfirmationRequired] = useState(initialModel.materialConfirmationRequired);
    const [materialLearnerNote, setMaterialLearnerNote] = useState(initialModel.materialLearnerNote);
    const [pathEnabled, setPathEnabled] = useState(initialModel.pathEnabled);
    const [pathKey, setPathKey] = useState(initialModel.pathKey);
    const [pathModuleKey] = useState(initialModel.pathModuleKey);
    const [pathModuleType] = useState(initialModel.pathModuleType);
    const [pathTitle, setPathTitle] = useState(initialModel.pathTitle);
    const [goalTitle, setGoalTitle] = useState(initialModel.goalTitle);
    const [levelTitle, setLevelTitle] = useState(initialModel.levelTitle);
    const [levelDescription, setLevelDescription] = useState(initialModel.levelDescription);
    const [pathOrderIndex, setPathOrderIndex] = useState(initialModel.pathOrderIndex);
    const [unlockAfterUnitIds, setUnlockAfterUnitIds] = useState(initialModel.unlockAfterUnitIds);
    const [completionRule, setCompletionRule] = useState<SalesTrainerCompletionRule | "">(initialModel.completionRule);
    const [primaryActionLabel, setPrimaryActionLabel] = useState(initialModel.primaryActionLabel);
    const [retryActionLabel, setRetryActionLabel] = useState(initialModel.retryActionLabel);
    const [reviewActionLabel, setReviewActionLabel] = useState(initialModel.reviewActionLabel);
    const [guidanceTemplates, setGuidanceTemplates] = useState(initialModel.guidanceTemplates);
    const [selectedQuestions, setSelectedQuestions] = useState<QuestionSelection[]>([...initialModel.selectedQuestions]);
    const [error, setError] = useState<string | null>(null);
    const selectedQuestionIds = useMemo(
        () => new Set(selectedQuestions.map((question) => question.question_id)),
        [selectedQuestions],
    );
    const canEdit = canEditUnitRevision(initialUnit?.status);

    function toggleQuestion(questionId: string) {
        setSelectedQuestions((current) => {
            if (current.some((question) => question.question_id === questionId)) {
                return current
                    .filter((question) => question.question_id !== questionId)
                    .map((question, index) => ({
                        ...question,
                        order_index: index + 1,
                    }));
            }
            return [
                ...current,
                {
                    question_id: questionId,
                    order_index: current.length + 1,
                    points: 10,
                },
            ];
        });
    }

    function updateQuestionPoints(questionId: string, value: string) {
        setSelectedQuestions((current) =>
            current.map((question) =>
                question.question_id === questionId
                    ? { ...question, points: Math.max(1, Number(value) || 1) }
                    : question,
            ),
        );
    }

    async function handleSubmit(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        setError(null);
        const validationError = validateUnitForm({
            audioPurpose,
            canEdit,
            materialId,
            name,
            promptId,
            selectedQuestions,
            unitType,
        });
        if (validationError) {
            setError(validationError);
            return;
        }
        try {
            const payload = buildUnitFormPayload({
                audioPurpose,
                completionRule,
                description,
                goalTitle,
                guidanceTemplates,
                levelDescription,
                levelTitle,
                materialConfirmationRequired,
                materialId,
                materialLearnerNote,
                name,
                passThreshold,
                pathEnabled,
                pathKey,
                pathModuleKey,
                pathModuleType,
                pathOrderIndex,
                pathTitle,
                primaryActionLabel,
                promptId,
                retryActionLabel,
                reviewActionLabel,
                selectedQuestions,
                taskBriefCommonMistakes,
                taskBriefInstructions,
                taskBriefPurpose,
                taskBriefScenario,
                taskBriefSuccessCriteria,
                taskBriefTitle,
                taskBriefUploadGuidance,
                unitType,
                unlockAfterUnitIds,
            });
            await onSubmit(payload);
        } catch (parseError) {
            setError(parseError instanceof Error ? parseError.message : "训练单元配置不合法。");
        }
    }

    return {
        audioPurpose,
        canEdit,
        completionRule,
        description,
        error,
        goalTitle,
        guidanceTemplates,
        handleSubmit,
        levelDescription,
        levelTitle,
        materialConfirmationRequired,
        materialId,
        materialLearnerNote,
        name,
        passThreshold,
        pathEnabled,
        pathKey,
        pathOrderIndex,
        pathTitle,
        primaryActionLabel,
        promptId,
        retryActionLabel,
        reviewActionLabel,
        selectedQuestionIds,
        selectedQuestions,
        setAudioPurpose,
        setCompletionRule,
        setDescription,
        setGoalTitle,
        setGuidanceTemplates,
        setLevelDescription,
        setLevelTitle,
        setMaterialConfirmationRequired,
        setMaterialId,
        setMaterialLearnerNote,
        setName,
        setPassThreshold,
        setPathEnabled,
        setPathKey,
        setPathOrderIndex,
        setPathTitle,
        setPrimaryActionLabel,
        setPromptId,
        setRetryActionLabel,
        setReviewActionLabel,
        setTaskBriefCommonMistakes,
        setTaskBriefInstructions,
        setTaskBriefPurpose,
        setTaskBriefScenario,
        setTaskBriefSuccessCriteria,
        setTaskBriefTitle,
        setTaskBriefUploadGuidance,
        setUnitType,
        setUnlockAfterUnitIds,
        taskBriefCommonMistakes,
        taskBriefInstructions,
        taskBriefPurpose,
        taskBriefScenario,
        taskBriefSuccessCriteria,
        taskBriefTitle,
        taskBriefUploadGuidance,
        toggleQuestion,
        unitType,
        unlockAfterUnitIds,
        updateQuestionPoints,
    };
}
