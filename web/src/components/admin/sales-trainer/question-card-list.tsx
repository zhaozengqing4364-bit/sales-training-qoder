"use client";

import { Archive, CheckCircle2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import type { SalesTrainerQuestion } from "@/lib/api/types";

import { displayQuestionTag, QUESTION_STATUS_LABELS } from "./question-display";

const QUESTION_TYPE_LABELS = {
    single_choice: "单选题",
    multiple_choice: "多选题",
    true_false: "判断题",
    short_answer: "简答题",
} as const satisfies Record<SalesTrainerQuestion["question_type"], string>;

const DIFFICULTY_LABELS = {
    easy: "简单",
    medium: "中等",
    hard: "困难",
} as const satisfies Record<SalesTrainerQuestion["difficulty"], string>;

interface QuestionCardListProps {
    readonly categoryNameById: ReadonlyMap<string, string>;
    readonly isLoading: boolean;
    readonly onArchive: (question: SalesTrainerQuestion) => void;
    readonly onEdit: (questionId: string) => void;
    readonly onPublish: (question: SalesTrainerQuestion) => void;
    readonly questions: readonly SalesTrainerQuestion[];
}

export function QuestionCardList({
    categoryNameById,
    isLoading,
    onArchive,
    onEdit,
    onPublish,
    questions,
}: QuestionCardListProps) {
    return (
        <GlassCard className="overflow-hidden p-0">
            <div className="flex items-center justify-between border-b border-slate-100 px-6 py-5">
                <div>
                    <h2 className="text-lg font-bold text-slate-900">题目清单</h2>
                    <p className="mt-1 text-xs text-slate-500">按题目粒度维护，组卷请前往考卷管理。</p>
                </div>
                <Badge className="bg-slate-100 text-slate-700">
                    {isLoading ? "加载中" : `${questions.length} 题`}
                </Badge>
            </div>
            <div className="divide-y divide-slate-100">
                <QuestionListContent
                    categoryNameById={categoryNameById}
                    isLoading={isLoading}
                    onArchive={onArchive}
                    onEdit={onEdit}
                    onPublish={onPublish}
                    questions={questions}
                />
            </div>
        </GlassCard>
    );
}

interface QuestionListContentProps {
    readonly categoryNameById: ReadonlyMap<string, string>;
    readonly isLoading: boolean;
    readonly onArchive: (question: SalesTrainerQuestion) => void;
    readonly onEdit: (questionId: string) => void;
    readonly onPublish: (question: SalesTrainerQuestion) => void;
    readonly questions: readonly SalesTrainerQuestion[];
}

function QuestionListContent({
    categoryNameById,
    isLoading,
    onArchive,
    onEdit,
    onPublish,
    questions,
}: QuestionListContentProps) {
    if (isLoading) {
        return <div className="px-6 py-14 text-center text-sm text-slate-500">正在加载题目...</div>;
    }
    if (questions.length === 0) {
        return <div className="px-6 py-14 text-center text-sm text-slate-500">暂无题目</div>;
    }
    return questions.map((question) => (
        <QuestionListItem
            key={question.question_id}
            categoryName={categoryNameById.get(question.category_id) || question.category_id}
            onArchive={onArchive}
            onEdit={onEdit}
            onPublish={onPublish}
            question={question}
        />
    ));
}

interface QuestionListItemProps {
    readonly categoryName: string;
    readonly onArchive: (question: SalesTrainerQuestion) => void;
    readonly onEdit: (questionId: string) => void;
    readonly onPublish: (question: SalesTrainerQuestion) => void;
    readonly question: SalesTrainerQuestion;
}

function QuestionListItem({
    categoryName,
    onArchive,
    onEdit,
    onPublish,
    question,
}: QuestionListItemProps) {
    return (
        <article className="grid gap-4 px-6 py-5 transition-colors hover:bg-slate-50/70 xl:grid-cols-[minmax(0,1fr)_220px]">
            <div className="min-w-0 space-y-3">
                <div className="flex flex-wrap items-center gap-2">
                    <Badge className="bg-slate-900 text-white">
                        {QUESTION_TYPE_LABELS[question.question_type]}
                    </Badge>
                    <Badge className={getStatusTone(question.status)}>{QUESTION_STATUS_LABELS[question.status]}</Badge>
                    <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
                        {DIFFICULTY_LABELS[question.difficulty]}
                    </span>
                    {question.ai_scoring ? (
                        <span className="rounded-full bg-blue-50 px-3 py-1 text-xs font-medium text-blue-700">
                            AI评分
                        </span>
                    ) : null}
                </div>
                <div>
                    <h3 className="text-base font-bold text-slate-950">{question.title}</h3>
                    <p className="mt-1 line-clamp-2 text-sm leading-6 text-slate-600">{question.stem}</p>
                </div>
                <div className="flex flex-wrap gap-2 text-xs text-slate-500">
                    <span className="rounded-full bg-white px-3 py-1 ring-1 ring-slate-200">
                        {categoryName}
                    </span>
                    {question.tags.map((tag) => (
                        <span key={tag} className="rounded-full bg-white px-3 py-1 ring-1 ring-slate-200">
                            #{displayQuestionTag(tag)}
                        </span>
                    ))}
                </div>
            </div>
            <div className="flex items-center gap-2 xl:justify-end">
                <Button variant="outline" size="sm" onClick={() => onEdit(question.question_id)}>
                    编辑
                </Button>
                {question.status !== "published" ? (
                    <Button variant="outline" size="sm" onClick={() => onPublish(question)}>
                        <CheckCircle2 className="mr-1 h-4 w-4" />
                        发布
                    </Button>
                ) : null}
                {question.status !== "archived" ? (
                    <Button variant="ghost" size="sm" onClick={() => onArchive(question)}>
                        <Archive className="mr-1 h-4 w-4" />
                        归档
                    </Button>
                ) : null}
            </div>
        </article>
    );
}

function getStatusTone(status: SalesTrainerQuestion["status"]): string {
    if (status === "published") {
        return "border-emerald-200 bg-emerald-50 text-emerald-700";
    }
    if (status === "archived") {
        return "border-slate-200 bg-slate-100 text-slate-500";
    }
    return "border-amber-200 bg-amber-50 text-amber-700";
}
