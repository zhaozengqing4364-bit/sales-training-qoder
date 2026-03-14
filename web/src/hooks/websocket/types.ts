import type { TTSChunkData, InterruptReason } from "../use-streaming-audio-player";

// Re-export types from streaming audio player for consumers
export type { TTSChunkData, InterruptReason } from "../use-streaming-audio-player";

/**
 * Interrupt message data sent to backend
 * 
 * Property 6: Interrupt Stops Playback
 * Property 7: Interrupt Queue Clearing
 * 
 * Validates: Requirements 3.1, 3.2
 */
export interface InterruptMessageData {
    reason: InterruptReason;
    timestamp: number;
}

// WebSocket 消息类型
// Critical Fix #2: 添加stream_id和request_id字段用于消息版本控制
export interface WSMessage {
    type: string;
    timestamp: string;
    trace_id?: string;
    stream_id?: string;  // TTS流ID，用于识别消息属于哪个流
    request_id?: number;  // 请求ID，用于识别消息属于哪个请求
    priority?: "high" | "normal"; // 客户端发送优先级（兼容扩展字段）
    data: unknown;
}

export interface ChatMessage {
    id: string;
    sender: "user" | "ai";
    message: string;
    timestamp: string;
}

export interface FuzzyDetection {
    category: string;
    matched: string[];
    suggestion: string;
    severity: "high" | "medium" | "low";
}

export interface SalesStage {
    current_stage: string;
    stage_name: string;
    key_actions: string[];
    guidance: string;
    progress: number;
}

export interface ScoreDimension {
    name: string;
    score: number;
    trend: "up" | "down" | "stable";
    delta: number;
}

export interface ScoreUpdate {
    session_id?: string;
    turn_count?: number;
    overall_score: number;
    dimension_scores: Record<string, number>;
    suggestions: string[];
    stage_name?: string;
}

export interface ActionCard {
    issue: string;
    replacement: string;
    next_turn_rule: string;
}

export interface SlideUpdate {
    current_page: number;
    page_number?: number;
    total_pages: number | null;
    content?: string;
    page_content?: string;
    image_url?: string;
}

export interface PointCovered {
    point_id: string;
    is_covered: boolean;
    content?: string;
}

export interface ForbiddenWordDetection {
    word: string;
    suggestion: string;
}

export interface TTSAudioData {
    text: string;
    audio: string;
    duration_ms: number;
    fallback?: string;
    audio_format?: string;
}

/**
 * TTS Chunk message data from WebSocket
 * Used for streaming TTS playback
 */
export interface TTSChunkMessage {
    chunk_index: number;
    audio: string;        // Base64 encoded MP3 chunk
    duration_ms: number;
    is_final: boolean;
    text?: string;        // Only on final chunk
    total_duration_ms?: number;  // Only on final chunk
    audio_format?: string; // e.g. mp3 | pcm16
    sample_rate?: number;  // e.g. 24000 for pcm16
}

export type SessionStatus =
    | "preparing"
    | "in_progress"
    | "paused"
    | "completed"
    | "scoring";

export type ConnectionState =
    | "connecting"
    | "connected"
    | "reconnecting"
    | "failed";

export interface PracticeState {
    connectionState: ConnectionState;
    isConnected: boolean;
    isConnecting: boolean;
    sessionStatus: SessionStatus;
    aiState: "listening" | "thinking" | "speaking" | "idle";
    messages: ChatMessage[];
    fuzzyDetections: FuzzyDetection[];
    salesStage: SalesStage | null;
    scores: ScoreUpdate | null;
    actionCard: ActionCard | null;
    error: string | null;
    isPlayingAudio: boolean;
    interimTranscript: string;
    audioUnlocked: boolean;
    /** Whether streaming TTS is currently active */
    isStreamingTTS: boolean;
    /** Whether backpressure is active (audio sending should pause) */
    isBackpressureActive: boolean;
    /** Whether network is slow (backpressure buffer overflow detected) */
    isNetworkSlow: boolean;
    /** PPT slide update */
    currentSlide: SlideUpdate | null;
    /** PPT points tracking */
    points: PointCovered[];
    /** PPT forbidden words detections */
    forbiddenWords: ForbiddenWordDetection[];
}

export interface UsePracticeWebSocketOptions {
    sessionId: string;
    scenarioType: 'sales' | 'presentation';
    agentId?: string;
    personaId?: string;
    voiceMode?: "legacy" | "stepfun_realtime";
    onMessage?: (message: WSMessage) => void;
    onError?: (error: string) => void;
    onTTSAudio?: (data: TTSAudioData) => void;
    /** Callback when a TTS chunk is received (for streaming) */
    onTTSChunk?: (data: TTSChunkData) => void;
    /** Whether to use streaming TTS playback (default: true) */
    useStreamingTTS?: boolean;
}

const RAW_WS_BASE_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:3444";
export const WS_BASE_URL = RAW_WS_BASE_URL.replace(/\/+$/, "").replace(/\/ws$/i, "");

export const INITIAL_PRACTICE_STATE: PracticeState = {
    connectionState: "connecting",
    isConnected: false,
    isConnecting: true,
    sessionStatus: "preparing",
    aiState: "idle",
    messages: [],
    fuzzyDetections: [],
    salesStage: null,
    scores: null,
    actionCard: null,
    error: null,
    isPlayingAudio: false,
    interimTranscript: "",
    audioUnlocked: false,
    isStreamingTTS: false,
    isBackpressureActive: false,
    isNetworkSlow: false,
    currentSlide: null,
    points: [],
    forbiddenWords: [],
};
