"use client";

import Link from "next/link";
import { BookOpen, Trash2 } from "lucide-react";

import type { LearningContentSummary } from "@/lib/api/types";
import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";

const STATUS_LABELS: Record<string, string> = {
    draft: "草稿",
    published: "已发布",
    archived: "已归档",
};

const STATUS_COLORS: Record<string, string> = {
    draft: "bg-slate-100 text-slate-700",
    published: "bg-emerald-100 text-emerald-700",
    archived: "bg-amber-100 text-amber-700",
};

interface LearningContentIndexTableProps {
    items: LearningContentSummary[];
    onDelete: (item: LearningContentSummary) => void;
}

export function LearningContentIndexTable({ items, onDelete }: LearningContentIndexTableProps) {
    if (items.length === 0) {
        return (
            <GlassCard className="overflow-hidden">
                <div className="py-12 text-center text-slate-500">暂无学习内容数据</div>
            </GlassCard>
        );
    }

    return (
        <GlassCard className="overflow-hidden">
            <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                    <thead className="border-b border-slate-100 bg-slate-50/50 text-xs font-bold uppercase tracking-wider text-slate-400">
                        <tr>
                            <th className="px-6 py-4">标题</th>
                            <th className="px-6 py-4">摘要</th>
                            <th className="px-6 py-4">负责人</th>
                            <th className="px-6 py-4">来源</th>
                            <th className="px-6 py-4">状态</th>
                            <th className="px-6 py-4">版本</th>
                            <th className="px-6 py-4">操作</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                        {items.map((item) => (
                            <tr key={item.learning_content_id} className="transition-colors hover:bg-slate-50/50">
                                <td className="px-6 py-4">
                                    <Link
                                        href={`/admin/learning-contents/${item.learning_content_id}`}
                                        prefetch={false}
                                        className="flex items-center gap-3 hover:opacity-80 transition-opacity"
                                    >
                                        <div className="flex h-9 w-9 items-center justify-center rounded-full bg-blue-50 text-blue-600">
                                            <BookOpen className="h-5 w-5" />
                                        </div>
                                        <div className="font-bold text-slate-900">{item.title}</div>
                                    </Link>
                                </td>
                                <td className="max-w-xs truncate px-6 py-4 text-slate-500">{item.summary || "-"}</td>
                                <td className="px-6 py-4 font-medium text-slate-700">{item.owner || "-"}</td>
                                <td className="px-6 py-4 font-medium text-slate-700">{item.source || "-"}</td>
                                <td className="px-6 py-4">
                                    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_COLORS[item.status] || "bg-slate-100 text-slate-700"}`}>
                                        {STATUS_LABELS[item.status] || item.status}
                                    </span>
                                </td>
                                <td className="px-6 py-4 font-medium text-slate-700">v{item.version}</td>
                                <td className="px-6 py-4">
                                    {item.status === "draft" ? (
                                        <Button
                                            variant="outline"
                                            className="rounded-full text-red-600"
                                            onClick={() => onDelete(item)}
                                        >
                                            <Trash2 className="mr-2 h-4 w-4" />
                                            删除
                                        </Button>
                                    ) : (
                                        <span className="text-xs font-medium text-slate-400">仅草稿可删除</span>
                                    )}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </GlassCard>
    );
}
