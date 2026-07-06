"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { AlertTriangle, Eye, Plus, RefreshCw, Sparkles } from "lucide-react";

import { AdminIndexShell, AdminPageHeader } from "@/components/admin/admin-layout-shells";
import { SalesTrainerAdminModuleNav } from "@/components/admin/sales-trainer/module-nav";
import { QuestionGovernanceWorkspace } from "@/components/admin/sales-trainer/question-governance-workspace";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useToast } from "@/components/ui/toast";
import { api, getApiErrorMessage } from "@/lib/api/client";
import { NEWCOMER_QUESTION_TAG } from "@/lib/sales-trainer/question-scope";
import { isSalesTrainerAdminPathAllowedForCapabilities } from "@/lib/sales-trainer/routes";
import type {
    SalesTrainerAdminCapabilities,
    SalesTrainerQuestion,
    SalesTrainerQuestionCategory,
} from "@/lib/api/types";

type ConfirmState =
    | { type: "publish"; question: SalesTrainerQuestion }
    | { type: "archive"; question: SalesTrainerQuestion }
    | null;

export default function SalesTrainerQuestionsPage() {
    const pathname = usePathname();
    const router = useRouter();
    const { error: showToastError, success: showToastSuccess } = useToast();
    const [questions, setQuestions] = useState<SalesTrainerQuestion[]>([]);
    const [categories, setCategories] = useState<SalesTrainerQuestionCategory[]>([]);
    const [categoryId, setCategoryId] = useState("");
    const [status, setStatus] = useState("");
    const [difficulty, setDifficulty] = useState("");
    const [tag, setTag] = useState(NEWCOMER_QUESTION_TAG);
    const [isLoading, setIsLoading] = useState(true);
    const [isOperating, setIsOperating] = useState(false);
    const [loadError, setLoadError] = useState<string | null>(null);
    const [confirmState, setConfirmState] = useState<ConfirmState>(null);
    const [capabilities, setCapabilities] = useState<SalesTrainerAdminCapabilities | null>(null);
    const [capabilityError, setCapabilityError] = useState<string | null>(null);
    const [isCapabilityLoading, setIsCapabilityLoading] = useState(true);
    const canAccessQuestions = isSalesTrainerAdminPathAllowedForCapabilities(pathname, capabilities);

    const categoryNameById = useMemo(
        () => new Map(categories.map((category) => [category.category_id, category.name])),
        [categories],
    );
    const publishedCount = useMemo(
        () => questions.filter((question) => question.status === "published").length,
        [questions],
    );
    const aiScoredCount = useMemo(
        () => questions.filter((question) => Boolean(question.ai_scoring)).length,
        [questions],
    );
    const scopedCategories = useMemo(() => {
        const visibleCategoryIds = new Set(questions.map((question) => question.category_id));
        return categories.filter((category) => (
            visibleCategoryIds.has(category.category_id) || category.category_id === categoryId
        ));
    }, [categories, categoryId, questions]);

    const fetchQuestionData = useCallback(async () => {
        const [questionResult, categoryResult] = await Promise.all([
            api.admin.salesTrainer.listQuestions({
                category_id: categoryId || undefined,
                status: status || undefined,
                difficulty: difficulty || undefined,
                tag: tag || undefined,
            }),
            api.admin.salesTrainer.listQuestionCategories(),
        ]);

        return {
            categories: categoryResult.items,
            questions: questionResult.items,
        };
    }, [categoryId, difficulty, status, tag]);

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
            setQuestions([]);
            setCategories([]);
            setLoadError(null);
            setIsLoading(false);
            return () => {
                isCurrent = false;
            };
        }

        void fetchQuestionData()
            .then((result) => {
                if (!isCurrent) return;
                setQuestions(result.questions);
                setCategories(result.categories);
                setLoadError(null);
            })
            .catch((loadError) => {
                if (!isCurrent) return;
                const message = getApiErrorMessage(loadError);
                setLoadError(message);
                showToastError(message);
            })
            .finally(() => {
                if (!isCurrent) return;
                setIsLoading(false);
            });

        return () => {
            isCurrent = false;
        };
    }, [canAccessQuestions, fetchQuestionData, isCapabilityLoading, showToastError]);

    const loadData = useCallback(async () => {
        if (!canAccessQuestions) {
            return;
        }
        setIsLoading(true);
        setLoadError(null);
        try {
            const result = await fetchQuestionData();
            setQuestions(result.questions);
            setCategories(result.categories);
            setLoadError(null);
        } catch (loadError) {
            const message = getApiErrorMessage(loadError);
            setLoadError(message);
            showToastError(message);
        } finally {
            setIsLoading(false);
        }
    }, [canAccessQuestions, fetchQuestionData, showToastError]);

    async function handleConfirm() {
        if (!confirmState) return;
        setIsOperating(true);
        try {
            if (confirmState.type === "publish") {
                await api.admin.salesTrainer.publishQuestion(confirmState.question.question_id);
                showToastSuccess("题目已发布并对后续组卷生效");
            } else {
                await api.admin.salesTrainer.archiveQuestion(confirmState.question.question_id);
                showToastSuccess("题目已归档");
            }
            setConfirmState(null);
            await loadData();
        } catch (operateError) {
            showToastError(getApiErrorMessage(operateError));
        } finally {
            setIsOperating(false);
        }
    }

    return (
        <AdminIndexShell
            className="space-y-5"
            header={(
                <div className="space-y-4">
                    <AdminPageHeader
                        title="正式题目库"
                        description="AI 草稿审核后会进入这里；只有发布后的题目才会被学员端小测抽取。"
                        primaryAction={canAccessQuestions ? (
                            <div className="flex flex-wrap gap-2">
                                <Button variant="outline" onClick={() => router.push("/admin/sales-trainer/questions/drafts")}>
                                    <Sparkles className="mr-2 h-4 w-4" />
                                    AI 出题审核
                                </Button>
                                <Button variant="outline" onClick={() => router.push("/admin/sales-trainer/questions/quiz-preview")}>
                                    <Eye className="mr-2 h-4 w-4" />
                                    小测预览
                                </Button>
                                <Button onClick={() => router.push("/admin/sales-trainer/questions/new")}>
                                    <Plus className="mr-2 h-4 w-4" />
                                    新建题目
                                </Button>
                            </div>
                        ) : null}
                    />
                    <SalesTrainerAdminModuleNav currentPath={pathname} capabilities={capabilities} />
                </div>
            )}
        >
            <ConfirmDialog
                open={Boolean(confirmState)}
                onOpenChange={(open) => !open && setConfirmState(null)}
                title={confirmState?.type === "publish" ? "发布题目" : "归档题目"}
                description={confirmState?.type === "publish"
                    ? "发布后只影响后续组卷和后续学员作答；已提交考试记录继续保留当时题目快照。"
                    : "归档后不再用于后续组卷，历史考试记录和审计记录继续保留。"}
                confirmText={confirmState?.type === "publish" ? "确认发布" : "确认归档"}
                onConfirm={() => void handleConfirm()}
                isLoading={isOperating}
            />

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
                                当前页不会在权限未确认时展示题目写入入口。请联系管理员开通题库管理权限后重试。
                            </p>
                            {capabilityError ? (
                                <p className="mt-2 text-sm font-medium">{capabilityError}</p>
                            ) : null}
                        </div>
                    </div>
                </div>
            ) : loadError ? (
                <div className="rounded-2xl border border-amber-200 bg-amber-50 p-5 text-amber-800">
                    <div className="flex items-start gap-3">
                        <AlertTriangle className="mt-0.5 h-5 w-5" aria-hidden />
                        <div className="space-y-3">
                            <div>
                                <h2 className="font-bold text-amber-950">题目加载失败</h2>
                                <p className="mt-1 text-sm leading-6">
                                    当前页不会把接口异常伪装成空题库。请核对权限、筛选条件或后端服务状态后重试。
                                </p>
                                <p className="mt-2 text-sm font-medium">{loadError}</p>
                            </div>
                            <Button
                                type="button"
                                variant="outline"
                                className="bg-white"
                                onClick={() => void loadData()}
                            >
                                <RefreshCw className="mr-2 h-4 w-4" />
                                重新加载题目
                            </Button>
                        </div>
                    </div>
                </div>
            ) : (
                <QuestionGovernanceWorkspace
                    aiScoredCount={aiScoredCount}
                    categories={scopedCategories}
                    categoryId={categoryId}
                    categoryNameById={categoryNameById}
                    difficulty={difficulty}
                    isLoading={isLoading}
                    onArchive={(question) => setConfirmState({ type: "archive", question })}
                    onCategoryChange={setCategoryId}
                    onDifficultyChange={setDifficulty}
                    onEdit={(questionId) => router.push(`/admin/sales-trainer/questions/${questionId}/edit`)}
                    onPublish={(question) => setConfirmState({ type: "publish", question })}
                    onRefresh={() => void loadData()}
                    onStatusChange={setStatus}
                    onTagChange={setTag}
                    publishedCount={publishedCount}
                    questions={questions}
                    status={status}
                    tag={tag}
                />
            )}
        </AdminIndexShell>
    );
}
