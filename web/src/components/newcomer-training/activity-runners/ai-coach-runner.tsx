"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type { ActivityRunnerProps } from "./types";

export function AiCoachRunner({ detail, onRefresh }: ActivityRunnerProps) {
    const [pending, setPending] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [session, setSession] = useState<{ id: string; question: string } | null>(null);
    const [answer, setAnswer] = useState("");
    const [feedback, setFeedback] = useState<string | null>(null);
    const streamController = useRef<AbortController | null>(null);
    useEffect(() => () => streamController.current?.abort(), []);
    const start = async () => {
        setPending(true); setError(null);
        try {
            const result = await api.newcomerTraining.startAiCoach(detail.activity.activity_id, crypto.randomUUID());
            setSession({ id: result.session_id, question: result.first_question });
            onRefresh?.(result.detail);
        } catch (cause) { setError(getApiErrorMessage(cause)); }
        finally { setPending(false); }
    };
    const submit = async () => {
        if (!session || !answer.trim()) { setError("请先填写你的回答。"); return; }
        setPending(true); setError(null);
        try {
            streamController.current?.abort();
            const controller = new AbortController();
            streamController.current = controller;
            for await (const event of api.newcomerTraining.streamAiCoachTurn(detail.activity.activity_id, session.id, answer.trim(), crypto.randomUUID(), controller.signal)) {
                if (event.type === "error") throw new Error(event.message);
                if (event.type !== "result") continue;
                setFeedback(event.feedback);
                setAnswer("");
                if (event.next_question) setSession({ id: event.session_id, question: event.next_question });
                else if (event.status === "completed") setSession(null);
                onRefresh?.(event.detail);
            }
        } catch (cause) { setError(getApiErrorMessage(cause)); }
        finally { streamController.current = null; setPending(false); }
    };
    return <div className="space-y-4"><p className="text-sm text-slate-600">AI 教练会围绕当前活动给出问题、反馈和补练建议。</p>{error && <p role="alert" className="rounded-xl bg-red-50 p-3 text-sm text-red-700">{error}</p>}{feedback && <div aria-live="polite" className="rounded-xl bg-blue-50 p-3 text-sm text-blue-900">{feedback}</div>}{!session ? <Button isLoading={pending} onClick={() => void start()}>进入 AI 辅导</Button> : <div className="space-y-4 rounded-2xl bg-slate-50 p-4"><p className="font-medium text-slate-900">{session.question}</p><label className="block text-sm font-medium text-slate-700">你的回答<textarea rows={5} value={answer} onChange={(event) => setAnswer(event.target.value)} className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2" /></label><Button isLoading={pending} onClick={() => void submit()}>提交回答</Button></div>}</div>;
}
