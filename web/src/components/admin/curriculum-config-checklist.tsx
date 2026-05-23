"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, Circle, ExternalLink, Loader2 } from "lucide-react";

import { GlassCard } from "@/components/ui/glass-card";
import { api, getApiErrorMessage } from "@/lib/api/client";
import { debug } from "@/lib/debug";

type StepStatus = "done" | "pending" | "loading";

export interface CurriculumConfigStep {
    key: string;
    order: number;
    title: string;
    description: string;
    href: string;
    external?: boolean;
}

/** Recommended sales curriculum setup order (plan §4.1). */
export const CURRICULUM_CONFIG_STEPS: CurriculumConfigStep[] = [
    {
        key: "knowledge",
        order: 1,
        title: "知识库",
        description: "上传文档；在检索策略页激活全局版本",
        href: "/admin/knowledge",
    },
    {
        key: "persona",
        order: 2,
        title: "角色管理（Persona）",
        description: "平台 AI 人格：绑定知识库、压力模型与策略审计",
        href: "/admin/personas",
    },
    {
        key: "agent",
        order: 3,
        title: "智能体",
        description: "发布训练场景壳（不承载实时提示词）",
        href: "/admin/agents",
    },
    {
        key: "voice-scoring",
        order: 4,
        title: "语音策略与评分规则",
        description: "语音运行时配置 + 销售评分规则集各至少一条可用",
        href: "/admin/voice-runtime",
    },
    {
        key: "case-role",
        order: 5,
        title: "训练案例库与客户角色库",
        description: "发布业务剧本与客户行为画像（RoleProfile.persona_ref 对齐 Persona）",
        href: "/admin/curriculum-practice/case-items",
    },
    {
        key: "learning",
        order: 6,
        title: "学习内容",
        description: "编排章节并发布学习材料",
        href: "/admin/learning-contents",
    },
    {
        key: "test-bank",
        order: 7,
        title: "题库",
        description: "发布考核题目供考官引用",
        href: "/admin/test-bank",
    },
    {
        key: "template",
        order: 8,
        title: "课程训练模板",
        description: "组装引用、CurriculumPlan 并发布闭环模板",
        href: "/admin/curriculum-practice/templates",
    },
    {
        key: "learner-path",
        order: 9,
        title: "学员路径试跑",
        description: "在学员端走通 study → exam → practice → report",
        href: "/learning-path",
        external: true,
    },
];

export function CurriculumConfigChecklist() {
    const [statusByKey, setStatusByKey] = useState<Record<string, StepStatus>>({});
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const loadStatus = useCallback(async () => {
        setLoading(true);
        setError(null);
        const next: Record<string, StepStatus> = Object.fromEntries(
            CURRICULUM_CONFIG_STEPS.map((step) => [step.key, "loading"]),
        );
        setStatusByKey(next);
        try {
            const [
                knowledge,
                personas,
                agents,
                voiceProfiles,
                scoring,
                caseItems,
                roleProfiles,
                learningContents,
                questions,
                templates,
                knowledgeConfig,
            ] = await Promise.all([
                api.admin.getKnowledgeBases({ page: 1, page_size: 50 }),
                api.admin.getPersonas({ page: 1, page_size: 50 }),
                api.admin.getAgents({ page: 1, page_size: 50 }),
                api.admin.getVoiceRuntimeProfiles(),
                api.admin.listScoringRulesets("sales"),
                api.admin.listCaseItems({ status: "published" }),
                api.admin.listRoleProfiles({ status: "published" }),
                api.learningContents.list({ status: "published" }),
                api.testBank.listQuestions({ status: "published" }),
                api.admin.listPracticeTemplates(),
                api.admin.getKnowledgeAnswerAdminConfig().catch(() => null),
            ]);

            const hasReadyKb = knowledge.items.some(
                (kb) => (kb.document_count ?? kb.doc_count ?? 0) > 0,
            );
            const hasActivePersona = personas.items.some((item) => item.status === "active");
            const hasPublishedAgent = agents.items.some((item) => item.status === "published");
            const hasVoice = voiceProfiles.items.some((item) => item.is_active);
            const hasScoring = scoring.items.some((item) => item.status === "published");
            const hasCaseRole = caseItems.items.length > 0 && roleProfiles.items.length > 0;
            const hasLearning = learningContents.items.length > 0;
            const hasQuestions = (questions.total ?? questions.items.length) > 0;
            const hasPublishedTemplate = templates.items.some((item) => item.status === "published");
            const hasRetrieval = Boolean(knowledgeConfig?.active_version?.id);

            setStatusByKey({
                knowledge: hasReadyKb && hasRetrieval ? "done" : "pending",
                persona: hasActivePersona ? "done" : "pending",
                agent: hasPublishedAgent ? "done" : "pending",
                "voice-scoring": hasVoice && hasScoring ? "done" : "pending",
                "case-role": hasCaseRole ? "done" : "pending",
                learning: hasLearning ? "done" : "pending",
                "test-bank": hasQuestions ? "done" : "pending",
                template: hasPublishedTemplate ? "done" : "pending",
                "learner-path": hasPublishedTemplate ? "done" : "pending",
            });
        } catch (err) {
            setError(`配置清单加载失败：${getApiErrorMessage(err)}`);
            debug.warn("[CurriculumConfigChecklist] failed to load status", { error: err });
            setStatusByKey(
                Object.fromEntries(CURRICULUM_CONFIG_STEPS.map((step) => [step.key, "pending"])),
            );
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        void Promise.resolve().then(loadStatus);
    }, [loadStatus]);

    const doneCount = CURRICULUM_CONFIG_STEPS.filter(
        (step) => statusByKey[step.key] === "done",
    ).length;

    return (
        <GlassCard className="space-y-4 p-6">
            <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                <div>
                    <h2 className="text-xl font-black text-slate-900">课程闭环配置清单</h2>
                    <p className="mt-1 text-sm text-slate-600">
                        按推荐顺序检查 9 步资产是否就绪。完成 {doneCount}/
                        {CURRICULUM_CONFIG_STEPS.length} 步。
                    </p>
                </div>
                <button
                    type="button"
                    className="text-sm font-medium text-slate-600 hover:text-slate-900"
                    onClick={() => void loadStatus()}
                    disabled={loading}
                >
                    刷新状态
                </button>
            </div>
            {error ? <p className="text-sm text-red-700">{error}</p> : null}
            <ol className="space-y-2">
                {CURRICULUM_CONFIG_STEPS.map((step) => {
                    const status = statusByKey[step.key] ?? "pending";
                    return (
                        <li
                            key={step.key}
                            className="flex items-start gap-3 rounded-xl border border-slate-100 bg-white/80 px-4 py-3"
                        >
                            <StepIcon
                                status={loading && status === "loading" ? "loading" : status}
                            />
                            <div className="min-w-0 flex-1">
                                <div className="flex flex-wrap items-center gap-2">
                                    <span className="text-xs font-bold text-slate-400">
                                        步骤 {step.order}
                                    </span>
                                    <span className="font-semibold text-slate-900">
                                        {step.title}
                                    </span>
                                </div>
                                <p className="mt-0.5 text-xs text-slate-500">{step.description}</p>
                                {step.key === "case-role" ? (
                                    <p className="mt-1 text-xs text-slate-400">
                                        客户角色库：
                                        <Link
                                            href="/admin/curriculum-practice/role-profiles"
                                            className="font-medium text-blue-700 hover:text-blue-900"
                                        >
                                            去配置
                                        </Link>
                                    </p>
                                ) : null}
                            </div>
                            {step.external ? (
                                <a
                                    href={step.href}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="inline-flex shrink-0 items-center gap-1 text-sm font-medium text-blue-700 hover:text-blue-900"
                                >
                                    打开
                                    <ExternalLink className="h-3.5 w-3.5" />
                                </a>
                            ) : (
                                <Link
                                    href={step.href}
                                    className="shrink-0 text-sm font-medium text-blue-700 hover:text-blue-900"
                                >
                                    去配置
                                </Link>
                            )}
                        </li>
                    );
                })}
            </ol>
        </GlassCard>
    );
}

function StepIcon({ status }: { status: StepStatus }) {
    if (status === "loading") {
        return <Loader2 className="mt-0.5 h-5 w-5 shrink-0 animate-spin text-slate-400" />;
    }
    if (status === "done") {
        return <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600" />;
    }
    return <Circle className="mt-0.5 h-5 w-5 shrink-0 text-slate-300" />;
}
