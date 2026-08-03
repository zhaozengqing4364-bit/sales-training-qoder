const DATABASE_NAME = "qoder.newcomer-audio-drafts.v1";
const DATABASE_VERSION = 1;
const DRAFTS_STORE = "drafts";
const CHUNKS_STORE = "chunks";
const UPLOAD_PARTS_STORE = "uploadParts";
const CHUNK_READ_BATCH_SIZE = 32;

export type BrowserAudioDraftState = "recording" | "paused" | "ready";

export interface BrowserAudioDraft {
    draftId: string;
    scopeKey: string;
    activityId: string;
    segmentId: string;
    source: "browser" | "file";
    filename: string;
    mimeType: string;
    state: BrowserAudioDraftState;
    durationSeconds: number;
    sizeBytes: number;
    chunkCount: number;
    createdAt: number;
    updatedAt: number;
    expiresAt: number;
    uploadPartSizeBytes?: number;
    uploadPartCount?: number;
    uploadManifestSha256?: string;
}

interface BrowserAudioChunk {
    draftId: string;
    sequence: number;
    blob: Blob;
}

interface BrowserAudioUploadPart {
    draftId: string;
    partNumber: number;
    sizeBytes: number;
    sha256: string;
    blob: Blob;
}

export interface BrowserAudioUploadPartDeclaration {
    part_number: number;
    size_bytes: number;
    sha256: string;
}

export interface BrowserAudioUploadManifest {
    manifestSha256: string;
    parts: BrowserAudioUploadPartDeclaration[];
}

export class BrowserAudioDraftStorageError extends Error {
    constructor(message = "本地录音草稿暂时无法使用，请检查浏览器存储权限后重试。") {
        super(message);
        this.name = "BrowserAudioDraftStorageError";
    }
}

export function browserAudioDraftScope(
    ownerId: string,
    activityId: string,
    segmentId: string,
): string {
    return `newcomer-audio:v1:${ownerId}:${activityId}:${segmentId}`;
}

function normalizeStorageError(cause: unknown): BrowserAudioDraftStorageError {
    return cause instanceof BrowserAudioDraftStorageError
        ? cause
        : new BrowserAudioDraftStorageError();
}

function requestResult<T>(request: IDBRequest<T>): Promise<T> {
    return new Promise((resolve, reject) => {
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
    });
}

function transactionDone(transaction: IDBTransaction): Promise<void> {
    return new Promise((resolve, reject) => {
        transaction.oncomplete = () => resolve();
        transaction.onerror = () => reject(transaction.error);
        transaction.onabort = () => reject(transaction.error);
    });
}

function openDatabase(): Promise<IDBDatabase> {
    if (typeof indexedDB === "undefined") {
        return Promise.reject(new BrowserAudioDraftStorageError());
    }
    return new Promise((resolve, reject) => {
        const request = indexedDB.open(DATABASE_NAME, DATABASE_VERSION);
        request.onupgradeneeded = () => {
            const database = request.result;
            if (!database.objectStoreNames.contains(DRAFTS_STORE)) {
                const drafts = database.createObjectStore(DRAFTS_STORE, { keyPath: "draftId" });
                drafts.createIndex("scopeKey", "scopeKey", { unique: false });
                drafts.createIndex("expiresAt", "expiresAt", { unique: false });
            }
            if (!database.objectStoreNames.contains(CHUNKS_STORE)) {
                const chunks = database.createObjectStore(CHUNKS_STORE, {
                    keyPath: ["draftId", "sequence"],
                });
                chunks.createIndex("draftId", "draftId", { unique: false });
            }
            if (!database.objectStoreNames.contains(UPLOAD_PARTS_STORE)) {
                const parts = database.createObjectStore(UPLOAD_PARTS_STORE, {
                    keyPath: ["draftId", "partNumber"],
                });
                parts.createIndex("draftId", "draftId", { unique: false });
            }
        };
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
        request.onblocked = () => reject(new BrowserAudioDraftStorageError());
    });
}

async function withTransaction<T>(
    stores: string | string[],
    mode: IDBTransactionMode,
    operation: (transaction: IDBTransaction) => Promise<T>,
): Promise<T> {
    const database = await openDatabase();
    try {
        const transaction = database.transaction(stores, mode);
        const completion = transactionDone(transaction);
        const result = await operation(transaction);
        await completion;
        return result;
    } catch (cause) {
        throw normalizeStorageError(cause);
    } finally {
        database.close();
    }
}

export async function createBrowserAudioDraft(input: {
    scopeKey: string;
    activityId: string;
    segmentId: string;
    source: "browser" | "file";
    filename: string;
    mimeType: string;
    ttlSeconds: number;
}): Promise<BrowserAudioDraft> {
    const now = Date.now();
    const draft: BrowserAudioDraft = {
        draftId: crypto.randomUUID(),
        scopeKey: input.scopeKey,
        activityId: input.activityId,
        segmentId: input.segmentId,
        source: input.source,
        filename: input.filename,
        mimeType: input.mimeType,
        state: "recording",
        durationSeconds: 0,
        sizeBytes: 0,
        chunkCount: 0,
        createdAt: now,
        updatedAt: now,
        expiresAt: now + input.ttlSeconds * 1000,
    };
    return withTransaction(DRAFTS_STORE, "readwrite", async (transaction) => {
        await requestResult(transaction.objectStore(DRAFTS_STORE).add(draft));
        return draft;
    });
}

export async function appendBrowserAudioChunk(input: {
    draftId: string;
    blob: Blob;
    durationSeconds: number;
    maxSizeBytes: number;
    maxDurationSeconds: number;
}): Promise<BrowserAudioDraft> {
    return withTransaction(
        [DRAFTS_STORE, CHUNKS_STORE],
        "readwrite",
        async (transaction) => {
            const drafts = transaction.objectStore(DRAFTS_STORE);
            const draft = await requestResult<BrowserAudioDraft | undefined>(
                drafts.get(input.draftId),
            );
            if (!draft) {
                throw new BrowserAudioDraftStorageError("本地录音草稿已不存在，请重新录制。");
            }
            const nextSize = draft.sizeBytes + input.blob.size;
            if (nextSize > input.maxSizeBytes) {
                throw new BrowserAudioDraftStorageError("录音已达到当前任务允许的大小上限，请停止并提交较短录音。");
            }
            if (input.durationSeconds > input.maxDurationSeconds) {
                throw new BrowserAudioDraftStorageError("录音已达到当前任务允许的时长上限，请停止并提交。");
            }
            const sequence = draft.chunkCount + 1;
            await requestResult(
                transaction.objectStore(CHUNKS_STORE).add({
                    draftId: draft.draftId,
                    sequence,
                    blob: input.blob,
                } satisfies BrowserAudioChunk),
            );
            const updated: BrowserAudioDraft = {
                ...draft,
                state: "recording",
                durationSeconds: input.durationSeconds,
                sizeBytes: nextSize,
                chunkCount: sequence,
                updatedAt: Date.now(),
            };
            await requestResult(drafts.put(updated));
            return updated;
        },
    );
}

export async function updateBrowserAudioDraft(
    draftId: string,
    changes: Partial<Pick<BrowserAudioDraft, "state" | "durationSeconds" | "filename">>,
): Promise<BrowserAudioDraft> {
    return withTransaction(DRAFTS_STORE, "readwrite", async (transaction) => {
        const store = transaction.objectStore(DRAFTS_STORE);
        const draft = await requestResult<BrowserAudioDraft | undefined>(store.get(draftId));
        if (!draft) {
            throw new BrowserAudioDraftStorageError("本地录音草稿已不存在，请重新录制。");
        }
        const updated: BrowserAudioDraft = { ...draft, ...changes, updatedAt: Date.now() };
        await requestResult(store.put(updated));
        return updated;
    });
}

export async function loadBrowserAudioDraft(scopeKey: string): Promise<BrowserAudioDraft | null> {
    const drafts = await withTransaction(DRAFTS_STORE, "readonly", (transaction) =>
        requestResult<BrowserAudioDraft[]>(
            transaction.objectStore(DRAFTS_STORE).index("scopeKey").getAll(scopeKey),
        ),
    );
    const now = Date.now();
    return drafts
        .filter((draft) => draft.expiresAt > now)
        .sort((left, right) => right.updatedAt - left.updatedAt)[0] ?? null;
}

export async function createBrowserAudioDraftFromFile(input: {
    scopeKey: string;
    activityId: string;
    segmentId: string;
    file: File;
    durationSeconds: number;
    ttlSeconds: number;
    chunkSizeBytes: number;
    maxSizeBytes: number;
    maxDurationSeconds: number;
}): Promise<BrowserAudioDraft> {
    if (input.file.size > input.maxSizeBytes) {
        throw new BrowserAudioDraftStorageError("所选录音文件超过当前任务允许的大小上限。");
    }
    if (input.durationSeconds > input.maxDurationSeconds) {
        throw new BrowserAudioDraftStorageError("所选录音文件超过当前任务允许的时长上限。");
    }
    let draft = await createBrowserAudioDraft({
        scopeKey: input.scopeKey,
        activityId: input.activityId,
        segmentId: input.segmentId,
        source: "file",
        filename: input.file.name,
        mimeType: input.file.type,
        ttlSeconds: input.ttlSeconds,
    });
    try {
        for (let offset = 0; offset < input.file.size; offset += input.chunkSizeBytes) {
            draft = await appendBrowserAudioChunk({
                draftId: draft.draftId,
                blob: input.file.slice(offset, offset + input.chunkSizeBytes, input.file.type),
                durationSeconds: input.durationSeconds,
                maxSizeBytes: input.maxSizeBytes,
                maxDurationSeconds: input.maxDurationSeconds,
            });
        }
        return updateBrowserAudioDraft(draft.draftId, { state: "ready" });
    } catch (cause) {
        await deleteBrowserAudioDraft(draft.draftId).catch(() => undefined);
        throw normalizeStorageError(cause);
    }
}

async function listBrowserAudioChunks(draftId: string): Promise<BrowserAudioChunk[]> {
    const chunks = await withTransaction(CHUNKS_STORE, "readonly", (transaction) =>
        requestResult<BrowserAudioChunk[]>(
            transaction.objectStore(CHUNKS_STORE).index("draftId").getAll(draftId),
        ),
    );
    return chunks.sort((left, right) => left.sequence - right.sequence);
}

async function readBrowserAudioChunkBatch(
    draftId: string,
    startSequence: number,
): Promise<BrowserAudioChunk[]> {
    const keyRange = IDBKeyRange.bound(
        [draftId, startSequence],
        [draftId, Number.MAX_SAFE_INTEGER],
    );
    const chunks = await withTransaction(CHUNKS_STORE, "readonly", (transaction) =>
        requestResult<BrowserAudioChunk[]>(
            transaction.objectStore(CHUNKS_STORE).getAll(keyRange, CHUNK_READ_BATCH_SIZE),
        ),
    );
    return chunks.sort((left, right) => left.sequence - right.sequence);
}

export async function createBrowserAudioPreviewBlob(draft: BrowserAudioDraft): Promise<Blob> {
    const chunks = await listBrowserAudioChunks(draft.draftId);
    if (chunks.length !== draft.chunkCount || chunks.length === 0) {
        throw new BrowserAudioDraftStorageError("本地录音草稿不完整，请重新录制或选择文件。");
    }
    return new Blob(chunks.map((chunk) => chunk.blob), { type: draft.mimeType });
}

async function sha256(value: Blob | string): Promise<string> {
    const bytes = typeof value === "string"
        ? new TextEncoder().encode(value)
        : await value.arrayBuffer();
    const digest = await crypto.subtle.digest("SHA-256", bytes);
    return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

function canonicalManifest(parts: BrowserAudioUploadPartDeclaration[]): string {
    return JSON.stringify(parts.map((part) => ({
        part_number: part.part_number,
        sha256: part.sha256,
        size_bytes: part.size_bytes,
    })));
}

async function clearUploadParts(draftId: string): Promise<void> {
    await withTransaction(UPLOAD_PARTS_STORE, "readwrite", async (transaction) => {
        const store = transaction.objectStore(UPLOAD_PARTS_STORE);
        const keys = await requestResult<IDBValidKey[]>(store.index("draftId").getAllKeys(draftId));
        await Promise.all(keys.map((key) => requestResult(store.delete(key))));
    });
}

async function putUploadPart(part: BrowserAudioUploadPart): Promise<void> {
    await withTransaction(UPLOAD_PARTS_STORE, "readwrite", async (transaction) => {
        await requestResult(transaction.objectStore(UPLOAD_PARTS_STORE).put(part));
    });
}

async function cachedUploadManifest(
    draft: BrowserAudioDraft,
    partSizeBytes: number,
): Promise<BrowserAudioUploadManifest | null> {
    if (
        draft.uploadPartSizeBytes !== partSizeBytes
        || !draft.uploadPartCount
        || !draft.uploadManifestSha256
    ) {
        return null;
    }
    const rows = await withTransaction(UPLOAD_PARTS_STORE, "readonly", (transaction) =>
        requestResult<BrowserAudioUploadPart[]>(
            transaction.objectStore(UPLOAD_PARTS_STORE).index("draftId").getAll(draft.draftId),
        ),
    );
    if (rows.length !== draft.uploadPartCount) {
        return null;
    }
    const parts = rows
        .sort((left, right) => left.partNumber - right.partNumber)
        .map((part) => ({
            part_number: part.partNumber,
            size_bytes: part.sizeBytes,
            sha256: part.sha256,
        }));
    return { parts, manifestSha256: draft.uploadManifestSha256 };
}

export async function buildBrowserAudioUploadManifest(
    draft: BrowserAudioDraft,
    partSizeBytes: number,
): Promise<BrowserAudioUploadManifest> {
    const cached = await cachedUploadManifest(draft, partSizeBytes);
    if (cached) {
        return cached;
    }
    await clearUploadParts(draft.draftId);
    if (draft.chunkCount === 0) {
        throw new BrowserAudioDraftStorageError("本地录音草稿不完整，请重新录制或选择文件。");
    }
    const declarations: BrowserAudioUploadPartDeclaration[] = [];
    let pieces: Blob[] = [];
    let pendingBytes = 0;

    const persistPending = async () => {
        if (pendingBytes === 0) return;
        const blob = new Blob(pieces, { type: draft.mimeType });
        const partNumber = declarations.length + 1;
        const digest = await sha256(blob);
        await putUploadPart({
            draftId: draft.draftId,
            partNumber,
            sizeBytes: blob.size,
            sha256: digest,
            blob,
        });
        declarations.push({ part_number: partNumber, size_bytes: blob.size, sha256: digest });
        pieces = [];
        pendingBytes = 0;
    };

    let expectedSequence = 1;
    while (expectedSequence <= draft.chunkCount) {
        const batch = await readBrowserAudioChunkBatch(draft.draftId, expectedSequence);
        if (batch.length === 0) {
            throw new BrowserAudioDraftStorageError("本地录音草稿不完整，请重新录制或选择文件。");
        }
        for (const chunk of batch) {
            if (chunk.sequence !== expectedSequence || chunk.sequence > draft.chunkCount) {
                throw new BrowserAudioDraftStorageError("本地录音草稿不完整，请重新录制或选择文件。");
            }
            let offset = 0;
            while (offset < chunk.blob.size) {
                const remaining = partSizeBytes - pendingBytes;
                const end = Math.min(chunk.blob.size, offset + remaining);
                const piece = chunk.blob.slice(offset, end, draft.mimeType);
                pieces.push(piece);
                pendingBytes += piece.size;
                offset = end;
                if (pendingBytes === partSizeBytes) {
                    await persistPending();
                }
            }
            expectedSequence += 1;
        }
    }
    await persistPending();
    const manifestSha256 = await sha256(canonicalManifest(declarations));
    await withTransaction(DRAFTS_STORE, "readwrite", async (transaction) => {
        const store = transaction.objectStore(DRAFTS_STORE);
        const current = await requestResult<BrowserAudioDraft | undefined>(store.get(draft.draftId));
        if (!current) throw new BrowserAudioDraftStorageError();
        await requestResult(store.put({
            ...current,
            uploadPartSizeBytes: partSizeBytes,
            uploadPartCount: declarations.length,
            uploadManifestSha256: manifestSha256,
            updatedAt: Date.now(),
        } satisfies BrowserAudioDraft));
    });
    return { parts: declarations, manifestSha256 };
}

export async function readBrowserAudioUploadPart(
    draftId: string,
    partNumber: number,
): Promise<Blob> {
    const part = await withTransaction(UPLOAD_PARTS_STORE, "readonly", (transaction) =>
        requestResult<BrowserAudioUploadPart | undefined>(
            transaction.objectStore(UPLOAD_PARTS_STORE).get([draftId, partNumber]),
        ),
    );
    if (!part) {
        throw new BrowserAudioDraftStorageError("待上传录音分片已不存在，请重新准备上传。");
    }
    return part.blob;
}

export async function deleteBrowserAudioDraft(draftId: string): Promise<void> {
    await withTransaction(
        [DRAFTS_STORE, CHUNKS_STORE, UPLOAD_PARTS_STORE],
        "readwrite",
        async (transaction) => {
            const chunks = transaction.objectStore(CHUNKS_STORE);
            const parts = transaction.objectStore(UPLOAD_PARTS_STORE);
            const [chunkKeys, partKeys] = await Promise.all([
                requestResult<IDBValidKey[]>(chunks.index("draftId").getAllKeys(draftId)),
                requestResult<IDBValidKey[]>(parts.index("draftId").getAllKeys(draftId)),
            ]);
            for (const key of chunkKeys) chunks.delete(key);
            for (const key of partKeys) parts.delete(key);
            transaction.objectStore(DRAFTS_STORE).delete(draftId);
        },
    );
}

export async function cleanupExpiredBrowserAudioDrafts(now = Date.now()): Promise<number> {
    const expired = await withTransaction(DRAFTS_STORE, "readonly", (transaction) =>
        requestResult<BrowserAudioDraft[]>(
            transaction.objectStore(DRAFTS_STORE).index("expiresAt").getAll(IDBKeyRange.upperBound(now)),
        ),
    );
    for (const draft of expired) {
        await deleteBrowserAudioDraft(draft.draftId);
    }
    return expired.length;
}

export function clearBrowserAudioDraftDatabase(): void {
    if (typeof indexedDB === "undefined") return;
    indexedDB.deleteDatabase(DATABASE_NAME);
}

export const BROWSER_AUDIO_DRAFT_DATABASE_NAME = DATABASE_NAME;
