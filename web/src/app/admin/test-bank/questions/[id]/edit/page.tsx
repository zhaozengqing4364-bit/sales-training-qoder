"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { AdminFormShell } from "@/components/admin/admin-layout-shells";
import { TestBankQuestionForm } from "@/components/admin/test-bank/test-bank-question-form";
import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api/client";
import type { QuestionItem } from "@/lib/api/types";

export default function EditTestBankQuestionPage() {
    const router = useRouter();
    const params = useParams();
    const questionId = params.id as string;
    const [question, setQuestion] = useState<QuestionItem | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        void (async () => {
            try {
                const result = await api.testBank.listQuestions();
                const found = (result.items || []).find((item) => item.question_id === questionId);
                if (!found) { setError("题目不存在"); return; }
                if (found.status !== "draft") { setError("仅草稿题目可编辑"); return; }
                setQuestion(found);
            } catch (err) {
                setError(err instanceof Error ? err.message : "加载失败");
            } finally {
                setLoading(false);
            }
        })();
    }, [questionId]);

    if (loading) return <GlassCard className="p-8">加载中...</GlassCard>;
    if (error || !question) return <GlassCard className="space-y-4 p-8"><p className="text-red-700">{error}</p><Button onClick={() => router.push("/admin/test-bank")}>返回</Button></GlassCard>;

    return (
        <AdminFormShell backHref="/admin/test-bank" title={`编辑：${question.title}`}>
            <TestBankQuestionForm mode="edit" questionId={questionId} initialQuestion={question} onSaved={() => router.push("/admin/test-bank")} onCancel={() => router.push("/admin/test-bank")} />
        </AdminFormShell>
    );
}
