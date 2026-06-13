import type {
    PracticeRuntimePreflight,
    PracticeSessionRuntime,
    RetryFocusIntent,
    SessionLifecycleAction,
    SessionLifecycleRequest,
    SessionLifecycleResponse,
} from "../types";
import type { ApiRequest } from "./shared";

type PracticeDomainDependencies = {
    request: ApiRequest;
};

type AudioSegmentUploadUrl = {
    url: string;
    object_key: string;
    expires_at?: string;
};

type AudioSegment = {
    id?: string;
    segment_sequence: number;
    upload_status: string;
    object_key?: string;
    size_bytes?: number;
    duration_ms?: number | null;
    error_message?: string | null;
};

type AudioSegmentFailureToken =
    | "signing_failed"
    | "oss_put_failed"
    | "register_failed"
    | "network_error"
    | "unknown";

export function createPracticeDomain({ request }: PracticeDomainDependencies) {
    const controlLifecycle = async (sessionId: string, action: SessionLifecycleAction) => {
        const payload: SessionLifecycleRequest = { action };
        return request<SessionLifecycleResponse>(`/practice/sessions/${sessionId}/lifecycle`, {
            method: "POST",
            body: JSON.stringify(payload),
        });
    };

    return {
        createSession: async (data: {
            scenario_type: "sales" | "presentation";
            presentation_id?: string;
            agent_id?: string;
            persona_id?: string;
            scenario_id?: string;
            voice_mode?: "legacy" | "stepfun_realtime";
            runtime_profile_id?: string;
            focus_intent?: RetryFocusIntent;
        }) => {
            return request<{ session_id: string }>("/practice/sessions", {
                method: "POST",
                body: JSON.stringify(data),
            });
        },

        getSession: async (sessionId: string) => {
            return request<PracticeSessionRuntime>(`/practice/sessions/${sessionId}`);
        },

        getRuntimePreflight: async (sessionId: string) => {
            return request<PracticeRuntimePreflight>(
                `/practice/sessions/${sessionId}/runtime-preflight`,
            );
        },

        controlLifecycle,
        startSession: async (sessionId: string) => controlLifecycle(sessionId, "start"),
        pauseSession: async (sessionId: string) => controlLifecycle(sessionId, "pause"),
        resumeSession: async (sessionId: string) => controlLifecycle(sessionId, "resume"),
        endSession: async (sessionId: string) => controlLifecycle(sessionId, "end"),
        audioSegments: {
            createUploadUrl: async (
                sessionId: string,
                payload: { segment_sequence: number; content_type: string },
            ) => {
                return request<AudioSegmentUploadUrl>(`/practice/sessions/${sessionId}/audio-upload-urls`, {
                    method: "POST",
                    body: JSON.stringify(payload),
                });
            },
            register: async (
                sessionId: string,
                payload: {
                    segment_sequence: number;
                    object_key: string;
                    size_bytes: number;
                    duration_ms?: number;
                },
            ) => {
                return request<AudioSegment>(`/practice/sessions/${sessionId}/audio-segments`, {
                    method: "POST",
                    body: JSON.stringify(payload),
                });
            },
            registerFailure: async (
                sessionId: string,
                payload: { segment_sequence: number; error_token: AudioSegmentFailureToken },
            ) => {
                return request<AudioSegment>(`/practice/sessions/${sessionId}/audio-segments/failure`, {
                    method: "POST",
                    body: JSON.stringify(payload),
                });
            },
        },
    };
}
