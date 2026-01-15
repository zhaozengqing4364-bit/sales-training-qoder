"use client";

import * as React from "react";
import { useParams, useRouter } from "next/navigation";
import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
    ArrowLeft,
    RotateCcw,
    History,
    Home,
    Clock,
    MessageSquare,
    TrendingUp,
    TrendingDown,
    Minus,
    ChevronDown,
    ChevronUp,
    Play,
    CheckCircle2,
    AlertTriangle,
    Lightbulb,
    Loader2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api/client";

// 类型定义
interface ScoreDimension {
    name: string;
    score: number;
    trend?: "up" | "down" | "stable";
}

interface ConversationTurn {
    id: string;
    role: "user" | "ai";
    content: string;
    timestamp: string;
    score?: number;
    feedback?: string;
}

interface SessionReport {
    session_id: string;
    agent_name: string;
    persona_name: string;
    duration_seconds: number;
    total_turns: number;
    overall_score: number;
    dimensions: ScoreDimension[];
    highlights: string[];
    improvements: string[];
    suggestions: string[];
    conversation: ConversationTurn[];
}

// 雷达图组件
function RadarChart({ dimensions }: { dimensions: ScoreDimension[] }) {
    const size = 240;
    const center = size / 2;
    const radius = 80;
    const levels = 5;

    if (dimensions.length < 3) {
        return (
            <div className="w-[240px] h-[240px] flex items-center justify-center text-slate-400 text-sm">
                数据不足
            </div>
        );
    }

    const getPoint = (index: number, value: number) => {
        const angle = (Math.PI * 2 * index) / dimensions.length - Math.PI / 2;
        const r = (value / 100) * radius;
        return {
            x: center + r * Math.cos(angle),
            y: center + r * Math.sin(angle),
        };
    };

    const gridLevels = Array.from({ length: levels }, (_, i) => {
        const levelRadius = ((i + 1) / levels) * radius;
        const points = dimensions.map((_, idx) => {
            const angle = (Math.PI * 2 * idx) / dimensions.length - Math.PI / 2;
            return `${center + levelRadius * Math.cos(angle)},${center + levelRadius * Math.sin(angle)}`;
        });
        return points.join(" ");
    });

    const dataPoints = dimensions.map((d, i) => {
        const point = getPoint(i, d.score);
        return `${point.x},${point.y}`;
    }).join(" ");

    const axes = dimensions.map((_, i) => {
        const angle = (Math.PI * 2 * i) / dimensions.length - Math.PI / 2;
        return {
            x2: center + radius * Math.cos(angle),
            y2: center + radius * Math.sin(angle),
        };
    });

    const labels = dimensions.map((d, i) => {
        const angle = (Math.PI * 2 * i) / dimensions.length - Math.PI / 2;
        const labelRadius = radius + 30;
        return {
            x: center + labelRadius * Math.cos(angle),
            y: center + labelRadius * Math.sin(angle),
            name: d.name,
            score: d.score,
        };
    });

    return (
        <svg width={size} height={size} className="mx-auto">
            {gridLevels.map((points, i) => (
                <polygon
                    key={i}
                    points={points}
                    fill="none"
                    stroke="rgb(226, 232, 240)"
                    strokeWidth="1"
                />
            ))}
            
            {axes.map((axis, i) => (
                <line
                    key={i}
                    x1={center}
                    y1={center}
                    x2={axis.x2}
                    y2={axis.y2}
                    stroke="rgb(226, 232, 240)"
                    strokeWidth="1"
                />
            ))}
            
            <polygon
                points={dataPoints}
                fill="rgba(99, 102, 241, 0.2)"
                stroke="rgb(99, 102, 241)"
                strokeWidth="2"
                className="transition-all duration-500"
            />
            
            {dimensions.map((d, i) => {
                const point = getPoint(i, d.score);
                return (
                    <circle
                        key={i}
                        cx={point.x}
                        cy={point.y}
                        r="5"
                        fill="rgb(99, 102, 241)"
                        className="transition-all duration-500"
                    />
                );
            })}
            
            {labels.map((label, i) => (
                <g key={i}>
                    <text
                        x={label.x}
                        y={label.y - 6}
                        textAnchor="middle"
                        dominantBaseline="middle"
                        className="text-[11px] fill-slate-700 font-medium"
                    >
                        {label.name}
                    </text>
                    <text
                        x={label.x}
                        y={label.y + 8}
                        textAnchor="middle"
                        dominantBaseline="middle"
                        className="text-[10px] fill-indigo-600 font-bold"
                    >
                        {label.score}
                    </text>
                </g>
            ))}
        </svg>
    );
}

// 趋势图标
function TrendIcon({ trend }: { trend?: "up" | "down" | "stable" }) {
    if (trend === "up") return <TrendingUp className="w-4 h-4 text-emerald-500" />;
    if (trend === "down") return <TrendingDown className="w-4 h-4 text-red-500" />;
    return <Minus className="w-4 h-4 text-slate-400" />;
}

// 评分等级
function getScoreLevel(score: number): { label: string; color: string } {
    if (score >= 90) return { label: "优秀", color: "bg-emerald-50 text-emerald-600" };
    if (score >= 80) return { label: "良好", color: "bg-blue-50 text-blue-600" };
    if (score >= 70) return { label: "中等", color: "bg-amber-50 text-amber-600" };
    if (score >= 60) return { label: "及格", color: "bg-orange-50 text-orange-600" };
    return { label: "需改进", color: "bg-red-50 text-red-600" };
}

export default function PracticeReportPage() {
    const params = useParams();
    const router = useRouter();
    const sessionId = params.sessionId as string;

    const [report, setReport] = React.useState<SessionReport | null>(null);
    const [loading, setLoading] = React.useState(true);
    const [error, setError] = React.useState<string | null>(null);
    const [expandedTurn, setExpandedTurn] = React.useState<string | null>(null);

    // 加载报告数据
    React.useEffect(() => {
        async function loadReport() {
            try {
                setLoading(true);
                // 尝试获取增强报告
                const response = await api.sessions.getEnhancedReport(sessionId);
                if (response) {
                    // 转换 API 响应为报告格式
                    const data = response;
                    
                    setReport({
                        session_id: sessionId,
                        agent_name: data.agent_name || "AI 教练",
                        persona_name: data.persona_name || "销售场景",
                        duration_seconds: data.duration_seconds || 0,
                        total_turns: data.total_turns || 0,
                        overall_score: data.overall_score || 0,
                        dimensions: data.dimension_scores?.map(d => ({
                            name: d.name,
                            score: d.score,
                            trend: undefined,
                        })) || [
                            { name: "专业度", score: 75, trend: "up" as const },
                            { name: "沟通技巧", score: 80, trend: "stable" as const },
                            { name: "销售流程", score: 70, trend: "up" as const },
                            { name: "应变能力", score: 65, trend: "down" as const },
                            { name: "产品知识", score: 85, trend: "up" as const },
                        ],
                        highlights: data.strengths?.length > 0 ? data.strengths : [
                            "产品介绍清晰准确",
                            "能够有效处理客户异议",
                        ],
                        improvements: data.improvements?.length > 0 ? data.improvements : [
                            "需要更多倾听客户需求",
                            "价格谈判技巧有待提升",
                        ],
                        suggestions: data.suggestions || [
                            "建议学习 SPIN 销售法",
                            "多练习处理价格异议的话术",
                        ],
                        conversation: [],
                    });
                }
            } catch (err) {
                console.error("Failed to load report:", err);
                setError("加载报告失败");
                // 使用模拟数据
                setReport({
                    session_id: sessionId,
                    agent_name: "销售教练",
                    persona_name: "挑剔客户",
                    duration_seconds: 320,
                    total_turns: 12,
                    overall_score: 78,
                    dimensions: [
                        { name: "专业度", score: 82, trend: "up" },
                        { name: "沟通技巧", score: 75, trend: "stable" },
                        { name: "销售流程", score: 80, trend: "up" },
                        { name: "应变能力", score: 70, trend: "down" },
                        { name: "产品知识", score: 85, trend: "up" },
                    ],
                    highlights: [
                        "产品介绍清晰准确",
                        "能够有效处理客户异议",
                    ],
                    improvements: [
                        "需要更多倾听客户需求",
                        "价格谈判技巧有待提升",
                    ],
                    suggestions: [
                        "建议学习 SPIN 销售法",
                        "多练习处理价格异议的话术",
                    ],
                    conversation: [],
                });
            } finally {
                setLoading(false);
            }
        }
        loadReport();
    }, [sessionId]);

    const formatDuration = (seconds: number) => {
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${mins}分${secs}秒`;
    };

    if (loading) {
        return (
            <div className="min-h-screen bg-slate-50 flex items-center justify-center">
                <div className="text-center">
                    <Loader2 className="w-8 h-8 animate-spin text-indigo-600 mx-auto mb-4" />
                    <p className="text-slate-500">加载报告中...</p>
                </div>
            </div>
        );
    }

    if (!report) {
        return (
            <div className="min-h-screen bg-slate-50 flex items-center justify-center">
                <div className="text-center">
                    <AlertTriangle className="w-12 h-12 text-amber-500 mx-auto mb-4" />
                    <p className="text-slate-700 font-medium mb-2">报告不存在</p>
                    <p className="text-slate-500 text-sm mb-4">{error}</p>
                    <Button onClick={() => router.push("/")} variant="outline">
                        返回首页
                    </Button>
                </div>
            </div>
        );
    }

    const scoreLevel = getScoreLevel(report.overall_score);

    return (
        <div className="min-h-screen bg-slate-50">
            {/* 头部 */}
            <header className="sticky top-0 z-10 bg-white/80 backdrop-blur-lg border-b border-slate-200/50">
                <div className="max-w-4xl mx-auto px-4 h-14 flex items-center justify-between">
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => router.back()}
                        className="gap-2"
                    >
                        <ArrowLeft className="w-4 h-4" />
                        返回
                    </Button>
                    <h1 className="text-base font-semibold text-slate-800">训练报告</h1>
                    <div className="w-16" />
                </div>
            </header>

            <main className="max-w-4xl mx-auto px-4 py-6 space-y-6 pb-24">
                {/* 总分卡片 */}
                <GlassCard className="p-6">
                    <div className="flex flex-col md:flex-row items-center gap-6">
                        {/* 分数圆环 */}
                        <div className="relative">
                            <svg width="140" height="140" className="transform -rotate-90">
                                <circle
                                    cx="70"
                                    cy="70"
                                    r="60"
                                    fill="none"
                                    stroke="rgb(226, 232, 240)"
                                    strokeWidth="12"
                                />
                                <circle
                                    cx="70"
                                    cy="70"
                                    r="60"
                                    fill="none"
                                    stroke="rgb(99, 102, 241)"
                                    strokeWidth="12"
                                    strokeLinecap="round"
                                    strokeDasharray={`${(report.overall_score / 100) * 377} 377`}
                                    className="transition-all duration-1000"
                                />
                            </svg>
                            <div className="absolute inset-0 flex flex-col items-center justify-center">
                                <span className="text-4xl font-bold text-slate-800">
                                    {report.overall_score}
                                </span>
                                <Badge className={cn("mt-1", scoreLevel.color)}>
                                    {scoreLevel.label}
                                </Badge>
                            </div>
                        </div>

                        {/* 基本信息 */}
                        <div className="flex-1 text-center md:text-left">
                            <h2 className="text-xl font-bold text-slate-800 mb-2">
                                {report.agent_name} · {report.persona_name}
                            </h2>
                            <div className="flex flex-wrap justify-center md:justify-start gap-4 text-sm text-slate-500">
                                <span className="flex items-center gap-1">
                                    <Clock className="w-4 h-4" />
                                    {formatDuration(report.duration_seconds)}
                                </span>
                                <span className="flex items-center gap-1">
                                    <MessageSquare className="w-4 h-4" />
                                    {report.total_turns} 轮对话
                                </span>
                            </div>
                        </div>
                    </div>
                </GlassCard>

                {/* 雷达图 + 维度详情 */}
                <div className="grid md:grid-cols-2 gap-6">
                    <GlassCard className="p-6">
                        <h3 className="text-base font-semibold text-slate-800 mb-4">能力雷达图</h3>
                        <RadarChart dimensions={report.dimensions} />
                    </GlassCard>

                    <GlassCard className="p-6">
                        <h3 className="text-base font-semibold text-slate-800 mb-4">维度评分</h3>
                        <div className="space-y-4">
                            {report.dimensions.map((dim) => (
                                <div key={dim.name}>
                                    <div className="flex items-center justify-between mb-1">
                                        <span className="text-sm text-slate-600 flex items-center gap-2">
                                            {dim.name}
                                            <TrendIcon trend={dim.trend} />
                                        </span>
                                        <span className="text-sm font-semibold text-slate-800">
                                            {dim.score}
                                        </span>
                                    </div>
                                    <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                                        <div
                                            className="h-full bg-indigo-500 rounded-full transition-all duration-500"
                                            style={{ width: `${dim.score}%` }}
                                        />
                                    </div>
                                </div>
                            ))}
                        </div>
                    </GlassCard>
                </div>

                {/* 亮点与改进 */}
                <div className="grid md:grid-cols-2 gap-6">
                    {/* 亮点 */}
                    <GlassCard className="p-6">
                        <h3 className="text-base font-semibold text-slate-800 mb-4 flex items-center gap-2">
                            <CheckCircle2 className="w-5 h-5 text-emerald-500" />
                            表现亮点
                        </h3>
                        <ul className="space-y-3">
                            {report.highlights.map((item, idx) => (
                                <li
                                    key={idx}
                                    className="flex items-start gap-2 text-sm text-slate-600"
                                >
                                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 mt-2 flex-shrink-0" />
                                    {item}
                                </li>
                            ))}
                            {report.highlights.length === 0 && (
                                <li className="text-sm text-slate-400">暂无数据</li>
                            )}
                        </ul>
                    </GlassCard>

                    {/* 改进点 */}
                    <GlassCard className="p-6">
                        <h3 className="text-base font-semibold text-slate-800 mb-4 flex items-center gap-2">
                            <AlertTriangle className="w-5 h-5 text-amber-500" />
                            待改进
                        </h3>
                        <ul className="space-y-3">
                            {report.improvements.map((item, idx) => (
                                <li
                                    key={idx}
                                    className="flex items-start gap-2 text-sm text-slate-600"
                                >
                                    <span className="w-1.5 h-1.5 rounded-full bg-amber-500 mt-2 flex-shrink-0" />
                                    {item}
                                </li>
                            ))}
                            {report.improvements.length === 0 && (
                                <li className="text-sm text-slate-400">暂无数据</li>
                            )}
                        </ul>
                    </GlassCard>
                </div>

                {/* 建议 */}
                <GlassCard className="p-6">
                    <h3 className="text-base font-semibold text-slate-800 mb-4 flex items-center gap-2">
                        <Lightbulb className="w-5 h-5 text-blue-500" />
                        学习建议
                    </h3>
                    <ul className="space-y-3">
                        {report.suggestions.map((item, idx) => (
                            <li
                                key={idx}
                                className="flex items-start gap-3 p-3 bg-blue-50/50 rounded-xl text-sm text-slate-600"
                            >
                                <span className="w-6 h-6 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center text-xs font-semibold flex-shrink-0">
                                    {idx + 1}
                                </span>
                                {item}
                            </li>
                        ))}
                        {report.suggestions.length === 0 && (
                            <li className="text-sm text-slate-400">暂无建议</li>
                        )}
                    </ul>
                </GlassCard>

                {/* 对话回放入口 */}
                {report.conversation.length > 0 && (
                    <GlassCard className="p-6">
                        <div className="flex items-center justify-between mb-4">
                            <h3 className="text-base font-semibold text-slate-800 flex items-center gap-2">
                                <Play className="w-5 h-5 text-indigo-500" />
                                对话回放
                            </h3>
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => router.push(`/history/${sessionId}`)}
                            >
                                查看完整对话
                            </Button>
                        </div>
                        <div className="space-y-2">
                            {report.conversation.slice(0, 3).map((turn) => (
                                <div
                                    key={turn.id}
                                    className={cn(
                                        "p-3 rounded-xl text-sm",
                                        turn.role === "user"
                                            ? "bg-indigo-50 ml-8"
                                            : "bg-slate-100 mr-8"
                                    )}
                                >
                                    <p className="text-slate-600 line-clamp-2">{turn.content}</p>
                                </div>
                            ))}
                        </div>
                    </GlassCard>
                )}
            </main>

            {/* 底部操作栏 */}
            <div className="fixed bottom-0 left-0 right-0 bg-white/80 backdrop-blur-lg border-t border-slate-200/50 p-4">
                <div className="max-w-4xl mx-auto flex gap-3">
                    <Button
                        variant="outline"
                        className="flex-1 gap-2"
                        onClick={() => router.push("/")}
                    >
                        <Home className="w-4 h-4" />
                        返回首页
                    </Button>
                    <Button
                        variant="outline"
                        className="flex-1 gap-2"
                        onClick={() => router.push("/history")}
                    >
                        <History className="w-4 h-4" />
                        历史记录
                    </Button>
                    <Button
                        className="flex-1 gap-2 bg-indigo-600 hover:bg-indigo-700"
                        onClick={() => router.push(`/practice/${sessionId}?retry=true`)}
                    >
                        <RotateCcw className="w-4 h-4" />
                        再练一次
                    </Button>
                </div>
            </div>
        </div>
    );
}
