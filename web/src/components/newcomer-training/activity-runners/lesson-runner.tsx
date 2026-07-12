"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type { LearningContent } from "@/lib/api/types";
import type { ActivityRunnerProps } from "./types";

export function LessonRunner({ detail, onRefresh }: ActivityRunnerProps) {
    const runner = detail.runner.type === "lesson" ? detail.runner : null;
    const [content, setContent] = useState<LearningContent | null>(null);
    const [pending, setPending] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const open = async () => {
        if (!runner) return;
        setPending(true); setError(null);
        try { setContent(await api.learningContents.get(runner.learning_content_id)); }
        catch (cause) { setError(getApiErrorMessage(cause)); }
        finally { setPending(false); }
    };
    const complete = async (chapterId?: string) => {
        if (!runner) return;
        setPending(true); setError(null);
        try {
            const result = chapterId ? await api.newcomerTraining.completeLessonChapter(detail.activity.activity_id, chapterId, crypto.randomUUID()) : await api.newcomerTraining.confirmLesson(detail.activity.activity_id, crypto.randomUUID());
            onRefresh?.(result);
        } catch (cause) { setError(getApiErrorMessage(cause)); }
        finally { setPending(false); }
    };
    if (!runner) return <p role="alert" className="rounded-xl bg-red-50 p-3 text-sm text-red-700">活动类型不匹配，请返回模块后重试。</p>;
    return <div className="space-y-4"><p className="text-sm text-slate-600">阅读课程内容并完成学习要求，进度会自动保存。</p>{error && <p role="alert" className="rounded-xl bg-red-50 p-3 text-sm text-red-700">{error}</p>}{!content ? <Button isLoading={pending} onClick={() => void open()}>学习内容</Button> : <div className="space-y-4"><div><h2 className="text-lg font-semibold text-slate-900">{content.title}</h2>{content.summary && <p className="mt-1 text-sm text-slate-600">{content.summary}</p>}</div>{content.chapters.map((chapter) => <section key={chapter.chapter_id} className="rounded-2xl border border-slate-200 p-4"><h3 className="font-semibold text-slate-900">{chapter.title}</h3><div className="mt-3 whitespace-pre-wrap text-sm leading-7 text-slate-700">{chapter.content}</div>{runner.completion_mode === "all_chapters" && <Button className="mt-4" size="sm" variant="secondary" disabled={pending} onClick={() => void complete(chapter.chapter_id)}>完成本章节</Button>}</section>)}{runner.completion_mode === "learner_confirmed" && <Button isLoading={pending} onClick={() => void complete()}>确认完成学习</Button>}</div>}</div>;
}
