"use client";

import Link from "next/link";

import type {
    NewcomerArticle,
    NewcomerExamPaper,
} from "@/lib/api/types";
import type { PathBusinessBindingValue } from "@/lib/sales-trainer/path-config-editing";

interface PathConfigBusinessBindingEditorProps {
    readonly articles: readonly NewcomerArticle[];
    readonly disabled: boolean;
    readonly moduleTitle: string;
    readonly onChange: (value: PathBusinessBindingValue) => void;
    readonly papers: readonly NewcomerExamPaper[];
    readonly value: PathBusinessBindingValue;
}

export function PathConfigBusinessBindingEditor({
    articles,
    disabled,
    moduleTitle,
    onChange,
    papers,
    value,
}: PathConfigBusinessBindingEditorProps) {
    const publishedPapers = papers.filter((paper) => paper.status === "published");
    return (
        <div className="rounded-2xl border border-blue-100 bg-white p-4">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                <div>
                    <p className="text-sm font-black text-slate-900">在配置中心直接绑定学习与考试</p>
                    <p className="mt-1 text-sm text-slate-500">
                        学员端按这里绑定的文章学习，再进入绑定考卷考试。
                    </p>
                </div>
                <div className="flex gap-3 text-sm font-semibold text-blue-700">
                    <Link href="/admin/sales-trainer/articles" className="underline">
                        管理文章
                    </Link>
                    <Link href="/admin/sales-trainer/papers" className="underline">
                        管理考卷
                    </Link>
                </div>
            </div>
            <div className="mt-4 grid gap-3 md:grid-cols-2">
                <div className="space-y-2">
                    <label className="text-sm font-medium text-slate-700" htmlFor="business-skills-learning-content">
                        学习文章（{moduleTitle}）
                    </label>
                    <select
                        id="business-skills-learning-content"
                        value={value.learningContentId}
                        onChange={(event) => onChange({ ...value, learningContentId: event.target.value })}
                        disabled={disabled}
                        className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm"
                    >
                        <option value="">请选择已发布学习文章</option>
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
        </div>
    );
}
