"use client";

import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { Input } from "@/components/ui/input";
import type {
    QuestionItem,
    SalesTrainerQuestion,
    SalesTrainerAudioScorePrompt,
    SalesTrainerStatus,
    SalesTrainerUnit,
    SalesTrainerUnitCreateRequest,
    SalesTrainerUnitQuestionBinding,
    SalesTrainerUnitType,
    SalesTrainerUnitUpdateRequest,
} from "@/lib/api/types";

type QuestionSelection = SalesTrainerUnitQuestionBinding;
type SalesTrainerCompletionRule = "passed" | "scored" | "submitted";

interface SalesTrainerUnitFormProps {
    mode: "create" | "edit";
    initialUnit?: SalesTrainerUnit | null;
    availableQuestions: Array<QuestionItem | SalesTrainerQuestion>;
    availablePrompts: SalesTrainerAudioScorePrompt[];
    isSubmitting: boolean;
    onSubmit: (
        payload: SalesTrainerUnitCreateRequest | SalesTrainerUnitUpdateRequest,
    ) => Promise<void> | void;
}

function isDraftStatus(status: SalesTrainerStatus | undefined): boolean {
    return status === undefined || status === "draft";
}

function getPromptId(unit?: SalesTrainerUnit | null): string {
    const rawPromptId = unit?.config?.audio?.scoring_prompt_id;
    return typeof rawPromptId === "string" ? rawPromptId : "";
}

function getPassThreshold(unit?: SalesTrainerUnit | null): string {
    const rawThreshold = unit?.config?.audio?.pass_threshold;
    return typeof rawThreshold === "number" && Number.isFinite(rawThreshold)
        ? String(rawThreshold)
        : "";
}

function getAudioPurpose(unit?: SalesTrainerUnit | null): string {
    const rawPurpose = unit?.config?.audio?.purpose;
    return typeof rawPurpose === "string" && rawPurpose.trim()
        ? rawPurpose
        : "general_audio_scoring";
}

function getPathConfig(unit?: SalesTrainerUnit | null): NonNullable<SalesTrainerUnit["config"]["path"]> {
    const config = unit?.config?.path;
    return config && typeof config === "object" && !Array.isArray(config) ? config : {};
}

function pathConfigString(
    config: NonNullable<SalesTrainerUnit["config"]["path"]>,
    key: string,
): string {
    const value = config[key];
    return typeof value === "string" ? value : "";
}

function pathConfigNumberText(
    config: NonNullable<SalesTrainerUnit["config"]["path"]>,
    key: string,
): string {
    const value = config[key];
    return typeof value === "number" && Number.isFinite(value) ? String(value) : "";
}

function listToText(values: unknown): string {
    return Array.isArray(values) ? values.map((item) => String(item)).join("\n") : "";
}

function textToList(text: string): string[] {
    return text
        .split(/[\n,，]/)
        .map((item) => item.trim())
        .filter(Boolean);
}

function guidanceTemplateText(
    config: NonNullable<SalesTrainerUnit["config"]["path"]>,
): string {
    const templates = config.guidance_templates;
    if (!templates || typeof templates !== "object" || Array.isArray(templates)) {
        return "";
    }
    return Object.entries(templates)
        .map(([key, value]) => `${key}: ${String(value)}`)
        .join("\n");
}

function textToGuidanceTemplates(text: string): Record<string, string> {
    return Object.fromEntries(
        text
            .split("\n")
            .map((line) => {
                const [key, ...rest] = line.split(":");
                return [key?.trim(), rest.join(":").trim()];
            })
            .filter(([key, value]) => key && value),
    );
}

function toCompletionRule(value: string): SalesTrainerCompletionRule {
    return value === "scored" || value === "submitted" ? value : "passed";
}

function parseOptionalNumber(
    value: string,
    label: string,
    options: { min?: number; max?: number; integer?: boolean } = {},
): number | undefined {
    const trimmed = value.trim();
    if (!trimmed) {
        return undefined;
    }
    const parsed = Number(trimmed);
    if (!Number.isFinite(parsed)) {
        throw new Error(`${label}必须是数字。`);
    }
    if (options.integer && !Number.isInteger(parsed)) {
        throw new Error(`${label}必须是整数。`);
    }
    if (options.min !== undefined && parsed < options.min) {
        throw new Error(`${label}不能小于 ${options.min}。`);
    }
    if (options.max !== undefined && parsed > options.max) {
        throw new Error(`${label}不能大于 ${options.max}。`);
    }
    return parsed;
}

export function SalesTrainerUnitForm({
    mode,
    initialUnit,
    availableQuestions,
    availablePrompts,
    isSubmitting,
    onSubmit,
}: SalesTrainerUnitFormProps) {
    const initialPathConfig = getPathConfig(initialUnit);
    const [name, setName] = useState(initialUnit?.name ?? "");
    const [description, setDescription] = useState(initialUnit?.description ?? "");
    const [unitType, setUnitType] = useState<SalesTrainerUnitType>(
        initialUnit?.unit_type ?? "quiz",
    );
    const [promptId, setPromptId] = useState(getPromptId(initialUnit));
    const [passThreshold, setPassThreshold] = useState(getPassThreshold(initialUnit));
    const [audioPurpose, setAudioPurpose] = useState(getAudioPurpose(initialUnit));
    const [pathEnabled, setPathEnabled] = useState(initialPathConfig.enabled === true);
    const [pathKey, setPathKey] = useState(pathConfigString(initialPathConfig, "path_key"));
    const [pathTitle, setPathTitle] = useState(pathConfigString(initialPathConfig, "path_title"));
    const [goalTitle, setGoalTitle] = useState(pathConfigString(initialPathConfig, "goal_title"));
    const [levelTitle, setLevelTitle] = useState(pathConfigString(initialPathConfig, "level_title"));
    const [levelDescription, setLevelDescription] = useState(pathConfigString(initialPathConfig, "level_description"));
    const [pathOrderIndex, setPathOrderIndex] = useState(pathConfigNumberText(initialPathConfig, "order_index"));
    const [unlockAfterUnitIds, setUnlockAfterUnitIds] = useState(listToText(initialPathConfig.unlock_after_unit_ids));
    const [completionRule, setCompletionRule] = useState<SalesTrainerCompletionRule | "">(
        pathConfigString(initialPathConfig, "completion_rule")
            ? toCompletionRule(pathConfigString(initialPathConfig, "completion_rule"))
            : "",
    );
    const [primaryActionLabel, setPrimaryActionLabel] = useState(pathConfigString(initialPathConfig, "primary_action_label"));
    const [retryActionLabel, setRetryActionLabel] = useState(pathConfigString(initialPathConfig, "retry_action_label"));
    const [reviewActionLabel, setReviewActionLabel] = useState(pathConfigString(initialPathConfig, "review_action_label"));
    const [guidanceTemplates, setGuidanceTemplates] = useState(guidanceTemplateText(initialPathConfig));
    const [selectedQuestions, setSelectedQuestions] = useState<QuestionSelection[]>(
        initialUnit?.questions.map((question) => ({
            question_id: question.question_id,
            order_index: question.order_index,
            points: question.points,
        })) ?? [],
    );
    const [error, setError] = useState<string | null>(null);

    const selectedQuestionIds = useMemo(
        () => new Set(selectedQuestions.map((question) => question.question_id)),
        [selectedQuestions],
    );
    const canEdit = isDraftStatus(initialUnit?.status);

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
                    ? {
                        ...question,
                        points: Math.max(1, Number(value) || 1),
                    }
                    : question,
            ),
        );
    }

    async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
        event.preventDefault();
        setError(null);

        if (!name.trim()) {
            setError("训练单元名称不能为空。");
            return;
        }

        if (!canEdit) {
            setError("只有 draft 状态的训练单元可以修改。");
            return;
        }

        if (unitType === "quiz" && selectedQuestions.length === 0) {
            setError("做题训练单元至少需要绑定一道题。");
            return;
        }

        if (unitType === "audio_scoring" && !promptId) {
            setError("音频评分训练单元必须绑定录音评分标准。");
            return;
        }

        if (unitType === "audio_scoring" && !audioPurpose.trim()) {
            setError("录音用途不能为空。");
            return;
        }

        let parsedPassThreshold: number | undefined;
        let parsedPathOrderIndex: number | undefined;
        try {
            parsedPassThreshold = parseOptionalNumber(passThreshold, "音频评分通过线", {
                min: 0,
                max: 100,
            });
            parsedPathOrderIndex = parseOptionalNumber(pathOrderIndex, "关卡顺序", {
                min: 1,
                integer: true,
            });
        } catch (parseError) {
            setError(parseError instanceof Error ? parseError.message : "训练单元配置不合法。");
            return;
        }

        const unlockAfterUnitIdList = textToList(unlockAfterUnitIds);
        const customGuidanceTemplates = textToGuidanceTemplates(guidanceTemplates);
        const pathConfig = pathEnabled
            ? {
                path: {
                    enabled: true,
                    ...(pathKey.trim() ? { path_key: pathKey.trim() } : {}),
                    ...(pathTitle.trim() ? { path_title: pathTitle.trim() } : {}),
                    ...(goalTitle.trim() ? { goal_title: goalTitle.trim() } : {}),
                    ...(levelTitle.trim() ? { level_title: levelTitle.trim() } : {}),
                    ...(levelDescription.trim()
                        ? { level_description: levelDescription.trim() }
                        : {}),
                    ...(parsedPathOrderIndex !== undefined
                        ? { order_index: parsedPathOrderIndex }
                        : {}),
                    ...(unlockAfterUnitIdList.length
                        ? { unlock_after_unit_ids: unlockAfterUnitIdList }
                        : {}),
                    ...(completionRule ? { completion_rule: completionRule } : {}),
                    ...(primaryActionLabel.trim()
                        ? { primary_action_label: primaryActionLabel.trim() }
                        : {}),
                    ...(retryActionLabel.trim()
                        ? { retry_action_label: retryActionLabel.trim() }
                        : {}),
                    ...(reviewActionLabel.trim()
                        ? { review_action_label: reviewActionLabel.trim() }
                        : {}),
                    ...(Object.keys(customGuidanceTemplates).length
                        ? { guidance_templates: customGuidanceTemplates }
                        : {}),
                },
            }
            : {};

        const payload = {
            name: name.trim(),
            description: description.trim() || null,
            unit_type: unitType,
            config: unitType === "audio_scoring"
                ? {
                    audio: {
                        scoring_prompt_id: promptId,
                        purpose: audioPurpose.trim(),
                        ...(parsedPassThreshold !== undefined
                            ? { pass_threshold: parsedPassThreshold }
                            : {}),
                    },
                    ...pathConfig,
                }
                : pathConfig,
            questions: unitType === "quiz" ? selectedQuestions : [],
        };

        await onSubmit(payload);
    }

    return (
        <form className="space-y-6" noValidate onSubmit={handleSubmit}>
            <GlassCard className="space-y-4 p-6">
                <div className="grid gap-4 md:grid-cols-2">
                    <div className="space-y-2">
                        <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-unit-name">
                            训练单元名称
                        </label>
                        <Input
                            id="sales-trainer-unit-name"
                            value={name}
                            onChange={(event) => setName(event.target.value)}
                            disabled={isSubmitting || !canEdit}
                            placeholder="例如：首轮客户需求问答"
                        />
                    </div>
                    <div className="space-y-2">
                        <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-unit-type">
                            训练类型
                        </label>
                        <select
                            id="sales-trainer-unit-type"
                            value={unitType}
                            onChange={(event) => setUnitType(event.target.value as SalesTrainerUnitType)}
                            disabled={isSubmitting || !canEdit || mode === "edit"}
                            className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm"
                        >
                            <option value="quiz">做题训练</option>
                            <option value="audio_scoring">录音评分</option>
                        </select>
                    </div>
                </div>

                <div className="space-y-2">
                    <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-unit-description">
                        描述
                    </label>
                    <textarea
                        id="sales-trainer-unit-description"
                        value={description}
                        onChange={(event) => setDescription(event.target.value)}
                        disabled={isSubmitting || !canEdit}
                        rows={4}
                        className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm"
                        placeholder="说明这个训练单元适合什么场景。"
                    />
                </div>
            </GlassCard>

            {unitType === "quiz" ? (
                <GlassCard className="space-y-4 p-6">
                    <div>
                        <h2 className="text-lg font-bold text-slate-900">绑定题目</h2>
                        <p className="mt-1 text-sm text-slate-500">
                            列表页不内嵌编辑，本页只负责选择已发布题目并设置分值。
                        </p>
                    </div>
                    <div className="space-y-3">
                        {availableQuestions.length === 0 ? (
                            <p className="text-sm text-slate-500">暂无已发布题目。</p>
                        ) : availableQuestions.map((question) => {
                            const selectedQuestion = selectedQuestions.find(
                                (item) => item.question_id === question.question_id,
                            );
                            return (
                                <div
                                    key={question.question_id}
                                    className="rounded-2xl border border-slate-100 bg-white p-4"
                                >
                                    <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                                        <label className="flex items-start gap-3 text-sm text-slate-700">
                                            <input
                                                type="checkbox"
                                                checked={selectedQuestionIds.has(question.question_id)}
                                                onChange={() => toggleQuestion(question.question_id)}
                                                disabled={isSubmitting || !canEdit}
                                            />
                                            <span>
                                                <span className="block font-semibold text-slate-900">
                                                    {question.title}
                                                </span>
                                                <span className="mt-1 block text-slate-500">
                                                    {question.stem}
                                                </span>
                                            </span>
                                        </label>
                                        <div className="flex items-center gap-2">
                                            <span className="text-xs text-slate-500">分值</span>
                                            <Input
                                                type="number"
                                                min={1}
                                                value={selectedQuestion?.points ?? 10}
                                                onChange={(event) => updateQuestionPoints(question.question_id, event.target.value)}
                                                disabled={!selectedQuestion || isSubmitting || !canEdit}
                                                className="w-24"
                                            />
                                        </div>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </GlassCard>
            ) : (
                <GlassCard className="space-y-4 p-6">
                    <div>
                        <h2 className="text-lg font-bold text-slate-900">录音评分配置</h2>
                        <p className="mt-1 text-sm text-slate-500">
                            时长上限、格式和大小限制由后端配置控制，前端这里不写死业务规则。
                        </p>
                    </div>
                    <div className="grid gap-4 md:grid-cols-2">
                        <div className="space-y-2">
                            <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-audio-purpose">
                                录音用途
                            </label>
                            <Input
                                id="sales-trainer-audio-purpose"
                                value={audioPurpose}
                                onChange={(event) => setAudioPurpose(event.target.value)}
                                disabled={isSubmitting || !canEdit}
                                placeholder="例如 ppt_pitch"
                            />
                        </div>
                        <div className="space-y-2">
                            <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-prompt-id">
                                录音评分标准
                            </label>
                            <select
                                id="sales-trainer-prompt-id"
                                value={promptId}
                                onChange={(event) => setPromptId(event.target.value)}
                                disabled={isSubmitting || !canEdit}
                                className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm"
                            >
                                <option value="">请选择已发布录音评分标准</option>
                                {availablePrompts
                                    .filter((prompt) => prompt.status === "published")
                                    .map((prompt) => (
                                        <option key={prompt.prompt_id} value={prompt.prompt_id}>
                                            {prompt.name}
                                        </option>
                                    ))}
                            </select>
                        </div>
                        <div className="space-y-2 md:col-span-2">
                            <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-pass-threshold">
                                通过线（可选）
                            </label>
                            <Input
                                id="sales-trainer-pass-threshold"
                                type="number"
                                min={0}
                                max={100}
                                value={passThreshold}
                                onChange={(event) => setPassThreshold(event.target.value)}
                                disabled={isSubmitting || !canEdit}
                                placeholder="留空使用后端默认通过线"
                            />
                        </div>
                    </div>
                </GlassCard>
            )}

            <GlassCard className="space-y-4 p-6">
                <div>
                    <h2 className="text-lg font-bold text-slate-900">闯关路径配置</h2>
                    <p className="mt-1 text-sm text-slate-500">
                        路径顺序、解锁条件和通关规则由这里配置，学员首页会按这些配置展示关卡。
                    </p>
                </div>
                <label className="flex items-center gap-2 text-sm text-slate-700">
                    <input
                        type="checkbox"
                        checked={pathEnabled}
                        onChange={(event) => setPathEnabled(event.target.checked)}
                        disabled={isSubmitting || !canEdit}
                    />
                    加入销售训练闯关路径
                </label>
                {pathEnabled ? (
                    <div className="grid gap-4 md:grid-cols-2">
                        <div className="space-y-2">
                            <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-path-key">路径标识</label>
                            <Input id="sales-trainer-path-key" value={pathKey} onChange={(event) => setPathKey(event.target.value)} disabled={isSubmitting || !canEdit} placeholder="留空使用默认路径" />
                        </div>
                        <div className="space-y-2">
                            <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-path-title">路径名称</label>
                            <Input id="sales-trainer-path-title" value={pathTitle} onChange={(event) => setPathTitle(event.target.value)} disabled={isSubmitting || !canEdit} placeholder="例如 新人销售闯关" />
                        </div>
                        <div className="space-y-2 md:col-span-2">
                            <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-goal-title">训练目标</label>
                            <Input id="sales-trainer-goal-title" value={goalTitle} onChange={(event) => setGoalTitle(event.target.value)} disabled={isSubmitting || !canEdit} placeholder="例如 掌握首次客户沟通" />
                        </div>
                        <div className="space-y-2">
                            <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-level-title">关卡名称</label>
                            <Input id="sales-trainer-level-title" value={levelTitle} onChange={(event) => setLevelTitle(event.target.value)} disabled={isSubmitting || !canEdit} placeholder={name || "例如 第一关：产品定位"} />
                        </div>
                        <div className="space-y-2">
                            <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-path-order">关卡顺序</label>
                            <Input id="sales-trainer-path-order" type="number" min={1} value={pathOrderIndex} onChange={(event) => setPathOrderIndex(event.target.value)} disabled={isSubmitting || !canEdit} placeholder="留空使用默认顺序" />
                        </div>
                        <div className="space-y-2 md:col-span-2">
                            <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-level-description">关卡说明</label>
                            <textarea
                                id="sales-trainer-level-description"
                                value={levelDescription}
                                onChange={(event) => setLevelDescription(event.target.value)}
                                disabled={isSubmitting || !canEdit}
                                rows={3}
                                className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm"
                            />
                        </div>
                        <div className="space-y-2">
                            <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-completion-rule">通关规则</label>
                            <select
                                id="sales-trainer-completion-rule"
                                value={completionRule}
                                onChange={(event) =>
                                    setCompletionRule(
                                        event.target.value
                                            ? toCompletionRule(event.target.value)
                                            : "",
                                    )
                                }
                                disabled={isSubmitting || !canEdit}
                                className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm"
                            >
                                <option value="">使用默认通关规则</option>
                                <option value="passed">必须通过</option>
                                <option value="scored">完成评分即可</option>
                                <option value="submitted">提交即可</option>
                            </select>
                        </div>
                        <div className="space-y-2">
                            <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-unlock-after">前置关卡 ID</label>
                            <textarea
                                id="sales-trainer-unlock-after"
                                value={unlockAfterUnitIds}
                                onChange={(event) => setUnlockAfterUnitIds(event.target.value)}
                                disabled={isSubmitting || !canEdit}
                                rows={3}
                                className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm"
                                placeholder="每行一个训练单元 ID"
                            />
                        </div>
                        <div className="space-y-2">
                            <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-primary-action">主按钮文案</label>
                            <Input id="sales-trainer-primary-action" value={primaryActionLabel} onChange={(event) => setPrimaryActionLabel(event.target.value)} disabled={isSubmitting || !canEdit} placeholder="留空使用默认文案" />
                        </div>
                        <div className="space-y-2">
                            <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-retry-action">重练按钮文案</label>
                            <Input id="sales-trainer-retry-action" value={retryActionLabel} onChange={(event) => setRetryActionLabel(event.target.value)} disabled={isSubmitting || !canEdit} placeholder="留空使用默认文案" />
                        </div>
                        <div className="space-y-2">
                            <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-review-action">查看结果按钮文案</label>
                            <Input id="sales-trainer-review-action" value={reviewActionLabel} onChange={(event) => setReviewActionLabel(event.target.value)} disabled={isSubmitting || !canEdit} placeholder="留空使用默认文案" />
                        </div>
                        <div className="space-y-2 md:col-span-2">
                            <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-guidance-templates">反馈文案模板</label>
                            <textarea
                                id="sales-trainer-guidance-templates"
                                value={guidanceTemplates}
                                onChange={(event) => setGuidanceTemplates(event.target.value)}
                                disabled={isSubmitting || !canEdit}
                                rows={5}
                                className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm"
                                placeholder="not_started: 本关还没有训练证据。"
                            />
                            <p className="text-xs text-slate-500">
                                可配置 locked、not_started、not_passed、not_scored、audio_improvement、start_level_reason、retry_level_reason、path_completed_reason。
                            </p>
                        </div>
                    </div>
                ) : null}
            </GlassCard>

            {error ? (
                <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                    {error}
                </div>
            ) : null}

            {!canEdit ? (
                <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                    当前状态为 {initialUnit?.status}，只能查看，不能继续修改。
                </div>
            ) : null}

            <div className="flex justify-end">
                <Button
                    type="submit"
                    disabled={isSubmitting || !canEdit}
                    className="rounded-full bg-slate-900 text-white"
                >
                    {isSubmitting ? "保存中..." : mode === "create" ? "创建训练单元" : "保存训练单元"}
                </Button>
            </div>
        </form>
    );
}
