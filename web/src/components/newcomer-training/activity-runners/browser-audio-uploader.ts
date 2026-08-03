import { api } from "@/lib/api/client";
import { getFoundationUserErrorMessage } from "@/lib/newcomer-training/errors";
import type {
    FoundationActivityWorkspace,
    FoundationAudioRunner,
    FoundationAudioUploadSession,
} from "@/lib/api/types/newcomer-training";

import {
    buildBrowserAudioUploadManifest,
    deleteBrowserAudioDraft,
    readBrowserAudioUploadPart,
    type BrowserAudioDraft,
    type BrowserAudioUploadManifest,
} from "./browser-audio-draft-store";

export type BrowserAudioUploadStage = "preparing" | "uploading" | "finalizing";

export interface BrowserAudioUploadProgress {
    stage: BrowserAudioUploadStage;
    completedParts: number;
    totalParts: number;
}

export class BrowserAudioUploadError extends Error {
    constructor(message: string) {
        super(message);
        this.name = "BrowserAudioUploadError";
    }
}

function audioRunner(workspace: FoundationActivityWorkspace): FoundationAudioRunner {
    if (workspace.runner.kind !== "audio_assessment" && workspace.runner.kind !== "assignment") {
        throw new BrowserAudioUploadError("当前活动不是可上传录音的任务，请刷新后重试。");
    }
    return workspace.runner;
}

function cookie(name: string): string | null {
    if (typeof document === "undefined") return null;
    const encodedName = `${encodeURIComponent(name)}=`;
    const entry = document.cookie
        .split(";")
        .map((item) => item.trim())
        .find((item) => item.startsWith(encodedName));
    if (!entry) return null;
    const value = entry.slice(encodedName.length);
    try {
        return decodeURIComponent(value);
    } catch {
        return value;
    }
}

function isSameOriginUpload(url: string): boolean {
    if (url.startsWith("/")) return true;
    if (typeof window === "undefined") return false;
    try {
        return new URL(url, window.location.href).origin === window.location.origin;
    } catch {
        return false;
    }
}

async function safeUploadError(response: Response): Promise<string> {
    try {
        const payload = await response.json() as {
            message?: unknown;
            error?: { message?: unknown };
        };
        const message = payload.error?.message ?? payload.message;
        if (typeof message === "string" && message.trim()) return message;
    } catch {
        // Signed object-storage responses are often empty or XML; never expose them verbatim.
    }
    return `录音分片上传失败（${response.status}），本地草稿仍已保留，请重试。`;
}

async function putPart(input: {
    url: string;
    headers: Record<string, string>;
    blob: Blob;
    signal?: AbortSignal;
}): Promise<void> {
    const sameOrigin = isSameOriginUpload(input.url);
    const headers = new Headers(input.headers);
    if (sameOrigin) {
        const csrfToken = cookie("app_csrf");
        if (csrfToken && !headers.has("X-CSRF-Token")) {
            headers.set("X-CSRF-Token", csrfToken);
        }
    }
    let response: Response;
    try {
        response = await fetch(input.url, {
            method: "PUT",
            body: input.blob,
            headers,
            credentials: sameOrigin ? "include" : "omit",
            signal: input.signal,
        });
    } catch (cause) {
        if (cause instanceof DOMException && cause.name === "AbortError") throw cause;
        throw new BrowserAudioUploadError("网络中断，录音尚未提交；本地草稿仍已保留，可继续上传。");
    }
    if (!response.ok) {
        throw new BrowserAudioUploadError(await safeUploadError(response));
    }
}

function contentType(draft: BrowserAudioDraft): string {
    const declared = draft.mimeType.split(";", 1)[0]?.trim().toLowerCase();
    if (declared) return declared;
    const extension = draft.filename.split(".").pop()?.toLowerCase();
    return ({
        mp3: "audio/mpeg",
        m4a: "audio/mp4",
        mp4: "audio/mp4",
        wav: "audio/wav",
        webm: "audio/webm",
    } as Record<string, string>)[extension ?? ""] ?? "application/octet-stream";
}

function matchesManifest(
    upload: FoundationAudioUploadSession,
    submissionId: string,
    manifest: BrowserAudioUploadManifest,
    partSizeBytes: number,
): boolean {
    if (
        upload.submission_id !== submissionId
        || upload.part_size_bytes !== partSizeBytes
        || upload.expected_part_count !== manifest.parts.length
        || upload.parts.length !== manifest.parts.length
    ) return false;
    return upload.parts.every((part, index) => {
        const local = manifest.parts[index];
        return Boolean(
            local
            && part.part_number === local.part_number
            && part.size_bytes === local.size_bytes
            && part.sha256 === local.sha256,
        );
    });
}

function idempotencyKey(kind: string, ...parts: string[]): string {
    return ["audio", kind, ...parts].join(":").slice(0, 200);
}

export async function uploadBrowserAudioDraft(input: {
    activityId: string;
    workspace: FoundationActivityWorkspace;
    segmentId: string;
    draft: BrowserAudioDraft;
    signal?: AbortSignal;
    onProgress?: (progress: BrowserAudioUploadProgress) => void;
}): Promise<FoundationActivityWorkspace> {
    if (!input.workspace.attempt) {
        throw new BrowserAudioUploadError("请先开始当前录音任务。");
    }
    const attemptId = input.workspace.attempt.attempt_id;
    let workspace = input.workspace;
    let runner = audioRunner(workspace);
    const segment = runner.segments.find((item) => item.segment_id === input.segmentId);
    if (!segment) {
        throw new BrowserAudioUploadError("当前录音分段不存在，请刷新后重试。");
    }
    const type = contentType(input.draft);
    if (!runner.rules.allowed_content_types.includes(type)) {
        throw new BrowserAudioUploadError("当前录音格式不受支持，请选择 MP3、M4A、WAV 或 WebM 音频。");
    }
    input.onProgress?.({ stage: "preparing", completedParts: 0, totalParts: 0 });
    const manifest = await buildBrowserAudioUploadManifest(
        input.draft,
        runner.rules.part_size_bytes,
    );
    let upload = runner.active_upload;
    if (upload && !matchesManifest(
        upload,
        segment.submission_id,
        manifest,
        runner.rules.part_size_bytes,
    )) {
        throw new BrowserAudioUploadError(
            "服务器上已有另一份未完成录音上传；当前本地草稿仍已保留，请先取消原任务或等待上传会话过期。",
        );
    }
    if (!upload) {
        try {
            workspace = await api.newcomerTraining.executeCommand(
                input.activityId,
                {
                    command_type: "create_upload_session",
                    attempt_id: attemptId,
                    expected_enrollment_version: null,
                    expected_attempt_version: runner.version,
                    payload: {
                        segment_id: input.segmentId,
                        recording_mode: input.draft.source,
                        original_filename: input.draft.filename,
                        content_type: type,
                        size_bytes: input.draft.sizeBytes,
                        duration_seconds: input.draft.durationSeconds,
                        manifest_sha256: manifest.manifestSha256,
                        parts: manifest.parts,
                    },
                },
                idempotencyKey("create", input.draft.draftId, manifest.manifestSha256),
                input.signal,
            );
        } catch (cause) {
            throw new BrowserAudioUploadError(getFoundationUserErrorMessage(cause));
        }
        runner = audioRunner(workspace);
        upload = runner.active_upload;
        if (!upload || !matchesManifest(
            upload,
            segment.submission_id,
            manifest,
            runner.rules.part_size_bytes,
        )) {
            throw new BrowserAudioUploadError("上传会话创建后未能正确恢复，本地草稿仍已保留，请刷新后重试。");
        }
    }

    let completedParts = upload.parts.filter((part) => part.uploaded).length;
    input.onProgress?.({
        stage: "uploading",
        completedParts,
        totalParts: upload.expected_part_count,
    });
    for (const projectedPart of upload.parts) {
        if (projectedPart.uploaded) continue;
        const localPart = manifest.parts[projectedPart.part_number - 1];
        if (!localPart) {
            throw new BrowserAudioUploadError("本地录音分片不完整，请重新准备上传。");
        }
        const blob = await readBrowserAudioUploadPart(
            input.draft.draftId,
            projectedPart.part_number,
        );
        await putPart({
            url: projectedPart.upload_url,
            headers: projectedPart.required_headers,
            blob,
            signal: input.signal,
        });
        try {
            workspace = await api.newcomerTraining.executeCommand(
                input.activityId,
                {
                    command_type: "confirm_upload_part",
                    attempt_id: attemptId,
                    expected_enrollment_version: null,
                    expected_attempt_version: audioRunner(workspace).version,
                    payload: {
                        upload_session_id: upload.upload_session_id,
                        part_number: localPart.part_number,
                        size_bytes: localPart.size_bytes,
                        sha256: localPart.sha256,
                    },
                },
                idempotencyKey("confirm", upload.upload_session_id, String(localPart.part_number)),
                input.signal,
            );
        } catch (cause) {
            throw new BrowserAudioUploadError(getFoundationUserErrorMessage(cause));
        }
        completedParts += 1;
        input.onProgress?.({
            stage: "uploading",
            completedParts,
            totalParts: upload.expected_part_count,
        });
    }

    runner = audioRunner(workspace);
    input.onProgress?.({
        stage: "finalizing",
        completedParts: upload.expected_part_count,
        totalParts: upload.expected_part_count,
    });
    try {
        workspace = await api.newcomerTraining.executeCommand(
            input.activityId,
            {
                command_type: "finalize_upload",
                attempt_id: attemptId,
                expected_enrollment_version: null,
                expected_attempt_version: runner.version,
                payload: { upload_session_id: upload.upload_session_id },
            },
            idempotencyKey("finalize", upload.upload_session_id),
            input.signal,
        );
    } catch (cause) {
        throw new BrowserAudioUploadError(getFoundationUserErrorMessage(cause));
    }
    await deleteBrowserAudioDraft(input.draft.draftId).catch(() => undefined);
    return workspace;
}
