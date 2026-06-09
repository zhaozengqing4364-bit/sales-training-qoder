"use client";

import { QuestionCardList } from "@/components/admin/sales-trainer/question-card-list";
import { QuestionGovernanceSidebar } from "@/components/admin/sales-trainer/question-governance-sidebar";
import type { SalesTrainerQuestion, SalesTrainerQuestionCategory } from "@/lib/api/types";

interface QuestionGovernanceWorkspaceProps {
    readonly aiScoredCount: number;
    readonly categories: readonly SalesTrainerQuestionCategory[];
    readonly categoryId: string;
    readonly categoryNameById: ReadonlyMap<string, string>;
    readonly difficulty: string;
    readonly isLoading: boolean;
    readonly onArchive: (question: SalesTrainerQuestion) => void;
    readonly onCategoryChange: (value: string) => void;
    readonly onDifficultyChange: (value: string) => void;
    readonly onEdit: (questionId: string) => void;
    readonly onPublish: (question: SalesTrainerQuestion) => void;
    readonly onRefresh: () => void;
    readonly onStatusChange: (value: string) => void;
    readonly onTagChange: (value: string) => void;
    readonly publishedCount: number;
    readonly questions: readonly SalesTrainerQuestion[];
    readonly status: string;
    readonly tag: string;
}

export function QuestionGovernanceWorkspace({
    aiScoredCount,
    categories,
    categoryId,
    categoryNameById,
    difficulty,
    isLoading,
    onArchive,
    onCategoryChange,
    onDifficultyChange,
    onEdit,
    onPublish,
    onRefresh,
    onStatusChange,
    onTagChange,
    publishedCount,
    questions,
    status,
    tag,
}: QuestionGovernanceWorkspaceProps) {
    return (
        <div className="grid gap-5 xl:grid-cols-[320px_minmax(0,1fr)]">
            <QuestionGovernanceSidebar
                aiScoredCount={aiScoredCount}
                categories={categories}
                categoryId={categoryId}
                difficulty={difficulty}
                onCategoryChange={onCategoryChange}
                onDifficultyChange={onDifficultyChange}
                onRefresh={onRefresh}
                onStatusChange={onStatusChange}
                onTagChange={onTagChange}
                publishedCount={publishedCount}
                questionCount={questions.length}
                status={status}
                tag={tag}
            />
            <QuestionCardList
                categoryNameById={categoryNameById}
                isLoading={isLoading}
                onArchive={onArchive}
                onEdit={onEdit}
                onPublish={onPublish}
                questions={questions}
            />
        </div>
    );
}
