"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";

import { AdminIndexShell, AdminPageHeader } from "@/components/admin/admin-layout-shells";
import { SalesTrainerAdminModuleNav } from "@/components/admin/sales-trainer/module-nav";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { Input } from "@/components/ui/input";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type { SalesTrainerAudioScoreResult, SalesTrainerQuizAttempt } from "@/lib/api/types";

function formatLearner(attempt: SalesTrainerQuizAttempt): string {
    const primary = attempt.user_name || attempt.user_email || attempt.user_id;
    const secondary = attempt.user_department || (
        attempt.user_email && attempt.user_email !== primary ? attempt.user_email : null
    );
    return secondary ? `${primary} · ${secondary}` : primary;
}

function getQuizResultLabel(attempt: SalesTrainerQuizAttempt): string {
    if (attempt.total_score == null || attempt.max_score == null) {
        return "待判分";
    }
    if (attempt.passed === true) {
        return "通过";
    }
    if (attempt.passed === false) {
        return "未通过";
    }
    return "已计分";
}

function getQuizResultVariant(attempt: SalesTrainerQuizAttempt): "green" | "orange" | "secondary" {
    if (attempt.passed === true) {
        return "green";
    }
    if (attempt.total_score == null || attempt.max_score == null) {
        return "orange";
    }
    return "secondary";
}

function getAudioScoreLabel(item: SalesTrainerAudioScoreResult): string {
    if (item.error_code) {
        return item.error_code;
    }
    if (item.passed === true) {
        return "通过";
    }
    if (item.passed === false) {
        return "未通过";
    }
    return "待确认";
}

function getAudioScoreVariant(item: SalesTrainerAudioScoreResult): "green" | "orange" | "red" | "secondary" {
    if (item.error_code) {
        return "red";
    }
    if (item.passed === true) {
        return "green";
    }
    if (item.passed === false) {
        return "orange";
    }
    return "secondary";
}

export default function SalesTrainerScoreResultsPage() {
    const pathname = usePathname();
    const router = useRouter();
    const [quizItems, setQuizItems] = useState<SalesTrainerQuizAttempt[]>([]);
    const [scoreItems, setScoreItems] = useState<SalesTrainerAudioScoreResult[]>([]);
    const [quizUserId, setQuizUserId] = useState("");
    const [quizUnitId, setQuizUnitId] = useState("");
    const [scoreUserId, setScoreUserId] = useState("");
    const [submissionId, setSubmissionId] = useState("");
    const [isQuizLoading, setIsQuizLoading] = useState(true);
    const [isScoreLoading, setIsScoreLoading] = useState(true);
    const [quizError, setQuizError] = useState<string | null>(null);
    const [scoreError, setScoreError] = useState<string | null>(null);

    async function loadQuizAttempts(filters?: { user_id?: string; unit_id?: string }) {
        setIsQuizLoading(true);
        setQuizError(null);
        try {
            const result = await api.admin.salesTrainer.listQuizAttempts({
                user_id: filters?.user_id,
                unit_id: filters?.unit_id,
                limit: 100,
            });
            setQuizItems(result.items);
        } catch (loadError) {
            setQuizItems([]);
            setQuizError(getApiErrorMessage(loadError));
        } finally {
            setIsQuizLoading(false);
        }
    }

    async function loadScoreResults(filters?: { user_id?: string; submission_id?: string }) {
        setIsScoreLoading(true);
        setScoreError(null);
        try {
            const result = await api.admin.salesTrainer.listScoreResults({
                user_id: filters?.user_id,
                submission_id: filters?.submission_id,
                limit: 100,
            });
            setScoreItems(result.items);
        } catch (loadError) {
            setScoreItems([]);
            setScoreError(getApiErrorMessage(loadError));
        } finally {
            setIsScoreLoading(false);
        }
    }

    useEffect(() => {
        void loadQuizAttempts();
        void loadScoreResults();
    }, []);

    function applyQuizFilters(event: React.FormEvent<HTMLFormElement>) {
        event.preventDefault();
        void loadQuizAttempts({
            user_id: quizUserId.trim() || undefined,
            unit_id: quizUnitId.trim() || undefined,
        });
    }

    function applyScoreFilters(event: React.FormEvent<HTMLFormElement>) {
        event.preventDefault();
        void loadScoreResults({
            user_id: scoreUserId.trim() || undefined,
            submission_id: submissionId.trim() || undefined,
        });
    }

    function resetQuizFilters() {
        setQuizUserId("");
        setQuizUnitId("");
        void loadQuizAttempts();
    }

    function resetScoreFilters() {
        setScoreUserId("");
        setSubmissionId("");
        void loadScoreResults();
    }

    return (
        <AdminIndexShell
            header={(
                <AdminPageHeader
                    title="销售训练学员结果"
                    description="统一查看做题结果和录音评分结果，核对题目快照、学员答案、AI 反馈和评分结论。"
                    secondaryActions={<SalesTrainerAdminModuleNav currentPath={pathname} />}
                />
            )}
        >
            <div className="space-y-6">
                <GlassCard className="p-6">
                    <div className="mb-4">
                        <h2 className="text-lg font-bold text-slate-900">做题结果</h2>
                        <p className="mt-1 text-sm text-slate-500">查看客观题自动判分和简答题 AI 评分后的答案快照。</p>
                    </div>
                    <form className="grid gap-4 md:grid-cols-[1fr_1fr_auto_auto]" onSubmit={applyQuizFilters}>
                        <div className="space-y-2">
                            <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-quiz-user-id">
                                用户 ID
                            </label>
                            <Input
                                id="sales-trainer-quiz-user-id"
                                value={quizUserId}
                                onChange={(event) => setQuizUserId(event.target.value)}
                                placeholder="按 user_id 查询"
                            />
                        </div>
                        <div className="space-y-2">
                            <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-quiz-unit-id">
                                训练单元 ID
                            </label>
                            <Input
                                id="sales-trainer-quiz-unit-id"
                                value={quizUnitId}
                                onChange={(event) => setQuizUnitId(event.target.value)}
                                placeholder="按 unit_id 查询"
                            />
                        </div>
                        <div className="flex items-end">
                            <Button type="submit" className="w-full rounded-full bg-slate-900 text-white">
                                查询
                            </Button>
                        </div>
                        <div className="flex items-end">
                            <Button type="button" variant="outline" className="w-full rounded-full" onClick={resetQuizFilters}>
                                重置
                            </Button>
                        </div>
                    </form>
                </GlassCard>

                <GlassCard className="overflow-hidden p-0">
                    {quizError ? (
                        <div className="border-b border-red-100 bg-red-50 px-6 py-4 text-sm text-red-700">
                            {quizError}
                        </div>
                    ) : null}
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="border-b border-slate-100 text-left text-slate-500">
                                <th className="px-6 py-4">学员</th>
                                <th className="px-6 py-4">训练单元</th>
                                <th className="px-6 py-4">得分</th>
                                <th className="px-6 py-4">结果</th>
                                <th className="px-6 py-4">提交时间</th>
                                <th className="px-6 py-4">操作</th>
                            </tr>
                        </thead>
                        <tbody>
                            {isQuizLoading ? (
                                <tr>
                                    <td colSpan={6} className="px-6 py-10 text-center text-slate-500">正在加载做题结果...</td>
                                </tr>
                            ) : quizItems.length === 0 ? (
                                <tr>
                                    <td colSpan={6} className="px-6 py-10 text-center text-slate-500">暂无做题结果</td>
                                </tr>
                            ) : quizItems.map((item) => (
                                <tr key={item.attempt_id} className="border-b border-slate-100 last:border-b-0">
                                    <td className="px-6 py-4">
                                        <div className="font-medium text-slate-900">{formatLearner(item)}</div>
                                        <div className="mt-1 text-xs text-slate-400">{item.user_id}</div>
                                    </td>
                                    <td className="px-6 py-4">{item.unit_id}</td>
                                    <td className="px-6 py-4">
                                        {item.total_score ?? "--"}
                                        <span className="text-slate-400"> / {item.max_score ?? "--"}</span>
                                    </td>
                                    <td className="px-6 py-4">
                                        <Badge variant={getQuizResultVariant(item)}>
                                            {getQuizResultLabel(item)}
                                        </Badge>
                                    </td>
                                    <td className="px-6 py-4">{new Date(item.submitted_at).toLocaleString()}</td>
                                    <td className="px-6 py-4">
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            onClick={() => router.push(`/admin/sales-trainer/quiz-attempts/${item.attempt_id}`)}
                                        >
                                            查看详情
                                        </Button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </GlassCard>

                <GlassCard className="p-6">
                    <div className="mb-4">
                        <h2 className="text-lg font-bold text-slate-900">录音评分</h2>
                        <p className="mt-1 text-sm text-slate-500">查看录音表达评分，核对模型、提示词版本和评分结论。</p>
                    </div>
                    <form className="grid gap-4 md:grid-cols-[1fr_1fr_auto_auto]" onSubmit={applyScoreFilters}>
                        <div className="space-y-2">
                            <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-score-user-id">
                                用户 ID
                            </label>
                            <Input
                                id="sales-trainer-score-user-id"
                                value={scoreUserId}
                                onChange={(event) => setScoreUserId(event.target.value)}
                                placeholder="按 user_id 查询"
                            />
                        </div>
                        <div className="space-y-2">
                            <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-score-submission-id">
                                录音提交 ID
                            </label>
                            <Input
                                id="sales-trainer-score-submission-id"
                                value={submissionId}
                                onChange={(event) => setSubmissionId(event.target.value)}
                                placeholder="按 submission_id 查询"
                            />
                        </div>
                        <div className="flex items-end">
                            <Button type="submit" className="w-full rounded-full bg-slate-900 text-white">
                                查询
                            </Button>
                        </div>
                        <div className="flex items-end">
                            <Button type="button" variant="outline" className="w-full rounded-full" onClick={resetScoreFilters}>
                                重置
                            </Button>
                        </div>
                    </form>
                </GlassCard>

                <GlassCard className="overflow-hidden p-0">
                    {scoreError ? (
                        <div className="border-b border-red-100 bg-red-50 px-6 py-4 text-sm text-red-700">
                            {scoreError}
                        </div>
                    ) : null}
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="border-b border-slate-100 text-left text-slate-500">
                                <th className="px-6 py-4">录音提交</th>
                                <th className="px-6 py-4">总分</th>
                                <th className="px-6 py-4">结果</th>
                                <th className="px-6 py-4">模型</th>
                                <th className="px-6 py-4">提示词版本</th>
                                <th className="px-6 py-4">创建时间</th>
                                <th className="px-6 py-4">操作</th>
                            </tr>
                        </thead>
                        <tbody>
                            {isScoreLoading ? (
                                <tr>
                                    <td colSpan={7} className="px-6 py-10 text-center text-slate-500">正在加载评分结果...</td>
                                </tr>
                            ) : scoreItems.length === 0 ? (
                                <tr>
                                    <td colSpan={7} className="px-6 py-10 text-center text-slate-500">暂无评分结果</td>
                                </tr>
                            ) : scoreItems.map((item) => (
                                <tr key={item.score_id} className="border-b border-slate-100 last:border-b-0">
                                    <td className="px-6 py-4 font-medium text-slate-900">{item.submission_id}</td>
                                    <td className="px-6 py-4">{item.total_score ?? "--"}</td>
                                    <td className="px-6 py-4">
                                        <Badge variant={getAudioScoreVariant(item)}>
                                            {getAudioScoreLabel(item)}
                                        </Badge>
                                    </td>
                                    <td className="px-6 py-4">{item.deucate_model || "--"}</td>
                                    <td className="px-6 py-4">v{item.prompt_version}</td>
                                    <td className="px-6 py-4">{new Date(item.created_at).toLocaleString()}</td>
                                    <td className="px-6 py-4">
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            onClick={() => router.push(`/admin/sales-trainer/audio-submissions/${item.submission_id}`)}
                                        >
                                            查看录音
                                        </Button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </GlassCard>
            </div>
        </AdminIndexShell>
    );
}
