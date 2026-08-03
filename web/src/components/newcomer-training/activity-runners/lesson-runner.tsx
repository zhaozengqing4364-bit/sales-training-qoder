"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronLeft, ChevronRight, Download, ExternalLink } from "lucide-react";

import { Button } from "@/components/ui/button";
import { api } from "@/lib/api/client";
import type {
    FoundationActivityCommand,
    FoundationActivityWorkspace,
    FoundationLessonContentBlock,
} from "@/lib/api/types/newcomer-training";
import { createIdempotencyTokenStore } from "@/lib/idempotency-token-store";
import { trackFoundationUxEvent } from "@/lib/newcomer-training/ux-events";
import { getFoundationUserErrorMessage } from "@/lib/newcomer-training/errors";
import type { ActivityRunnerProps } from "./types";

export function LessonRunner({ detail, onRefresh }: ActivityRunnerProps) {
    const runner = detail.runner.kind === "lesson" ? detail.runner : null;
    const [completedCheckpointIds, setCompletedCheckpointIds] = useState<string[]>(
        runner?.progress?.completed_checkpoint_ids ?? [],
    );
    const [pending, setPending] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const tokenStore = useRef(createIdempotencyTokenStore());

    useEffect(() => {
        if (runner) {
            setCompletedCheckpointIds(runner.progress?.completed_checkpoint_ids ?? []);
        }
    }, [runner]);

    const requiredCheckpointIds = useMemo(
        () => runner?.checkpoints.filter((checkpoint) => checkpoint.required).map((checkpoint) => checkpoint.checkpoint_id) ?? [],
        [runner],
    );

    if (!runner) {
        return <p role="alert" className="rounded-xl bg-red-50 p-3 text-sm text-red-700">活动类型不匹配，请返回训练路径后重试。</p>;
    }

    const execute = async (command: FoundationActivityCommand, inputKey: string) => {
        const result = await api.newcomerTraining.executeCommand(
            detail.activity.id,
            command,
            tokenStore.current.tokenFor(inputKey),
        );
        tokenStore.current.complete(inputKey);
        if (command.command_type === "start" || command.command_type === "start_relearn") {
            trackFoundationUxEvent("activity_started", "lesson");
            if (command.command_type === "start_relearn") trackFoundationUxEvent("remediation_started", "lesson");
        } else if (command.command_type === "save_progress") {
            trackFoundationUxEvent("progress_saved", "lesson");
        }
        onRefresh?.(result);
        return result;
    };

    const start = async () => {
        const relearn = detail.available_commands.includes("start_relearn");
        const inputKey = `${detail.activity.id}:${relearn ? "start-relearn" : "start"}:${detail.enrollment_version}`;
        setPending(true);
        setError(null);
        try {
            await execute({
                command_type: relearn ? "start_relearn" : "start",
                attempt_id: null,
                expected_enrollment_version: detail.enrollment_version,
                expected_attempt_version: null,
                payload: { relearn_of_detail_id: relearn ? runner.detail_id : null },
            }, inputKey);
        } catch (cause) {
            setError(getFoundationUserErrorMessage(cause));
        } finally {
            setPending(false);
        }
    };

    const save = async (workspace: FoundationActivityWorkspace = detail) => {
        if (!workspace.attempt || workspace.runner.kind !== "lesson") {
            throw new Error("学习记录尚未开始");
        }
        const sortedIds = [...completedCheckpointIds].sort();
        const inputKey = `${workspace.attempt.attempt_id}:save:${workspace.runner.version}:${sortedIds.join(",")}`;
        return execute({
            command_type: "save_progress",
            attempt_id: workspace.attempt.attempt_id,
            expected_enrollment_version: null,
            expected_attempt_version: workspace.runner.version,
            payload: {
                completed_checkpoint_ids: sortedIds,
                reading_position: { section: "checkpoints" },
            },
        }, inputKey);
    };

    const saveProgress = async () => {
        setPending(true);
        setError(null);
        try {
            await save();
        } catch (cause) {
            setError(getFoundationUserErrorMessage(cause));
        } finally {
            setPending(false);
        }
    };

    const complete = async () => {
        const missing = requiredCheckpointIds.filter((id) => !completedCheckpointIds.includes(id));
        if (missing.length > 0) {
            setError("请先完成全部必修检查点。");
            return;
        }
        setPending(true);
        setError(null);
        try {
            let current: FoundationActivityWorkspace = detail;
            const persistedIds = runner.progress?.completed_checkpoint_ids ?? [];
            if (JSON.stringify([...persistedIds].sort()) !== JSON.stringify([...completedCheckpointIds].sort())) {
                current = await save(current);
            }
            if (!current.attempt || current.runner.kind !== "lesson") {
                throw new Error("学习记录尚未开始");
            }
            await execute({
                command_type: "complete",
                attempt_id: current.attempt.attempt_id,
                expected_enrollment_version: null,
                expected_attempt_version: current.runner.version,
                payload: {},
            }, `${current.attempt.attempt_id}:complete:${current.runner.version}`);
        } catch (cause) {
            setError(getFoundationUserErrorMessage(cause));
        } finally {
            setPending(false);
        }
    };

    const canStart = detail.available_commands.includes("start") || detail.available_commands.includes("start_relearn");
    const canSave = detail.available_commands.includes("save_progress");
    const canComplete = detail.available_commands.includes("complete");

    return <div className="space-y-6">
        {error ? <p role="alert" className="rounded-xl bg-red-50 p-3 text-sm text-red-700">{error}</p> : null}
        {canStart ? <div className="rounded-2xl border border-blue-100 bg-blue-50 p-4"><p className="text-sm leading-6 text-blue-900">开始后会记录检查点进度；中途离开时可保存并继续。</p><Button className="mt-3" isLoading={pending} onClick={() => void start()}>{detail.available_commands.includes("start_relearn") ? "开始补学" : "开始学习"}</Button></div> : null}

        <section aria-labelledby="lesson-content-title" className="space-y-5">
            <div><h2 id="lesson-content-title" className="text-xl font-semibold text-slate-950">{runner.title}</h2>{runner.objectives.length > 0 ? <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-6 text-slate-600">{runner.objectives.map((objective) => <li key={objective}>{objective}</li>)}</ul> : null}</div>
            {runner.key_concepts.map((concept) => <article key={concept.concept_id} className="rounded-2xl border border-slate-200 p-5"><h3 className="font-semibold text-slate-900">{concept.title}</h3><div className="mt-3 whitespace-pre-wrap text-sm leading-7 text-slate-700">{concept.content}</div>{concept.sources.length > 0 ? <p className="mt-3 text-xs text-slate-500">依据：{concept.sources.join("、")}</p> : null}</article>)}
            {runner.examples.map((example) => <article key={example.example_id} className="rounded-2xl bg-slate-50 p-5"><h3 className="font-semibold text-slate-900">{example.title}</h3><div className="mt-3 whitespace-pre-wrap text-sm leading-7 text-slate-700">{example.content}</div>{example.sources.length > 0 ? <p className="mt-3 text-xs text-slate-500">依据：{example.sources.join("、")}</p> : null}</article>)}
            {(runner.content_blocks ?? [])
                .filter((block) => block.type !== "checkpoint")
                .map((block) => <LessonContentBlock key={block.block_id} block={block} />)}
        </section>

        {runner.checkpoints.length > 0 ? <fieldset disabled={!canSave || pending} className="rounded-2xl border border-slate-200 p-5 disabled:opacity-70"><legend className="px-1 font-semibold text-slate-900">学习检查点</legend><div className="mt-2 space-y-3">{runner.checkpoints.map((checkpoint) => <label key={checkpoint.checkpoint_id} className="flex items-start gap-3 text-sm leading-6 text-slate-700"><input type="checkbox" className="mt-1 h-4 w-4" checked={completedCheckpointIds.includes(checkpoint.checkpoint_id)} onChange={(event) => setCompletedCheckpointIds((current) => event.target.checked ? [...current, checkpoint.checkpoint_id] : current.filter((id) => id !== checkpoint.checkpoint_id))} /><span>{checkpoint.prompt}{checkpoint.required ? <span className="ml-1 text-red-600">（必修）</span> : null}</span></label>)}</div></fieldset> : null}

        {runner.practice_hints.length > 0 ? <aside className="rounded-2xl bg-amber-50 p-4"><h3 className="text-sm font-semibold text-amber-950">练习提示</h3><ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-6 text-amber-900">{runner.practice_hints.map((hint) => <li key={hint}>{hint}</li>)}</ul></aside> : null}

        {canSave || canComplete ? <div className="flex flex-wrap gap-3">{canSave ? <Button variant="secondary" disabled={pending} onClick={() => void saveProgress()}>保存进度</Button> : null}{canComplete ? <Button isLoading={pending} onClick={() => void complete()}>完成学习</Button> : null}</div> : null}
    </div>;
}

function LessonContentBlock({ block }: { block: FoundationLessonContentBlock }) {
    if (block.type === "checkpoint") return null;
    const heading = <div><h3 className="font-semibold text-slate-950">{block.title}</h3>{block.description ? <p className="mt-1 text-sm leading-6 text-slate-600">{block.description}</p> : null}</div>;
    if (block.type === "rich_text" || block.type === "source_excerpt") {
        const content = block.type === "rich_text" ? block.markdown : block.excerpt;
        return <article className="rounded-2xl border border-slate-200 p-5">{heading}<div className="mt-4 whitespace-pre-wrap break-words text-sm leading-7 text-slate-700">{content}</div><SourceLabel label={block.source_label} /></article>;
    }
    if (block.type === "slide_deck") return <SlideDeckBlock block={block} />;
    if (block.type === "video") {
        return <article className="space-y-4 rounded-2xl border border-slate-200 p-5">{heading}{block.availability === "external" && block.external_url ? <div className="rounded-xl bg-slate-50 p-4 text-sm text-slate-700"><p>该 Demo 在受控外部页面打开，网络不可用时可稍后重试；打开链接不会自动完成学习。</p><a href={block.external_url} target="_blank" rel="noreferrer" className="mt-3 inline-flex min-h-11 items-center font-semibold text-blue-700 underline"><ExternalLink className="mr-2 h-4 w-4" />打开 Demo 页面</a></div> : block.availability === "ready" && block.access?.playback ? <video className="max-h-[70vh] w-full rounded-xl bg-black" controls preload="metadata" aria-label={block.accessibility_alt}><source src={block.access.playback} /></video> : <UnavailableMaterial /> }<SourceLabel label={block.source_label} /></article>;
    }
    if (block.type === "audio_example") {
        return <article className="space-y-4 rounded-2xl border border-slate-200 p-5">{heading}{block.availability === "ready" && block.access?.playback ? <audio className="w-full" controls preload="metadata" aria-label={block.accessibility_alt}><source src={block.access.playback} /></audio> : <UnavailableMaterial />}<SourceLabel label={block.source_label} /></article>;
    }
    return <article className="space-y-4 rounded-2xl border border-slate-200 p-5">{heading}{block.availability === "ready" && block.access?.download ? <a href={block.access.download} className="inline-flex min-h-11 max-w-full items-center break-all font-semibold text-blue-700 underline"><Download className="mr-2 h-4 w-4 shrink-0" />{block.download_label || block.filename || "下载附件"}</a> : <UnavailableMaterial />}<SourceLabel label={block.source_label} /></article>;
}

function SlideDeckBlock({ block }: { block: Extract<FoundationLessonContentBlock, { type: "slide_deck" }> }) {
    const lastPage = Math.max(block.start_page, block.end_page ?? block.page_count ?? block.start_page);
    const [page, setPage] = useState(block.start_page);
    const [failed, setFailed] = useState(false);
    const template = block.access?.preview_page_template;
    const previewUrl = template?.replace("{page}", String(page));
    return <article className="space-y-4 rounded-2xl border border-slate-200 p-5">
        <div><h3 className="font-semibold text-slate-950">{block.title}</h3>{block.description ? <p className="mt-1 text-sm leading-6 text-slate-600">{block.description}</p> : null}</div>
        {block.availability === "ready" && previewUrl && !failed ? <img src={previewUrl} alt={`${block.accessibility_alt}，第 ${page} 页`} className="mx-auto max-h-[75vh] w-full rounded-xl border border-slate-200 bg-white object-contain" onError={() => setFailed(true)} /> : <div role="status" className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950"><p>{failed ? `第 ${page} 页预览暂不可用。` : "PPT 预览尚不可用。"}</p>{block.access?.download ? <a className="mt-2 inline-flex min-h-11 items-center font-semibold underline" href={block.access.download}><Download className="mr-2 h-4 w-4" />下载原文件查看</a> : null}</div>}
        <div className="flex flex-wrap items-center justify-between gap-3"><p className="text-sm text-slate-600">第 {page} / {lastPage} 页</p><div className="flex gap-2"><Button type="button" size="sm" variant="outline" disabled={page <= block.start_page} onClick={() => { setPage((value) => value - 1); setFailed(false); }}><ChevronLeft className="mr-1 h-4 w-4" />上一页</Button><Button type="button" size="sm" variant="outline" disabled={page >= lastPage} onClick={() => { setPage((value) => value + 1); setFailed(false); }}>下一页<ChevronRight className="ml-1 h-4 w-4" /></Button></div></div>
        <SourceLabel label={block.source_label} />
    </article>;
}

function SourceLabel({ label }: { label: string }) {
    return <p className="text-xs text-slate-500">依据：{label}</p>;
}

function UnavailableMaterial() {
    return <div role="status" className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">材料暂时不可播放，请刷新活动或联系培训负责人；已保存的学习进度不会丢失。</div>;
}
