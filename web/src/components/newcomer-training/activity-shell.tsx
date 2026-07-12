"use client";
import type { ComponentType } from "react";
import Link from "next/link";
import type { ActivityType } from "@/lib/api/types/newcomer-training";
import { LessonRunner } from "./activity-runners/lesson-runner";
import { QuizRunner } from "./activity-runners/quiz-runner";
import { AudioAssessmentRunner } from "./activity-runners/audio-assessment-runner";
import { RealtimeRoleplayRunner } from "./activity-runners/realtime-roleplay-runner";
import { AiCoachRunner } from "./activity-runners/ai-coach-runner";
import { AssignmentRunner } from "./activity-runners/assignment-runner";
import type { ActivityRunnerProps } from "./activity-runners/types";
import { ActivityResultPanel } from "./activity-result-panel";

export const ACTIVITY_RUNNERS: Record<ActivityType, ComponentType<ActivityRunnerProps>> = { lesson: LessonRunner, quiz: QuizRunner, audio_assessment: AudioAssessmentRunner, realtime_roleplay: RealtimeRoleplayRunner, ai_coach: AiCoachRunner, assignment: AssignmentRunner };
export function ActivityShell({ detail, onRefresh }: ActivityRunnerProps) { const Runner = ACTIVITY_RUNNERS[detail.activity.activity_type]; const showResult = detail.activity.completed || detail.activity.status === "failed" || (detail.activity.activity_type === "audio_assessment" && detail.activity.status === "in_progress"); const resultOnly = detail.activity.completed || (detail.activity.activity_type === "audio_assessment" && detail.activity.status === "in_progress"); return <main className="mx-auto min-h-screen max-w-3xl bg-slate-50 px-4 py-8"><Link href={`/newcomer-training/modules/${encodeURIComponent(detail.module_id)}`} className="text-sm text-slate-600">← 返回模块</Link><article className="mt-5 rounded-3xl bg-white p-6 shadow-sm md:p-8"><div className="border-b border-slate-100 pb-5"><p className="text-sm font-medium text-blue-700">训练活动</p><h1 className="mt-1 text-2xl font-semibold text-slate-900">{detail.activity.title}</h1>{detail.activity.description && <p className="mt-2 text-slate-500">{detail.activity.description}</p>}</div><div className="mt-6 space-y-5">{detail.activity.locked ? <div role="alert" className="rounded-xl bg-amber-50 p-4 text-amber-900">{detail.activity.lock_reason ?? "请先完成前置活动。"}</div> : <>{showResult ? <ActivityResultPanel status={detail.activity.status} completed={detail.activity.completed} passed={detail.activity.passed} score={detail.activity.score} maxScore={detail.activity.max_score} moduleId={detail.module_id} /> : null}{!resultOnly ? <Runner detail={detail} onRefresh={onRefresh} /> : null}</>}</div></article></main>; }
