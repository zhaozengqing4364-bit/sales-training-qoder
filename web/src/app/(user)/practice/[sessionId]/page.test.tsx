import { render, screen } from "@testing-library/react";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import PracticeSessionPage from "./page";

const {
    pushMock,
    replaceMock,
    usePracticeWebSocketMock,
    useAudioRecorderMock,
    usePracticeRuntimeLockMock,
    usePracticeSessionLifecycleMock,
} = vi.hoisted(() => ({
    pushMock: vi.fn(),
    replaceMock: vi.fn(),
    usePracticeWebSocketMock: vi.fn(),
    useAudioRecorderMock: vi.fn(),
    usePracticeRuntimeLockMock: vi.fn(),
    usePracticeSessionLifecycleMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    useParams: () => ({
        sessionId: "session-current",
    }),
    useRouter: () => ({
        push: pushMock,
        replace: replaceMock,
    }),
    useSearchParams: () => new URLSearchParams("scenario_type=sales&voice_mode=legacy"),
}));

vi.mock("@/components/ui/button", () => ({
    Button: ({ children, ...props }: ButtonHTMLAttributes<HTMLButtonElement>) => (
        <button type="button" {...props}>
            {children}
        </button>
    ),
}));

vi.mock("@/components/ui/chat-bubble", () => ({
    ChatBubble: ({ message }: { message: string }) => <div>{message}</div>,
}));

vi.mock("@/components/ui/audio-visualizer", () => ({
    AudioVisualizer: () => <div data-testid="audio-visualizer" />,
}));

vi.mock("@/components/ui/audio-waveform", () => ({
    AudioWaveform: () => <div data-testid="audio-waveform" />,
}));

vi.mock("@/components/ui/glass-sheet", () => ({
    GlassSheet: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

vi.mock("@/components/practice/RightPanelContent", () => ({
    RightPanelContent: ({ liveSessionSummary }: { liveSessionSummary?: { main_issue?: { issue_text?: string | null } | null; focus_type?: string | null } | null }) => (
        <div data-testid="right-panel-content">
            {liveSessionSummary?.focus_type ? <span>{`live-focus:${liveSessionSummary.focus_type}`}</span> : null}
            {liveSessionSummary?.main_issue?.issue_text ? <span>{liveSessionSummary.main_issue.issue_text}</span> : null}
        </div>
    ),
}));

vi.mock("@/hooks/use-practice-websocket", () => ({
    usePracticeWebSocket: (...args: unknown[]) => usePracticeWebSocketMock(...args),
}));

vi.mock("@/hooks/use-audio-recorder", () => ({
    useAudioRecorder: (...args: unknown[]) => useAudioRecorderMock(...args),
}));

vi.mock("./runtime-lock", () => ({
    normalizeVoiceMode: (value: string | null | undefined) =>
        value === "stepfun_realtime" ? "stepfun_realtime" : "legacy",
    usePracticeRuntimeLock: (...args: unknown[]) => usePracticeRuntimeLockMock(...args),
}));

vi.mock("./use-practice-recording-hotkeys", () => ({
    usePracticeRecordingHotkeys: vi.fn(),
}));

vi.mock("./use-practice-session-lifecycle", () => ({
    usePracticeSessionLifecycle: (...args: unknown[]) => usePracticeSessionLifecycleMock(...args),
}));

describe("PracticeSessionPage carry-forward retry focus", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        Element.prototype.scrollIntoView = vi.fn();

        usePracticeWebSocketMock.mockReturnValue({
            connectionState: "connected",
            isConnected: true,
            sessionStatus: "in_progress",
            aiState: "idle",
            messages: [],
            fuzzyDetections: [],
            salesStage: null,
            scores: null,
            liveSessionSummary: null,
            actionCard: null,
            error: null,
            isPlayingAudio: false,
            interimTranscript: "",
            audioUnlocked: true,
            isNetworkSlow: false,
            currentSlide: null,
            points: [],
            forbiddenWords: [],
            sendAudio: vi.fn(),
            sendAudioBinary: vi.fn(),
            sendAudioEnd: vi.fn(),
            startSpeaking: vi.fn(),
            sendInterrupt: vi.fn(),
            unlockAudio: vi.fn(),
            sendMessage: vi.fn(),
            connect: vi.fn(),
        });

        useAudioRecorderMock.mockReturnValue({
            isRecording: false,
            hasPermission: true,
            error: null,
            stream: null,
            startRecording: vi.fn(),
            stopRecording: vi.fn(),
            requestPermission: vi.fn(),
        });

        usePracticeSessionLifecycleMock.mockReturnValue({
            canToggleLifecycle: true,
            handleEndSession: vi.fn(),
            handleTogglePauseResume: vi.fn(),
            isEndingSession: false,
            isSessionPaused: false,
            isSessionTerminal: false,
            lifecycleError: null,
            pendingLifecycleAction: null,
        });
    });

    it("renders the targeted retry callout when runtime lock exposes focus intent", () => {
        usePracticeRuntimeLockMock.mockReturnValue({
            lockedScenarioType: "sales",
            lockedVoiceMode: "legacy",
            lockedAgentId: "agent-1",
            lockedPersonaId: "persona-1",
            lockedPresentationId: undefined,
            focusIntent: {
                version: "retry_focus_v1",
                source_session_id: "session-previous",
                main_issue: {
                    issue_type: "value_unclear",
                    issue_text: "客户还没听懂方案的核心收益。",
                    recovery_rule: "先复述痛点，再补一个客户案例。",
                },
                next_goal: {
                    goal_type: "single_next_goal",
                    goal_text: "下一轮先把 ROI 证据讲清楚。",
                    rule: "客户能复述价值和 ROI 逻辑。",
                },
            },
            sessionMetaError: null,
        });

        render(<PracticeSessionPage />);

        expect(screen.getByText("本次练习聚焦上次复盘问题")).toBeTruthy();
        expect(screen.getByText("这次不是普通新建会话，系统已带入上一轮的主问题和下一轮目标，方便你直接针对性再练。")).toBeTruthy();
        expect(screen.getByText("客户还没听懂方案的核心收益。")).toBeTruthy();
        expect(screen.getByText("修正动作：先复述痛点，再补一个客户案例。")).toBeTruthy();
        expect(screen.getByText("下一轮先把 ROI 证据讲清楚。")).toBeTruthy();
        expect(screen.getByText("判定条件：客户能复述价值和 ROI 逻辑。")).toBeTruthy();
    });

    it("omits the callout for ordinary practice sessions without retry focus", () => {
        usePracticeRuntimeLockMock.mockReturnValue({
            lockedScenarioType: "sales",
            lockedVoiceMode: "legacy",
            lockedAgentId: "agent-1",
            lockedPersonaId: "persona-1",
            lockedPresentationId: undefined,
            focusIntent: null,
            sessionMetaError: null,
        });

        render(<PracticeSessionPage />);

        expect(screen.queryByText("本次练习聚焦上次复盘问题")).toBeNull();
    });

    it("shows degraded coach health in the learner page shell even when the right panel is mocked", () => {
        usePracticeRuntimeLockMock.mockReturnValue({
            lockedScenarioType: "sales",
            lockedVoiceMode: "legacy",
            lockedAgentId: "agent-1",
            lockedPersonaId: "persona-1",
            lockedPresentationId: undefined,
            focusIntent: null,
            sessionMetaError: null,
        });
        usePracticeWebSocketMock.mockReturnValue({
            connectionState: "connected",
            isConnected: true,
            sessionStatus: "in_progress",
            aiState: "idle",
            messages: [],
            fuzzyDetections: [],
            salesStage: {
                current_stage: "objection",
                stage_name: "异议处理",
                key_actions: ["先回应风险", "再补证据"],
                guidance: "保持问题澄清后再推进下一步",
                progress: 0.72,
            },
            scores: {
                overall_score: 84,
                turn_count: 4,
                stage_name: "异议处理",
                suggestions: ["先补一个 ROI 证据，再回应价格异议"],
                dimension_scores: {
                    价值表达: 84,
                },
            },
            liveSessionSummary: null,
            actionCard: null,
            coachHealth: {
                status: "degraded",
                reason: "capability_pipeline_failed",
                message: "实时辅导暂不可用，训练仍可继续。",
            },
            error: null,
            isPlayingAudio: false,
            interimTranscript: "",
            audioUnlocked: true,
            isNetworkSlow: false,
            currentSlide: null,
            points: [],
            forbiddenWords: [],
            sendAudio: vi.fn(),
            sendAudioBinary: vi.fn(),
            sendAudioEnd: vi.fn(),
            startSpeaking: vi.fn(),
            sendInterrupt: vi.fn(),
            unlockAudio: vi.fn(),
            sendMessage: vi.fn(),
            connect: vi.fn(),
        });

        render(<PracticeSessionPage />);

        expect(screen.getByText("辅导状态提醒")).toBeTruthy();
        expect(screen.getByText("实时辅导暂不可用，训练仍可继续。", { exact: true })).toBeTruthy();
        expect(screen.getAllByTestId("right-panel-content")).toHaveLength(2);
    });

    it("passes live same-session summary through to the learner panel", () => {
        usePracticeRuntimeLockMock.mockReturnValue({
            lockedScenarioType: "sales",
            lockedVoiceMode: "legacy",
            lockedAgentId: "agent-1",
            lockedPersonaId: "persona-1",
            lockedPresentationId: undefined,
            focusIntent: null,
            sessionMetaError: null,
        });
        usePracticeWebSocketMock.mockReturnValue({
            connectionState: "connected",
            isConnected: true,
            sessionStatus: "in_progress",
            aiState: "idle",
            messages: [],
            fuzzyDetections: [],
            salesStage: null,
            scores: {
                overall_score: 83,
                turn_count: 4,
                stage_name: "异议处理",
                suggestions: ["先补一个 ROI 证据，再回应价格异议"],
                dimension_scores: {
                    价值表达: 84,
                },
            },
            liveSessionSummary: {
                alignment_used: true,
                stage_key: "objection",
                focus_type: "evidence_gap",
                fallback_reason: null,
                main_issue: {
                    issue_type: "evidence_gap",
                    issue_text: "价值主张缺少案例、数据或ROI支撑，客户很难相信收益承诺。",
                    recovery_rule: "下一轮先给出案例、数据或benchmark，再回应价格/ROI追问。",
                },
                next_goal: {
                    goal_type: "evidence_backing",
                    goal_text: "先用案例、数据或ROI证据支撑主张，再推进下一步。",
                    rule: "至少补上一条证据和一个明确的下一步动作。",
                },
                claim_truth: {
                    status: "evidence_pending",
                    label: "证据待补齐",
                    source: "objection_ledger",
                    reason: "open_objection_ledger",
                    closure_state: "open",
                },
            },
            actionCard: null,
            coachHealth: {
                status: "healthy",
                reason: null,
                message: "实时辅导正常。",
            },
            error: null,
            isPlayingAudio: false,
            interimTranscript: "",
            audioUnlocked: true,
            isNetworkSlow: false,
            currentSlide: null,
            points: [],
            forbiddenWords: [],
            sendAudio: vi.fn(),
            sendAudioBinary: vi.fn(),
            sendAudioEnd: vi.fn(),
            startSpeaking: vi.fn(),
            sendInterrupt: vi.fn(),
            unlockAudio: vi.fn(),
            sendMessage: vi.fn(),
            connect: vi.fn(),
        });

        render(<PracticeSessionPage />);

        expect(screen.getAllByText("live-focus:evidence_gap")).toHaveLength(2);
        expect(screen.getAllByText("价值主张缺少案例、数据或ROI支撑，客户很难相信收益承诺。")).toHaveLength(2);
    });

    it("keeps the learner page shell quiet when coach health is healthy or missing a message", () => {
        usePracticeRuntimeLockMock.mockReturnValue({
            lockedScenarioType: "sales",
            lockedVoiceMode: "legacy",
            lockedAgentId: "agent-1",
            lockedPersonaId: "persona-1",
            lockedPresentationId: undefined,
            focusIntent: null,
            sessionMetaError: null,
        });
        usePracticeWebSocketMock.mockReturnValue({
            connectionState: "connected",
            isConnected: true,
            sessionStatus: "in_progress",
            aiState: "idle",
            messages: [],
            fuzzyDetections: [],
            salesStage: null,
            scores: null,
            liveSessionSummary: null,
            actionCard: null,
            coachHealth: {
                status: "resumed",
                reason: "capability_pipeline_resumed",
            },
            error: null,
            isPlayingAudio: false,
            interimTranscript: "",
            audioUnlocked: true,
            isNetworkSlow: false,
            currentSlide: null,
            points: [],
            forbiddenWords: [],
            sendAudio: vi.fn(),
            sendAudioBinary: vi.fn(),
            sendAudioEnd: vi.fn(),
            startSpeaking: vi.fn(),
            sendInterrupt: vi.fn(),
            unlockAudio: vi.fn(),
            sendMessage: vi.fn(),
            connect: vi.fn(),
        });

        render(<PracticeSessionPage />);

        expect(screen.queryByText("辅导状态提醒")).toBeNull();
        expect(screen.queryByText("实时辅导正常。", { exact: true })).toBeNull();
    });
});
