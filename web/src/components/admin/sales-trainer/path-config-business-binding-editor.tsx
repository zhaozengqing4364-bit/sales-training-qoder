"use client";

import Link from "next/link";

import type {
    BusinessEtiquetteTrainingUnitConfig,
    NewcomerArticle,
    NewcomerExamPaper,
} from "@/lib/api/types";
import {
    parseChapterOrders,
    serializeChapterOrders,
} from "@/lib/sales-trainer/business-etiquette-units";
import type { PathBusinessBindingValue } from "@/lib/sales-trainer/path-config-editing";

interface PathConfigBusinessBindingEditorProps {
    readonly articles: readonly NewcomerArticle[];
    readonly disabled: boolean;
    readonly moduleTitle: string;
    readonly onChange: (value: PathBusinessBindingValue) => void;
    readonly papers: readonly NewcomerExamPaper[];
    readonly value: PathBusinessBindingValue;
}

type QuizQuestionTypeWeightKey = "single_choice" | "multiple_choice" | "short_answer";

export function PathConfigBusinessBindingEditor({
    articles,
    disabled,
    moduleTitle,
    onChange,
    papers,
    value,
}: PathConfigBusinessBindingEditorProps) {
    const publishedPapers = papers.filter((paper) => paper.status === "published");
    function updateLearningUnit(
        unitKey: string,
        patch: Partial<BusinessEtiquetteTrainingUnitConfig>,
    ) {
        onChange({
            ...value,
            learningUnits: value.learningUnits.map((unit) => (
                unit.unit_key === unitKey ? { ...unit, ...patch } : unit
            )),
        });
    }

    function updateQuestionTypeWeight(
        unit: BusinessEtiquetteTrainingUnitConfig,
        questionType: QuizQuestionTypeWeightKey,
        rawValue: string,
    ) {
        const nextWeights = { ...unit.quiz_question_type_weights };
        if (rawValue.trim() === "") {
            delete nextWeights[questionType];
        } else {
            nextWeights[questionType] = Math.max(0, Number(rawValue) || 0);
        }
        updateLearningUnit(unit.unit_key, {
            quiz_question_type_weights: nextWeights,
        });
    }

    function parseKeyList(value: string): string[] {
        return value
            .split(",")
            .map((item) => item.trim())
            .filter(Boolean);
    }

    function aiCoachRequiredCapabilityKeys(
        unit: BusinessEtiquetteTrainingUnitConfig,
    ): readonly string[] {
        return unit.ai_coach_required_capability_keys?.length
            ? unit.ai_coach_required_capability_keys
            : unit.capability_keys;
    }

    function aiCoachRemediationChapterOrders(
        unit: BusinessEtiquetteTrainingUnitConfig,
    ): readonly number[] {
        return unit.ai_coach_remediation_chapter_orders?.length
            ? unit.ai_coach_remediation_chapter_orders
            : unit.source_chapter_orders;
    }

    return (
        <div className="space-y-5 rounded-2xl border border-blue-100 bg-white p-4">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                <div>
                    <p className="text-sm font-black text-slate-900">在配置中心直接绑定学习与考试</p>
                    <p className="mt-1 text-sm text-slate-500">
                        学员端按这里绑定的专题内容学习，再进入绑定考卷考试。
                    </p>
                </div>
                <div className="flex gap-3 text-sm font-semibold text-blue-700">
                    <Link href="/admin/sales-trainer/learning-topics" className="underline">
                        管理专题内容
                    </Link>
                    <Link href="/admin/sales-trainer/learning-topics/papers" className="underline">
                        管理考卷
                    </Link>
                </div>
            </div>
            <div className="mt-4 grid gap-3 md:grid-cols-2">
                <div className="space-y-2">
                    <label className="text-sm font-medium text-slate-700" htmlFor="business-skills-learning-content">
                        专题内容（{moduleTitle}）
                    </label>
                    <select
                        id="business-skills-learning-content"
                        value={value.learningContentId}
                        onChange={(event) => onChange({ ...value, learningContentId: event.target.value })}
                        disabled={disabled}
                        className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm"
                    >
                        <option value="">请选择已发布专题内容</option>
                        {articles.map((article) => (
                            <option key={article.learning_content_id} value={article.learning_content_id}>
                                {article.title} · {article.chapters.length} 节
                            </option>
                        ))}
                    </select>
                </div>
                <div className="space-y-2">
                    <label className="text-sm font-medium text-slate-700" htmlFor="business-skills-paper">
                        考试考卷（{moduleTitle}）
                    </label>
                    <select
                        id="business-skills-paper"
                        value={value.examPaperId}
                        onChange={(event) => onChange({ ...value, examPaperId: event.target.value })}
                        disabled={disabled}
                        className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm"
                    >
                        <option value="">请选择已发布考卷</option>
                        {publishedPapers.map((paper) => (
                            <option key={paper.paper_id} value={paper.paper_id}>
                                {paper.title} · {paper.questions.length} 题
                            </option>
                        ))}
                    </select>
                </div>
            </div>

            <div className="border-t border-slate-100 pt-4">
                <div className="flex flex-col gap-1">
                    <p className="text-sm font-black text-slate-900">当前专题的训练小单元</p>
                    <p className="text-sm text-slate-500">
                        小单元顺序、标题、说明、章节绑定和开放规则会保存到新人训练路径待发布修订。
                    </p>
                </div>
                <div className="mt-4 space-y-3">
                    {value.learningUnits
                        .slice()
                        .sort((left, right) => left.order_index - right.order_index)
                        .map((unit) => (
                            <div
                                key={unit.unit_key}
                                className="rounded-2xl border border-slate-100 bg-slate-50 p-4"
                            >
                                <div className="grid gap-3 lg:grid-cols-[80px_1fr_1fr]">
                                    <div className="space-y-2">
                                        <label
                                            className="text-xs font-semibold text-slate-500"
                                            htmlFor={`${unit.unit_key}-order`}
                                        >
                                            顺序
                                        </label>
                                        <input
                                            id={`${unit.unit_key}-order`}
                                            className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm"
                                            type="number"
                                            min={1}
                                            value={unit.order_index}
                                            disabled={disabled}
                                            onChange={(event) => updateLearningUnit(unit.unit_key, {
                                                order_index: Number(event.target.value) || unit.order_index,
                                            })}
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <label
                                            className="text-xs font-semibold text-slate-500"
                                            htmlFor={`${unit.unit_key}-title`}
                                        >
                                            标题
                                        </label>
                                        <input
                                            id={`${unit.unit_key}-title`}
                                            className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm"
                                            value={unit.title}
                                            disabled={disabled}
                                            onChange={(event) => updateLearningUnit(unit.unit_key, {
                                                title: event.target.value,
                                            })}
                                        />
                                    </div>
                                    <label className="flex items-center gap-2 pt-6 text-sm font-semibold text-slate-700">
                                        <input
                                            type="checkbox"
                                            checked={unit.enabled}
                                            disabled={disabled}
                                            onChange={(event) => updateLearningUnit(unit.unit_key, {
                                                enabled: event.target.checked,
                                            })}
                                        />
                                        启用
                                    </label>
                                </div>
                                <div className="mt-3 grid gap-3 lg:grid-cols-2">
                                    <div className="space-y-2">
                                        <label
                                            className="text-xs font-semibold text-slate-500"
                                            htmlFor={`${unit.unit_key}-description`}
                                        >
                                            说明
                                        </label>
                                        <textarea
                                            id={`${unit.unit_key}-description`}
                                            className="min-h-20 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm"
                                            value={unit.description ?? ""}
                                            disabled={disabled}
                                            onChange={(event) => updateLearningUnit(unit.unit_key, {
                                                description: event.target.value || null,
                                            })}
                                        />
                                    </div>
                                    <div className="space-y-3">
                                        <div className="space-y-2">
                                            <label
                                                className="text-xs font-semibold text-slate-500"
                                                htmlFor={`${unit.unit_key}-chapters`}
                                            >
                                                覆盖原文章节序号
                                            </label>
                                            <input
                                                id={`${unit.unit_key}-chapters`}
                                                className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm"
                                                value={serializeChapterOrders(unit.source_chapter_orders)}
                                                disabled={disabled}
                                                onChange={(event) => updateLearningUnit(unit.unit_key, {
                                                    source_chapter_orders: parseChapterOrders(event.target.value),
                                                })}
                                            />
                                        </div>
                                        <div className="space-y-2">
                                            <label
                                                className="text-xs font-semibold text-slate-500"
                                                htmlFor={`${unit.unit_key}-unlock`}
                                            >
                                                前置小单元 key
                                            </label>
                                            <input
                                                id={`${unit.unit_key}-unlock`}
                                                className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm"
                                                value={unit.unlock_after_unit_keys.join(", ")}
                                                disabled={disabled}
                                                onChange={(event) => updateLearningUnit(unit.unit_key, {
                                                    unlock_after_unit_keys: event.target.value
                                                        .split(",")
                                                        .map((item) => item.trim())
                                                        .filter(Boolean),
                                                })}
                                            />
                                        </div>
                                    </div>
                                </div>
                                <div className="mt-3 grid gap-2 text-sm text-slate-700 sm:grid-cols-2 lg:grid-cols-4">
                                    <label className="flex items-center gap-2">
                                        <input
                                            type="checkbox"
                                            checked={unit.require_reading}
                                            disabled={disabled}
                                            onChange={(event) => updateLearningUnit(unit.unit_key, {
                                                require_reading: event.target.checked,
                                            })}
                                        />
                                        要求阅读
                                    </label>
                                    <label className="flex items-center gap-2">
                                        <input
                                            type="checkbox"
                                            checked={unit.require_quiz}
                                            disabled={disabled}
                                            onChange={(event) => updateLearningUnit(unit.unit_key, {
                                                require_quiz: event.target.checked,
                                            })}
                                        />
                                        要求小测
                                    </label>
                                    <label className="flex items-center gap-2">
                                        <input
                                            type="checkbox"
                                            checked={unit.require_ai_coach}
                                            disabled={disabled}
                                            onChange={(event) => updateLearningUnit(unit.unit_key, {
                                                require_ai_coach: event.target.checked,
                                            })}
                                        />
                                        要求 AI 教练
                                    </label>
                                    <label className="flex items-center gap-2">
                                        <input
                                            type="checkbox"
                                            checked={unit.block_next_until_complete}
                                            disabled={disabled}
                                            onChange={(event) => updateLearningUnit(unit.unit_key, {
                                                block_next_until_complete: event.target.checked,
                                            })}
                                        />
                                        未完成阻断后续
                                    </label>
                                    <label className="flex items-center gap-2">
                                        <input
                                            type="checkbox"
                                            checked={unit.allow_skip_reading}
                                            disabled={disabled}
                                            onChange={(event) => updateLearningUnit(unit.unit_key, {
                                                allow_skip_reading: event.target.checked,
                                            })}
                                        />
                                        允许跳过阅读
                                    </label>
                                </div>
                                <div className="mt-3 grid gap-3 lg:grid-cols-4">
                                    <div className="space-y-2">
                                        <label
                                            className="text-xs font-semibold text-slate-500"
                                            htmlFor={`${unit.unit_key}-quiz-count`}
                                        >
                                            小测题量
                                        </label>
                                        <input
                                            id={`${unit.unit_key}-quiz-count`}
                                            className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm"
                                            type="number"
                                            min={1}
                                            max={50}
                                            value={unit.quiz_question_count}
                                            disabled={disabled}
                                            onChange={(event) => updateLearningUnit(unit.unit_key, {
                                                quiz_question_count: Number(event.target.value) || unit.quiz_question_count,
                                            })}
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <label
                                            className="text-xs font-semibold text-slate-500"
                                            htmlFor={`${unit.unit_key}-quiz-threshold`}
                                        >
                                            小测通过线
                                        </label>
                                        <input
                                            id={`${unit.unit_key}-quiz-threshold`}
                                            className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm"
                                            type="number"
                                            min={0}
                                            max={100}
                                            value={unit.quiz_pass_threshold ?? ""}
                                            disabled={disabled}
                                            onChange={(event) => updateLearningUnit(unit.unit_key, {
                                                quiz_pass_threshold: event.target.value
                                                    ? Number(event.target.value)
                                                    : null,
                                            })}
                                        />
                                    </div>
                                    <label className="flex items-center gap-2 pt-6 text-sm font-semibold text-slate-700">
                                        <input
                                            type="checkbox"
                                            checked={unit.quiz_allow_retake}
                                            disabled={disabled}
                                            onChange={(event) => updateLearningUnit(unit.unit_key, {
                                                quiz_allow_retake: event.target.checked,
                                            })}
                                        />
                                        允许重测
                                    </label>
                                    <div className="space-y-2">
                                        <label
                                            className="text-xs font-semibold text-slate-500"
                                            htmlFor={`${unit.unit_key}-quiz-max-attempts`}
                                        >
                                            最大次数
                                        </label>
                                        <input
                                            id={`${unit.unit_key}-quiz-max-attempts`}
                                            className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm"
                                            type="number"
                                            min={1}
                                            value={unit.quiz_max_attempts ?? ""}
                                            disabled={disabled}
                                            onChange={(event) => updateLearningUnit(unit.unit_key, {
                                                quiz_max_attempts: event.target.value
                                                    ? Number(event.target.value)
                                                    : null,
                                            })}
                                        />
                                    </div>
                                </div>
                                <div className="mt-3 grid gap-3 lg:grid-cols-3">
                                    <div className="space-y-2">
                                        <label
                                            className="text-xs font-semibold text-slate-500"
                                            htmlFor={`${unit.unit_key}-single-weight`}
                                        >
                                            单选题权重
                                        </label>
                                        <input
                                            id={`${unit.unit_key}-single-weight`}
                                            className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm"
                                            type="number"
                                            min={0}
                                            value={unit.quiz_question_type_weights.single_choice ?? ""}
                                            disabled={disabled}
                                            onChange={(event) => updateQuestionTypeWeight(
                                                unit,
                                                "single_choice",
                                                event.target.value,
                                            )}
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <label
                                            className="text-xs font-semibold text-slate-500"
                                            htmlFor={`${unit.unit_key}-multiple-weight`}
                                        >
                                            多选题权重
                                        </label>
                                        <input
                                            id={`${unit.unit_key}-multiple-weight`}
                                            className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm"
                                            type="number"
                                            min={0}
                                            value={unit.quiz_question_type_weights.multiple_choice ?? ""}
                                            disabled={disabled}
                                            onChange={(event) => updateQuestionTypeWeight(
                                                unit,
                                                "multiple_choice",
                                                event.target.value,
                                            )}
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <label
                                            className="text-xs font-semibold text-slate-500"
                                            htmlFor={`${unit.unit_key}-short-answer-weight`}
                                        >
                                            简答题权重
                                        </label>
                                        <input
                                            id={`${unit.unit_key}-short-answer-weight`}
                                            className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm"
                                            type="number"
                                            min={0}
                                            value={unit.quiz_question_type_weights.short_answer ?? ""}
                                            disabled={disabled}
                                            onChange={(event) => updateQuestionTypeWeight(
                                                unit,
                                                "short_answer",
                                                event.target.value,
                                            )}
                                        />
                                    </div>
                                </div>
                                <div className="mt-4 rounded-2xl border border-emerald-100 bg-white p-3">
                                    <div className="flex flex-col gap-1">
                                        <p className="text-xs font-black text-slate-900">
                                            AI 教练达标规则
                                        </p>
                                        <p className="text-xs leading-relaxed text-slate-500">
                                            达标等级、补救次数和阻断规则会随路径发布冻结到训练局。
                                        </p>
                                    </div>
                                    <div className="mt-3 grid gap-3 lg:grid-cols-3">
                                        <div className="space-y-2">
                                            <label
                                                className="text-xs font-semibold text-slate-500"
                                                htmlFor={`${unit.unit_key}-ai-required-capabilities`}
                                            >
                                                必达能力点 key
                                            </label>
                                            <input
                                                id={`${unit.unit_key}-ai-required-capabilities`}
                                                className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm"
                                                value={aiCoachRequiredCapabilityKeys(unit).join(", ")}
                                                disabled={disabled}
                                                onChange={(event) => updateLearningUnit(unit.unit_key, {
                                                    ai_coach_required_capability_keys: parseKeyList(event.target.value),
                                                })}
                                            />
                                        </div>
                                        <div className="space-y-2">
                                            <label
                                                className="text-xs font-semibold text-slate-500"
                                                htmlFor={`${unit.unit_key}-ai-pass-level`}
                                            >
                                                达标等级 key
                                            </label>
                                            <input
                                                id={`${unit.unit_key}-ai-pass-level`}
                                                className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm"
                                                value={unit.ai_coach_pass_mastery_level_key ?? "basic_mastery"}
                                                disabled={disabled}
                                                onChange={(event) => updateLearningUnit(unit.unit_key, {
                                                    ai_coach_pass_mastery_level_key: event.target.value,
                                                })}
                                            />
                                        </div>
                                        <div className="space-y-2">
                                            <label
                                                className="text-xs font-semibold text-slate-500"
                                                htmlFor={`${unit.unit_key}-ai-ready-level`}
                                            >
                                                可上场等级 key
                                            </label>
                                            <input
                                                id={`${unit.unit_key}-ai-ready-level`}
                                                className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm"
                                                value={unit.ai_coach_ready_mastery_level_key ?? "field_ready"}
                                                disabled={disabled}
                                                onChange={(event) => updateLearningUnit(unit.unit_key, {
                                                    ai_coach_ready_mastery_level_key: event.target.value,
                                                })}
                                            />
                                        </div>
                                    </div>
                                    <div className="mt-3 grid gap-3 lg:grid-cols-3">
                                        <div className="space-y-2">
                                            <label
                                                className="text-xs font-semibold text-slate-500"
                                                htmlFor={`${unit.unit_key}-ai-remediation-attempts`}
                                            >
                                                最大补救次数
                                            </label>
                                            <input
                                                id={`${unit.unit_key}-ai-remediation-attempts`}
                                                className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm"
                                                type="number"
                                                min={1}
                                                max={20}
                                                value={unit.ai_coach_max_remediation_attempts ?? 3}
                                                disabled={disabled}
                                                onChange={(event) => updateLearningUnit(unit.unit_key, {
                                                    ai_coach_max_remediation_attempts: Number(event.target.value) || 3,
                                                })}
                                            />
                                        </div>
                                        <div className="space-y-2 lg:col-span-2">
                                            <label
                                                className="text-xs font-semibold text-slate-500"
                                                htmlFor={`${unit.unit_key}-ai-remediation-chapters`}
                                            >
                                                补救回看章节序号
                                            </label>
                                            <input
                                                id={`${unit.unit_key}-ai-remediation-chapters`}
                                                className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm"
                                                value={serializeChapterOrders(aiCoachRemediationChapterOrders(unit))}
                                                disabled={disabled}
                                                onChange={(event) => updateLearningUnit(unit.unit_key, {
                                                    ai_coach_remediation_chapter_orders: parseChapterOrders(event.target.value),
                                                })}
                                            />
                                        </div>
                                    </div>
                                    <div className="mt-3 grid gap-2 text-sm font-semibold text-slate-700 sm:grid-cols-2">
                                        <label className="flex items-center gap-2">
                                            <input
                                                type="checkbox"
                                                checked={unit.ai_coach_manual_review_after_max_attempts ?? true}
                                                disabled={disabled}
                                                onChange={(event) => updateLearningUnit(unit.unit_key, {
                                                    ai_coach_manual_review_after_max_attempts: event.target.checked,
                                                })}
                                            />
                                            补救超限后进入人工复盘
                                        </label>
                                        <label className="flex items-center gap-2">
                                            <input
                                                type="checkbox"
                                                checked={unit.ai_coach_block_next_until_passed ?? true}
                                                disabled={disabled}
                                                onChange={(event) => updateLearningUnit(unit.unit_key, {
                                                    ai_coach_block_next_until_passed: event.target.checked,
                                                })}
                                            />
                                            AI 教练未达标阻断下一单元
                                        </label>
                                    </div>
                                </div>
                            </div>
                        ))}
                </div>
            </div>
        </div>
    );
}
