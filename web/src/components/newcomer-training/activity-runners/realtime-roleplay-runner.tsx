"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type { ActivityRunnerProps } from "./types";
export function RealtimeRoleplayRunner({ detail }: ActivityRunnerProps) { const router = useRouter(); const [pending, setPending] = useState(false); const [error, setError] = useState<string | null>(null); return <div className="space-y-4"><p className="text-sm text-slate-600">进入实时语音情境训练。开始前请确认麦克风可用。</p>{error && <p role="alert" className="rounded-xl bg-red-50 p-3 text-sm text-red-700">{error}</p>}<Button isLoading={pending} onClick={async () => { setPending(true); setError(null); try { const result = await api.newcomerTraining.startRealtime(detail.activity.activity_id, crypto.randomUUID()); router.push(`/practice/${encodeURIComponent(result.session_id)}`); } catch (cause) { setError(getApiErrorMessage(cause)); } finally { setPending(false); } }}>开始实时对练</Button></div>; }
