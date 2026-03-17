/**
 * Score Panel Component for Sales Training
 *
 * Requirements: Story 2.6 - Real-time scoring updates and improvement suggestions
 *
 * Features:
 * - Displays real-time score updates
 * - Shows dimension scores with visual indicators
 * - Displays improvement suggestions
 * - Smooth animations for score changes
 * - Responsive design for mobile (H5)
 */

import React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { TrendingUp, Lightbulb, Award, BarChart3 } from "lucide-react";
import type { ScoreUpdate } from "@/hooks/use-practice-websocket";

interface ScorePanelProps {
    scores: ScoreUpdate | null;
    className?: string;
}

const DIMENSION_CONFIG: Record<string, { color: string; icon: React.ReactNode }> = {
    "专业度": { color: "#1890FF", icon: <Award className="w-4 h-4" /> },
    "沟通技巧": { color: "#52C41A", icon: <BarChart3 className="w-4 h-4" /> },
    "销售流程": { color: "#FAAD14", icon: <TrendingUp className="w-4 h-4" /> },
    "异议处理": { color: "#722ED1", icon: <Lightbulb className="w-4 h-4" /> },
    "成交能力": { color: "#EB2F96", icon: <Award className="w-4 h-4" /> },
    "communication": { color: "#52C41A", icon: <BarChart3 className="w-4 h-4" /> },
    "discovery": { color: "#FAAD14", icon: <TrendingUp className="w-4 h-4" /> },
    "objection": { color: "#722ED1", icon: <Lightbulb className="w-4 h-4" /> },
    "closing": { color: "#EB2F96", icon: <Award className="w-4 h-4" /> },
    "professional": { color: "#1890FF", icon: <Award className="w-4 h-4" /> },
};

function getScoreColor(score: number): string {
    if (score >= 85) return "#52C41A"; // Success green
    if (score >= 70) return "#FAAD14"; // Warning yellow
    return "#F5222D"; // Error red
}

function getScoreLevel(score: number): string {
    if (score >= 85) return "优秀";
    if (score >= 70) return "良好";
    if (score >= 60) return "及格";
    return "需改进";
}

function ScoreRing({ score, size = 80 }: { score: number; size?: number }) {
    const color = getScoreColor(score);
    const circumference = 2 * Math.PI * ((size - 8) / 2);
    const strokeDashoffset = circumference - (score / 100) * circumference;

    return (
        <div className="relative" style={{ width: size, height: size }}>
            <svg
                width={size}
                height={size}
                className="transform -rotate-90"
            >
                {/* Background ring */}
                <circle
                    cx={size / 2}
                    cy={size / 2}
                    r={(size - 8) / 2}
                    fill="none"
                    stroke="#E2E8F0"
                    strokeWidth={6}
                />
                {/* Progress ring */}
                <motion.circle
                    cx={size / 2}
                    cy={size / 2}
                    r={(size - 8) / 2}
                    fill="none"
                    stroke={color}
                    strokeWidth={6}
                    strokeLinecap="round"
                    strokeDasharray={circumference}
                    initial={{ strokeDashoffset: circumference }}
                    animate={{ strokeDashoffset }}
                    transition={{ duration: 0.8, ease: "easeOut" }}
                />
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
                <motion.span
                    className="text-xl font-bold"
                    style={{ color }}
                    initial={{ opacity: 0, scale: 0.5 }}
                    animate={{ opacity: 1, scale: 1 }}
                    key={score}
                >
                    {Math.round(score)}
                </motion.span>
                <span className="text-xs text-gray-500">分</span>
            </div>
        </div>
    );
}

function DimensionBar({ name, score }: { name: string; score: number }) {
    const config = DIMENSION_CONFIG[name] || { color: "#1890FF", icon: <BarChart3 className="w-4 h-4" /> };
    const color = getScoreColor(score);

    return (
        <div className="flex items-center gap-3 py-2">
            <div className="flex items-center gap-2 w-24 shrink-0">
                <span style={{ color: config.color }}>{config.icon}</span>
                <span className="text-sm text-gray-700 truncate">{name}</span>
            </div>
            <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                <motion.div
                    className="h-full rounded-full"
                    style={{ backgroundColor: color }}
                    initial={{ width: 0 }}
                    animate={{ width: `${score}%` }}
                    transition={{ duration: 0.6, ease: "easeOut" }}
                />
            </div>
            <span className="text-sm font-medium w-10 text-right" style={{ color }}>
                {Math.round(score)}
            </span>
        </div>
    );
}

function SuggestionCard({ suggestion, index }: { suggestion: string; index: number }) {
    return (
        <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: index * 0.1 }}
            className="flex items-start gap-2 p-3 bg-blue-50 rounded-lg border border-blue-100"
        >
            <Lightbulb className="w-4 h-4 text-blue-500 shrink-0 mt-0.5" />
            <span className="text-sm text-gray-700 leading-relaxed">{suggestion}</span>
        </motion.div>
    );
}

export function ScorePanel({ scores, className = "" }: ScorePanelProps) {
    const dimensions = scores?.dimension_scores
        ? Object.entries(scores.dimension_scores).map(([name, score]) => ({
            name,
            score,
        }))
        : [];

    const overallScore = scores?.overall_score ?? 0;
    const suggestions = scores?.suggestions ?? [];
    const stageName = scores?.stage_name ?? "";

    if (!scores) {
        return (
            <div className={`bg-white rounded-xl shadow-sm border border-gray-100 p-4 ${className}`}>
                <div className="flex flex-col items-center justify-center py-8 text-gray-400">
                    <BarChart3 className="w-12 h-12 mb-3 opacity-50" />
                    <p className="text-sm">评分数据加载中...</p>
                    <p className="text-xs text-gray-400 mt-1">完成更多对话轮次后显示评分</p>
                </div>
            </div>
        );
    }

    return (
        <div className={`bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden ${className}`}>
            {/* Header */}
            <div className="px-4 py-3 border-b border-gray-100 bg-gradient-to-r from-blue-50 to-white">
                <div className="flex items-center justify-between">
                    <h3 className="font-semibold text-gray-800 flex items-center gap-2">
                        <Award className="w-5 h-5 text-blue-500" />
                        实时评分
                    </h3>
                    {stageName && (
                        <span className="text-xs px-2 py-1 bg-blue-100 text-blue-700 rounded-full">
                            {stageName}
                        </span>
                    )}
                </div>
            </div>

            {/* Overall Score */}
            <div className="p-4 flex items-center gap-4 border-b border-gray-100">
                <ScoreRing score={overallScore} />
                <div className="flex-1">
                    <div className="text-sm text-gray-500 mb-1">综合评分</div>
                    <div
                        className="text-lg font-bold"
                        style={{ color: getScoreColor(overallScore) }}
                    >
                        {getScoreLevel(overallScore)}
                    </div>
                    <div className="text-xs text-gray-400 mt-1">
                        第 {scores.turn_count ?? 0} 轮对话
                    </div>
                </div>
            </div>

            {/* Dimension Scores */}
            <div className="p-4 border-b border-gray-100">
                <h4 className="text-sm font-medium text-gray-700 mb-2 flex items-center gap-2">
                    <BarChart3 className="w-4 h-4" />
                    维度得分
                </h4>
                <div className="space-y-1">
                    <AnimatePresence>
                        {dimensions.map((dim) => (
                            <DimensionBar
                                key={dim.name}
                                name={dim.name}
                                score={dim.score}
                            />
                        ))}
                    </AnimatePresence>
                </div>
            </div>

            {/* Suggestions */}
            {suggestions.length > 0 && (
                <div className="p-4 bg-gray-50">
                    <h4 className="text-sm font-medium text-gray-700 mb-3 flex items-center gap-2">
                        <Lightbulb className="w-4 h-4 text-amber-500" />
                        改进建议
                    </h4>
                    <div className="space-y-2">
                        <AnimatePresence>
                            {suggestions.map((suggestion, index) => (
                                <SuggestionCard
                                    key={`${index}-${suggestion.slice(0, 20)}`}
                                    suggestion={suggestion}
                                    index={index}
                                />
                            ))}
                        </AnimatePresence>
                    </div>
                </div>
            )}
        </div>
    );
}

export default ScorePanel;
