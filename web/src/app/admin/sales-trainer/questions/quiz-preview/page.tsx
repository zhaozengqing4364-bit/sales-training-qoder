"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { usePathname } from "next/navigation";
import { AlertTriangle, BookOpenCheck, RefreshCcw } from "lucide-react";

import { AdminIndexShell, AdminPageHeader } from "@/components/admin/admin-layout-shells";
import { SalesTrainerAdminModuleNav } from "@/components/admin/sales-trainer/module-nav";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { useToast } from "@/components/ui/toast";
import { api, getApiErrorMessage } from "@/lib/api/client";
import { isSalesTrainerAdminPathAllowedForCapabilities } from "@/lib/sales-trainer/routes";
import type {
    BusinessEtiquetteLearningUnit,
    BusinessEtiquetteUnitQuiz,
    SalesTrainerAdminCapabilities,
} from "@/lib/api/types";

const QUESTION_TYPE_LABELS = {
    single_choice: "单选题",
    multiple_choice: "多选题",
    short_answer: "简答题",
} as const;

export default function BusinessEtiquetteQuizPreviewPage() {
    const pathname = usePathname();
    const { error: showToastError } = useToast();
    const [units, setUnits] = useState<BusinessEtiquetteLearningUnit[]>([]);
    const [selectedUnitKey, setSelectedUnitKey] = useState("");
    const [quiz, setQuiz] = useState<BusinessEtiquetteUnitQuiz | null>(null);
    const [loadError, setLoadError] = useState("");
    const [isLoadingUnits, setIsLoadingUnits] = useState(true);
    const [isLoadingPreview, setIsLoadingPreview] = useState(false);
    const [capabilities, setCapabilities] = useState<SalesTrainerAdminCapabilities | null>(null);
    const [capabilityError, setCapabilityError] = useState<string | null>(null);
    const [isCapabilityLoading, setIsCapabilityLoading] = useState(true);
    const canAccessQuestions = isSalesTrainerAdminPathAllowedForCapabilities(pathname, capabilities);

    const selectedUnit = useMemo(
        () => units.find((unit) => unit.unit_key === selectedUnitKey) ?? null,
        [selectedUnitKey, units],
    );

    const fetchQuizUnits = useCallback(async () => {
        const response = await api.admin.salesTrainer.getBusinessEtiquetteLearningUnits();
        return response.units.filter((unit) => unit.enabled && unit.require_quiz);
    }, []);

    const fetchPreview = useCallback(async (unitKey: string) => {
        return api.admin.salesTrainer.getBusinessEtiquetteUnitQuizPreview(unitKey);
    }, []);

    const loadUnits = useCallback(async () => {
        if (!canAccessQuestions) {
            return;
        }
        setIsLoadingUnits(true);
        setLoadError("");
        try {
            const quizUnits = await fetchQuizUnits();
            setUnits(quizUnits);
            setSelectedUnitKey((current) => (
                current && quizUnits.some((unit) => unit.unit_key === current)
                    ? current
                    : quizUnits[0]?.unit_key ?? ""
            ));
            setIsLoadingPreview(quizUnits.length > 0);
            if (!quizUnits.length) {
                setQuiz(null);
                setLoadError("当前没有启用且要求小测的商务礼仪小单元。");
            }
        } catch (error) {
            const message = getApiErrorMessage(error);
            setUnits([]);
            setQuiz(null);
            setSelectedUnitKey("");
            setLoadError(message);
            showToastError(message);
        } finally {
            setIsLoadingUnits(false);
        }
    }, [canAccessQuestions, fetchQuizUnits, showToastError]);

    useEffect(() => {
        let isCurrent = true;
        void api.admin.salesTrainer.getCapabilities()
            .then((result) => {
                if (!isCurrent) return;
                setCapabilities(result);
                setCapabilityError(null);
            })
            .catch((error) => {
                if (!isCurrent) return;
                setCapabilities(null);
                setCapabilityError(getApiErrorMessage(error));
            })
            .finally(() => {
                if (!isCurrent) return;
                setIsCapabilityLoading(false);
            });
        return () => {
            isCurrent = false;
        };
    }, []);

    useEffect(() => {
        let isCurrent = true;
        if (isCapabilityLoading) {
            return () => {
                isCurrent = false;
            };
        }
        if (!canAccessQuestions) {
            setUnits([]);
            setSelectedUnitKey("");
            setQuiz(null);
            setLoadError("");
            setIsLoadingUnits(false);
            setIsLoadingPreview(false);
            return () => {
                isCurrent = false;
            };
        }
        void fetchQuizUnits()
            .then((quizUnits) => {
                if (!isCurrent) return;
                setUnits(quizUnits);
                setSelectedUnitKey((current) => (
                    current && quizUnits.some((unit) => unit.unit_key === current)
                        ? current
                        : quizUnits[0]?.unit_key ?? ""
                ));
                setIsLoadingPreview(quizUnits.length > 0);
                if (!quizUnits.length) {
                    setQuiz(null);
                    setLoadError("当前没有启用且要求小测的商务礼仪小单元。");
                }
            })
            .catch((error) => {
                if (!isCurrent) return;
                const message = getApiErrorMessage(error);
                setUnits([]);
                setQuiz(null);
                setSelectedUnitKey("");
                setLoadError(message);
                showToastError(message);
            })
            .finally(() => {
                if (!isCurrent) return;
                setIsLoadingUnits(false);
            });

        return () => {
            isCurrent = false;
        };
    }, [canAccessQuestions, fetchQuizUnits, isCapabilityLoading, showToastError]);

    useEffect(() => {
        if (!canAccessQuestions || !selectedUnitKey) return;
        let isCurrent = true;

        void fetchPreview(selectedUnitKey)
            .then((response) => {
                if (!isCurrent) return;
                setQuiz(response);
            })
            .catch((error) => {
                if (!isCurrent) return;
                const message = getApiErrorMessage(error);
                setQuiz(null);
                setLoadError(message);
            })
            .finally(() => {
                if (!isCurrent) return;
                setIsLoadingPreview(false);
            });

        return () => {
            isCurrent = false;
        };
    }, [canAccessQuestions, fetchPreview, selectedUnitKey]);

    return (
        <AdminIndexShell
            className="space-y-5"
            header={(
                <div className="space-y-4">
                    <AdminPageHeader
                        title="小测组卷预览"
                        description="按学员端真实规则预览当前小单元会抽到哪些已发布题目；这里不保存、不提交、不占用学员作答次数。"
                        primaryAction={(
                            canAccessQuestions ? <Button variant="outline" onClick={() => void loadUnits()}>
                                <RefreshCcw className="mr-2 h-4 w-4" />
                                刷新
                            </Button> : null
                        )}
                    />
                    <SalesTrainerAdminModuleNav currentPath={pathname} capabilities={capabilities} />
                </div>
            )}
        >
            {isCapabilityLoading ? (
                <div className="rounded-2xl border border-slate-200 bg-white p-5 text-sm text-slate-500">
                    正在校验题库管理权限...
                </div>
            ) : capabilityError || !canAccessQuestions ? (
                <div className="rounded-2xl border border-amber-200 bg-amber-50 p-5 text-amber-800">
                    <div className="flex items-start gap-3">
                        <AlertTriangle className="mt-0.5 h-5 w-5" aria-hidden />
                        <div>
                            <h2 className="font-bold text-amber-950">题库管理权限不足</h2>
                            <p className="mt-1 text-sm leading-6">
                                当前页不会在权限未确认时加载小测预览。请联系管理员开通题库管理权限后重试。
                            </p>
                            {capabilityError ? (
                                <p className="mt-2 text-sm font-medium">{capabilityError}</p>
                            ) : null}
                        </div>
                    </div>
                </div>
            ) : (
            <div className="grid gap-5 xl:grid-cols-[340px_minmax(0,1fr)]">
                <aside className="space-y-5">
                    <GlassCard className="space-y-4 p-5">
                        <div className="flex items-center gap-3">
                            <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-slate-900 text-white">
                                <BookOpenCheck className="h-5 w-5" aria-hidden />
                            </div>
                            <div>
                                <h2 className="text-base font-bold text-slate-900">选择小单元</h2>
                                <p className="text-xs text-slate-500">只展示启用且要求小测的小单元</p>
                            </div>
                        </div>
                        <label className="space-y-2 text-sm font-medium text-slate-700">
                            <span>小单元</span>
                            <select
                                className="h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm"
                                disabled={isLoadingUnits || units.length === 0}
                                value={selectedUnitKey}
                                onChange={(event) => {
                                    setLoadError("");
                                    setIsLoadingPreview(Boolean(event.target.value));
                                    setSelectedUnitKey(event.target.value);
                                }}
                            >
                                {units.map((unit) => (
                                    <option key={unit.unit_key} value={unit.unit_key}>
                                        {unit.order_index}. {unit.title}
                                    </option>
                                ))}
                            </select>
                        </label>
                        {selectedUnit ? (
                            <div className="space-y-3 rounded-2xl bg-slate-50 p-4 text-sm text-slate-600">
                                <div>
                                    <span className="text-xs text-slate-400">能力点</span>
                                    <p className="mt-1 font-semibold text-slate-900">
                                        {selectedUnit.capabilities.map((item) => item.display_name).join("、") || "未配置"}
                                    </p>
                                </div>
                                <div>
                                    <span className="text-xs text-slate-400">原文章节</span>
                                    <p className="mt-1">
                                        {selectedUnit.source_chapter_orders.map((order) => `第 ${order} 章`).join("、") || "未绑定"}
                                    </p>
                                </div>
                            </div>
                        ) : null}
                    </GlassCard>

                    <GlassCard className="space-y-3 p-5">
                        <h2 className="text-base font-bold text-slate-900">抽题规则</h2>
                        <p className="text-sm leading-6 text-slate-500">
                            学员端小测只使用已发布、未安全拦截、范围为新人训练路径，且能力点命中当前小单元的题目。
                        </p>
                        <p className="text-sm leading-6 text-slate-500">
                            分类不会直接控制抽题；分类只帮助运营管理正式题目。
                        </p>
                    </GlassCard>
                </aside>

                <GlassCard className="overflow-hidden p-0">
                    <div className="flex items-center justify-between border-b border-slate-100 px-6 py-5">
                        <div>
                            <h2 className="text-lg font-bold text-slate-900">当前会抽到的题</h2>
                            <p className="mt-1 text-xs text-slate-500">
                                {quiz ? `${quiz.learning_unit_title} · ${quiz.question_count} 题` : "选择小单元后查看"}
                            </p>
                        </div>
                        <Badge className="bg-slate-100 text-slate-700">
                            {isLoadingPreview ? "加载中" : quiz ? `${quiz.questions.length} 题` : "未就绪"}
                        </Badge>
                    </div>
                    {loadError ? (
                        <div className="m-6 rounded-2xl border border-amber-100 bg-amber-50 px-5 py-4 text-sm leading-6 text-amber-800">
                            {loadError}
                        </div>
                    ) : null}
                    {!loadError && isLoadingPreview ? (
                        <div className="px-6 py-14 text-center text-sm text-slate-500">正在预览当前小测题目...</div>
                    ) : null}
                    {!loadError && !isLoadingPreview && quiz ? (
                        <div className="divide-y divide-slate-100">
                            {quiz.questions.map((question) => (
                                <article key={question.question_id} className="px-6 py-5">
                                    <div className="flex flex-wrap items-center gap-2">
                                        <Badge className="bg-slate-900 text-white">
                                            {QUESTION_TYPE_LABELS[question.question_type]}
                                        </Badge>
                                        <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
                                            {question.points} 分
                                        </span>
                                        {question.chapter_orders.map((order) => (
                                            <span key={order} className="rounded-full bg-blue-50 px-3 py-1 text-xs font-medium text-blue-700">
                                                第 {order} 章
                                            </span>
                                        ))}
                                    </div>
                                    <h3 className="mt-3 text-base font-bold text-slate-950">{question.title}</h3>
                                    <p className="mt-1 text-sm leading-6 text-slate-600">{question.stem}</p>
                                    <div className="mt-3 flex flex-wrap gap-2">
                                        {question.capability_keys.map((key) => (
                                            <span key={key} className="rounded-full bg-white px-3 py-1 text-xs text-slate-500 ring-1 ring-slate-200">
                                                {key}
                                            </span>
                                        ))}
                                    </div>
                                </article>
                            ))}
                        </div>
                    ) : null}
                    {!loadError && !isLoadingPreview && !quiz ? (
                        <div className="px-6 py-14 text-center text-sm text-slate-500">暂无可预览的小测题目</div>
                    ) : null}
                </GlassCard>
            </div>
            )}
        </AdminIndexShell>
    );
}
