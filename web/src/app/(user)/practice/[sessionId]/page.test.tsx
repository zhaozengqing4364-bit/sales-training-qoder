import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import PracticeSessionPage from "./page";

const {
    pushMock,
    replaceMock,
    getAgentWithPersonasMock,
    getPresentationMock,
    getPresentationProgressMock,
    savePresentationProgressMock,
    sendMessageMock,
    usePracticeWebSocketMock,
    useAudioRecorderMock,
    useContinuousAudioUploaderMock,
    usePracticeRuntimeLockMock,
    usePracticeSessionLifecycleMock,
    searchParamsMock,
} = vi.hoisted(() => ({
    pushMock: vi.fn(),
    replaceMock: vi.fn(),
    getAgentWithPersonasMock: vi.fn(),
    getPresentationMock: vi.fn(),
    getPresentationProgressMock: vi.fn(),
    savePresentationProgressMock: vi.fn(),
    sendMessageMock: vi.fn(),
    usePracticeWebSocketMock: vi.fn(),
    useAudioRecorderMock: vi.fn(),
    useContinuousAudioUploaderMock: vi.fn(),
    usePracticeRuntimeLockMock: vi.fn(),
    usePracticeSessionLifecycleMock: vi.fn(),
    searchParamsMock: { current: "scenario_type=sales&voice_mode=legacy" },
}));

vi.mock("next/navigation", () => ({
    useParams: () => ({
        sessionId: "session-current",
    }),
    useRouter: () => ({
        push: pushMock,
        replace: replaceMock,
    }),
    usePathname: () => "/practice/session-current",
    useSearchParams: () => new URLSearchParams(searchParamsMock.current),
}));

vi.mock("next/link", () => ({
    default: ({ href, children }: { href: string; children: ReactNode }) => <a href={href}>{children}</a>,
}));

vi.mock("@/components/ui/button", () => ({
    Button: ({ children, asChild: _asChild, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { asChild?: boolean }) => (
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
    RightPanelContent: ({ liveSessionSummary, actionCompletionStatus, presentationFocusPage }: { liveSessionSummary?: { main_issue?: { issue_text?: string | null } | null; focus_type?: string | null } | null; actionCompletionStatus?: { label: string } | null; presentationFocusPage?: number | null }) => (
        <div data-testid="right-panel-content">
            {liveSessionSummary?.focus_type ? <span>{`live-focus:${liveSessionSummary.focus_type}`}</span> : null}
            {liveSessionSummary?.main_issue?.issue_text ? <span>{liveSessionSummary.main_issue.issue_text}</span> : null}
            {actionCompletionStatus?.label ? <span>{actionCompletionStatus.label}</span> : null}
            {presentationFocusPage ? <span>{`panel-focus-page:${presentationFocusPage}`}</span> : null}
        </div>
    ),
}));

vi.mock("@/hooks/use-practice-websocket", () => ({
    usePracticeWebSocket: (...args: unknown[]) => usePracticeWebSocketMock(...args),
}));

vi.mock("@/hooks/use-audio-recorder", () => ({
    useAudioRecorder: (...args: unknown[]) => useAudioRecorderMock(...args),
}));

vi.mock("@/hooks/use-continuous-audio-uploader", () => ({
    useContinuousAudioUploader: (...args: unknown[]) => useContinuousAudioUploaderMock(...args),
}));

vi.mock("./runtime-lock", () => ({
    normalizeVoiceMode: (value: string | null | undefined) =>
        value === "stepfun_realtime" ? "stepfun_realtime" : "legacy",
    usePracticeRuntimeLock: (...args: unknown[]) => usePracticeRuntimeLockMock(...args),
}));

vi.mock("@/lib/api/client", () => ({
    api: {
        agents: {
            getAgentWithPersonas: (...args: unknown[]) => getAgentWithPersonasMock(...args),
        },
        presentations: {
            get: (...args: unknown[]) => getPresentationMock(...args),
            getProgress: (...args: unknown[]) => getPresentationProgressMock(...args),
            saveProgress: (...args: unknown[]) => savePresentationProgressMock(...args),
        },
    },
}));

vi.mock("./use-practice-recording-hotkeys", () => ({
    usePracticeRecordingHotkeys: vi.fn(),
}));

vi.mock("./use-practice-session-lifecycle", () => ({
    usePracticeSessionLifecycle: (...args: unknown[]) => usePracticeSessionLifecycleMock(...args),
}));

async function flushPreflightEffects() {
    await act(async () => {
        await Promise.resolve();
    });
}

function buildPracticeWebSocketMock(overrides: Record<string, unknown> = {}) {
    return {
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
        coachHealth: null,
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
        sendMessage: sendMessageMock,
        connect: vi.fn(),
        ...overrides,
    };
}

function buildAudioRecorderMock(overrides: Record<string, unknown> = {}) {
    return {
        isRecording: false,
        hasPermission: true,
        error: null,
        stream: null,
        startRecording: vi.fn(),
        stopRecording: vi.fn(),
        requestPermission: vi.fn(),
        ...overrides,
    };
}

describe("PracticeSessionPage carry-forward retry focus", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        searchParamsMock.current = "scenario_type=sales&voice_mode=legacy";
        Element.prototype.scrollIntoView = vi.fn();

        usePracticeWebSocketMock.mockReturnValue(buildPracticeWebSocketMock());

        useAudioRecorderMock.mockReturnValue(buildAudioRecorderMock());

        usePracticeSessionLifecycleMock.mockReturnValue({
            canToggleLifecycle: true,
            handleEndSession: vi.fn(),
            handleStartSession: vi.fn(),
            handleTogglePauseResume: vi.fn(),
            isEndingSession: false,
            isSessionPaused: false,
            isSessionTerminal: false,
            lifecycleError: null,
            pendingLifecycleAction: null,
        });
        useContinuousAudioUploaderMock.mockReturnValue({
            isUploading: false,
            segmentCount: 0,
            pendingUploads: 0,
            lastError: null,
            uploadStatus: "idle",
            startUpload: vi.fn(),
            stopUpload: vi.fn(),
            flushAndStop: vi.fn(),
        });

        getAgentWithPersonasMock.mockResolvedValue({
            id: "agent-1",
            name: "企业版销售教练",
            description: "重点训练价值翻译和 ROI 证据表达。",
            personas: [
                {
                    id: "persona-1",
                    name: "谨慎型采购经理",
                    description: "会反复确认投入产出、落地周期和风险控制。",
                },
            ],
        });
        getPresentationMock.mockResolvedValue({
            presentation_id: "presentation-1",
            title: "企业协同平台方案",
            page_count: 12,
            total_pages: 12,
            pages: [],
        });
        getPresentationProgressMock.mockResolvedValue(null);
        savePresentationProgressMock.mockResolvedValue({
            presentation_id: "presentation-1",
            last_page_number: 1,
        });
        sendMessageMock.mockReset();
    });

    afterEach(() => {
        vi.useRealTimers();
    });

    it("renders the targeted retry callout when runtime lock exposes focus intent", async () => {
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
        await flushPreflightEffects();

        expect(screen.getByText("本次练习聚焦上次复盘问题")).toBeTruthy();
        expect(screen.getByText("这次不是普通新建会话，系统已带入上一轮的主问题和下一轮目标，方便你直接针对性再练。")).toBeTruthy();
        expect(screen.getByText("客户还没听懂方案的核心收益。")).toBeTruthy();
        expect(screen.getByText("修正动作：先复述痛点，再补一个客户案例。")).toBeTruthy();
        expect(screen.getByText("下一轮先把 ROI 证据讲清楚。")).toBeTruthy();
        expect(screen.getByText("判定条件：客户能复述价值和 ROI 逻辑。")).toBeTruthy();
    });

    it("offers a backend-saved PPT resume prompt and sends page_change", async () => {
        searchParamsMock.current = "scenario_type=presentation&presentation_id=presentation-1&voice_mode=legacy";
        getPresentationProgressMock.mockResolvedValue({
            source: "user_presentation_progress",
            presentation_id: "presentation-1",
            user_id: "user-1",
            last_page_number: 6,
            last_practice_at: "2026-04-21T06:00:00Z",
        });
        usePracticeRuntimeLockMock.mockReturnValue({
            lockedScenarioType: "presentation",
            lockedVoiceMode: "legacy",
            lockedAgentId: undefined,
            lockedPersonaId: undefined,
            lockedPresentationId: "presentation-1",
            focusIntent: null,
            sessionMetaError: null,
        });

        render(<PracticeSessionPage />);
        await flushPreflightEffects();

        expect(await screen.findByText("PPT 续练提示")).toBeTruthy();
        const continueButton = screen.getByRole("button", { name: "继续第 6 页" });
        fireEvent.click(continueButton);

        expect(sendMessageMock).toHaveBeenCalledWith("page_change", { page_number: 6 });
        expect(getPresentationProgressMock).toHaveBeenCalledWith("presentation-1");
    });

    it("renders a minimal sales preflight brief before the learner starts speaking", async () => {
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
        await flushPreflightEffects();

        expect(await screen.findByText("开始前先看本次练习重点")).toBeTruthy();
        expect(screen.getByText("围绕「企业版销售教练」进行销售对练，开口前先想好价值主张和下一步推进。", { exact: true })).toBeTruthy();
        expect(screen.getByText("系统会重点看价值翻译、证据支撑和异议推进的完成度。", { exact: true })).toBeTruthy();
        expect(screen.getByText("谨慎型采购经理：会反复确认投入产出、落地周期和风险控制。", { exact: true })).toBeTruthy();
        expect(screen.getByText("练习中遇到异常怎么办？")).toBeTruthy();
        expect(screen.getByText(/麦克风或连接异常时，先按故障面板动作重试/)).toBeTruthy();
        const mobileQuickActions = screen.getByRole("navigation", { name: "移动快捷入口" });
        expect(mobileQuickActions).toBeTruthy();
        expect(within(mobileQuickActions).getByRole("link", { name: /训练大厅/ }).getAttribute("href")).toBe("/training");
    });

    it("shows a presentation page focus in preflight and the learner panel", async () => {
        searchParamsMock.current = "scenario_type=presentation&presentation_id=presentation-1&focus=presentation_page&page=2&source_session_id=session-previous";
        usePracticeRuntimeLockMock.mockReturnValue({
            lockedScenarioType: "presentation",
            lockedVoiceMode: "legacy",
            lockedAgentId: undefined,
            lockedPersonaId: undefined,
            lockedPresentationId: "presentation-1",
            focusIntent: null,
            sessionMetaError: null,
        });

        render(<PracticeSessionPage />);
        await flushPreflightEffects();

        expect(await screen.findByText("开始前先看本次练习重点")).toBeTruthy();
        expect(screen.getAllByText("本轮重点页").length).toBeGreaterThan(0);
        expect(screen.getByText("第 2 页")).toBeTruthy();
        expect(screen.getAllByText(/先补齐这一页的必讲点、缺失点或案例证据/).length).toBeGreaterThan(0);
        expect(screen.getAllByText("panel-focus-page:2").length).toBeGreaterThan(0);
    });



    it("prefers persisted runtime focus over URL page focus", async () => {
        searchParamsMock.current = "scenario_type=presentation&presentation_id=presentation-1&focus=presentation_page&page=2";
        usePracticeRuntimeLockMock.mockReturnValue({
            lockedScenarioType: "presentation",
            lockedVoiceMode: "legacy",
            lockedAgentId: undefined,
            lockedPersonaId: undefined,
            lockedPresentationId: "presentation-1",
            focusIntent: {
                version: "presentation_page_retry_v1",
                source_session_id: "session-previous",
                presentation_page: {
                    page_number: 3,
                    reason: "missing_required_points",
                    summary: "第 3 页缺少客户案例。",
                    missing_required_points: ["客户案例"],
                },
            },
            sessionMetaError: null,
        });

        render(<PracticeSessionPage />);
        await flushPreflightEffects();

        expect(await screen.findByText("开始前先看本次练习重点")).toBeTruthy();
        expect(screen.getByText("第 3 页")).toBeTruthy();
        expect(screen.queryByText("第 2 页")).toBeNull();
        expect(screen.getAllByText("panel-focus-page:3").length).toBeGreaterThan(0);
    });

    it("ignores invalid presentation page focus values", async () => {
        searchParamsMock.current = "scenario_type=presentation&presentation_id=presentation-1&focus=presentation_page&page=bad";
        usePracticeRuntimeLockMock.mockReturnValue({
            lockedScenarioType: "presentation",
            lockedVoiceMode: "legacy",
            lockedAgentId: undefined,
            lockedPersonaId: undefined,
            lockedPresentationId: "presentation-1",
            focusIntent: null,
            sessionMetaError: null,
        });

        render(<PracticeSessionPage />);
        await flushPreflightEffects();

        expect(await screen.findByText("开始前先看本次练习重点")).toBeTruthy();
        expect(screen.queryByText("本轮重点页")).toBeNull();
        expect(screen.queryByText(/panel-focus-page/)).toBeNull();
    });

    it("hides the preflight brief after the learner already has conversation history", async () => {
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
            messages: [
                {
                    id: "msg-1",
                    sender: "ai",
                    message: "欢迎回来，我们继续上次的销售对练。",
                    timestamp: new Date().toISOString(),
                },
            ],
            fuzzyDetections: [],
            salesStage: null,
            scores: null,
            liveSessionSummary: null,
            actionCard: null,
            coachHealth: null,
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
            sendMessage: sendMessageMock,
            connect: vi.fn(),
        });

        render(<PracticeSessionPage />);
        await flushPreflightEffects();

        expect(screen.getByText("欢迎回来，我们继续上次的销售对练。")).toBeTruthy();
        expect(screen.queryByText("开始前先看本次练习重点")).toBeNull();
        expect(screen.queryByText("训练目标")).toBeNull();
        expect(screen.queryByText("评价标准")).toBeNull();
        expect(screen.queryByText("角色简介")).toBeNull();
    });

    it("surfaces learner-facing retry guidance when pausing fails", async () => {
        usePracticeRuntimeLockMock.mockReturnValue({
            lockedScenarioType: "sales",
            lockedVoiceMode: "legacy",
            lockedAgentId: "agent-1",
            lockedPersonaId: "persona-1",
            lockedPresentationId: undefined,
            focusIntent: null,
            sessionMetaError: null,
        });
        usePracticeSessionLifecycleMock.mockReturnValue({
            canToggleLifecycle: true,
            handleEndSession: vi.fn(),
            handleTogglePauseResume: vi.fn(),
            isEndingSession: false,
            isSessionPaused: false,
            isSessionTerminal: false,
            lifecycleError: {
                action: "pause",
                message: "暂停失败，请再试一次。",
                guidance: "你可以先继续当前对话，稍后再暂停；如果按钮持续无响应，再结束本次练习后重新进入。",
            },
            pendingLifecycleAction: null,
        });

        render(<PracticeSessionPage />);
        await flushPreflightEffects();

        expect(screen.getByText("暂停失败，请再试一次。", { exact: true })).toBeTruthy();
        expect(screen.getByText("下一步：你可以先继续当前对话，稍后再暂停；如果按钮持续无响应，再结束本次练习后重新进入。", { exact: true })).toBeTruthy();
        expect(screen.getByRole("button", { name: "重试暂停" })).toBeTruthy();
    });

    it("shows connection, microphone, lifecycle, session, and audio evidence faults together", async () => {
        usePracticeRuntimeLockMock.mockReturnValue({
            lockedScenarioType: "sales",
            lockedVoiceMode: "legacy",
            lockedAgentId: "agent-1",
            lockedPersonaId: "persona-1",
            lockedPresentationId: undefined,
            focusIntent: null,
            sessionMetaError: "会话配置缺少客户画像，请返回训练入口重新选择。",
        });
        usePracticeWebSocketMock.mockReturnValue({
            connectionState: "failed",
            isConnected: false,
            sessionStatus: "in_progress",
            aiState: "idle",
            messages: [],
            fuzzyDetections: [],
            salesStage: null,
            scores: null,
            liveSessionSummary: null,
            actionCard: null,
            coachHealth: null,
            error: "连接失败，请检查网络。",
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
            isRecording: true,
            hasPermission: true,
            error: "麦克风被其他应用占用",
            stream: null,
            startRecording: vi.fn(),
            stopRecording: vi.fn(),
            requestPermission: vi.fn(),
        });
        usePracticeSessionLifecycleMock.mockReturnValue({
            canToggleLifecycle: false,
            handleEndSession: vi.fn(),
            handleStartSession: vi.fn(),
            handleTogglePauseResume: vi.fn(),
            isEndingSession: false,
            isSessionPaused: false,
            isSessionTerminal: false,
            lifecycleError: {
                action: "end",
                message: "结束失败，请再试一次。报告生成超时，请稍后再试。",
                guidance: "请先确认连接正常，再点击“结束练习”；如果仍失败，可先重新连接后重试结束。",
            },
            audioEvidenceStatus: {
                status: "timed_out",
                message: "音频证据保存超时，本次报告可能缺少最后一段录音留痕。",
                error: "segment 2 still pending",
            },
            pendingLifecycleAction: null,
        });
        useContinuousAudioUploaderMock.mockReturnValue({
            isUploading: false,
            segmentCount: 2,
            pendingUploads: 1,
            lastError: "OSS PUT 失败",
            uploadStatus: "error",
            startUpload: vi.fn(),
            stopUpload: vi.fn(),
            flushAndStop: vi.fn(),
        });

        render(<PracticeSessionPage />);
        await flushPreflightEffects();

        expect(screen.getByLabelText("练习故障与恢复面板")).toBeTruthy();
        expect(screen.getByText("当前有 6 项需要处理的练习状态")).toBeTruthy();
        expect(screen.getByText("连接失败，请检查网络。", { exact: true })).toBeTruthy();
        expect(screen.getByText("会话配置缺少客户画像，请返回训练入口重新选择。", { exact: true })).toBeTruthy();
        expect(screen.getByText("结束失败，请再试一次。报告生成超时，请稍后再试。", { exact: true })).toBeTruthy();
        expect(screen.getByText("麦克风被其他应用占用", { exact: true })).toBeTruthy();
        expect(screen.getByText("实时对话仍可继续，但回放或报告的音频证据可能缺失。原因：OSS PUT 失败", { exact: true })).toBeTruthy();
        expect(screen.getByText("音频证据保存超时，本次报告可能缺少最后一段录音留痕。 原因：segment 2 still pending", { exact: true })).toBeTruthy();
    });

    it("surfaces automatic start failure with a retry action", async () => {
        const handleStartSession = vi.fn();
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
            sessionStatus: "preparing",
            aiState: "idle",
            messages: [],
            fuzzyDetections: [],
            salesStage: null,
            scores: null,
            liveSessionSummary: null,
            actionCard: null,
            coachHealth: null,
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
        usePracticeSessionLifecycleMock.mockReturnValue({
            canToggleLifecycle: false,
            handleEndSession: vi.fn(),
            handleStartSession,
            handleTogglePauseResume: vi.fn(),
            isEndingSession: false,
            isSessionPaused: false,
            isSessionTerminal: false,
            lifecycleError: {
                action: "start",
                message: "启动训练失败，可重试。",
                guidance: "请先确认连接正常，再点击“重试启动”；如果仍失败，可刷新页面后重新进入训练。",
            },
            pendingLifecycleAction: null,
        });

        render(<PracticeSessionPage />);
        await flushPreflightEffects();

        expect(screen.getByText("启动训练失败，可重试。", { exact: true })).toBeTruthy();
        expect(screen.getByText("下一步：请先确认连接正常，再点击“重试启动”；如果仍失败，可刷新页面后重新进入训练。", { exact: true })).toBeTruthy();
        const retryButton = screen.getByRole("button", { name: "重试启动" });
        expect(retryButton).toBeTruthy();
        await act(async () => {
            retryButton.click();
        });
        expect(handleStartSession).toHaveBeenCalledTimes(1);
    });

    it("shows audio evidence upload failure without blocking the live conversation", async () => {
        const restartUpload = vi.fn();
        const stopUpload = vi.fn();
        usePracticeRuntimeLockMock.mockReturnValue({
            lockedScenarioType: "sales",
            lockedVoiceMode: "legacy",
            lockedAgentId: "agent-1",
            lockedPersonaId: "persona-1",
            lockedPresentationId: undefined,
            focusIntent: null,
            sessionMetaError: null,
        });
        useAudioRecorderMock.mockReturnValue({
            isRecording: true,
            hasPermission: true,
            error: null,
            stream: null,
            startRecording: vi.fn(),
            stopRecording: vi.fn(),
            requestPermission: vi.fn(),
        });
        useContinuousAudioUploaderMock.mockReturnValue({
            isUploading: false,
            segmentCount: 2,
            pendingUploads: 0,
            lastError: "OSS PUT 失败",
            uploadStatus: "error",
            startUpload: restartUpload,
            stopUpload,
            flushAndStop: vi.fn(),
        });

        render(<PracticeSessionPage />);
        await flushPreflightEffects();

        expect(screen.getByText("音频留痕", { exact: true })).toBeTruthy();
        expect(screen.getByText("实时对话仍可继续，但回放或报告的音频证据可能缺失。原因：OSS PUT 失败", { exact: true })).toBeTruthy();
        expect(screen.getByText("留痕失败", { exact: true })).toBeTruthy();
        const retryButton = screen.getByRole("button", { name: "重试留痕" });
        await act(async () => {
            retryButton.click();
        });
        expect(stopUpload).toHaveBeenCalledTimes(1);
        expect(restartUpload).toHaveBeenCalledTimes(1);
    });

    it("shows end-failure guidance with retry and reconnect actions when the interruption needs recovery", async () => {
        const handleEndSession = vi.fn();
        const reconnect = vi.fn();

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
            connectionState: "failed",
            isConnected: false,
            sessionStatus: "in_progress",
            aiState: "idle",
            messages: [],
            fuzzyDetections: [],
            salesStage: null,
            scores: null,
            liveSessionSummary: null,
            actionCard: null,
            coachHealth: null,
            error: "连接失败",
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
            connect: reconnect,
        });
        usePracticeSessionLifecycleMock.mockReturnValue({
            canToggleLifecycle: false,
            handleEndSession,
            handleTogglePauseResume: vi.fn(),
            isEndingSession: false,
            isSessionPaused: false,
            isSessionTerminal: false,
            lifecycleError: {
                action: "end",
                message: "结束失败，请再试一次。报告生成超时，请稍后再试。",
                guidance: "请先确认连接正常，再点击“结束练习”；如果仍失败，可先重新连接后重试结束。",
            },
            pendingLifecycleAction: null,
        });

        render(<PracticeSessionPage />);
        await flushPreflightEffects();

        expect(screen.getByText("结束失败，请再试一次。报告生成超时，请稍后再试。", { exact: true })).toBeTruthy();
        expect(screen.getByText("下一步：请先确认连接正常，再点击“结束练习”；如果仍失败，可先重新连接后重试结束。", { exact: true })).toBeTruthy();
        expect(screen.getByRole("button", { name: "重试结束" })).toBeTruthy();
        expect(screen.getByRole("button", { name: "重新连接" })).toBeTruthy();
    });

    it("shows automatic reconnect guidance while transport recovery is still in progress", async () => {
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
            connectionState: "reconnecting",
            isConnected: false,
            sessionStatus: "in_progress",
            aiState: "idle",
            messages: [],
            fuzzyDetections: [],
            salesStage: null,
            scores: null,
            liveSessionSummary: null,
            actionCard: null,
            coachHealth: null,
            error: "连接中断，正在重连...",
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
        await flushPreflightEffects();

        expect(screen.getByText("连接中断，正在重连...", { exact: true })).toBeTruthy();
        expect(screen.getByText("网络波动，正在自动重连...", { exact: true })).toBeTruthy();
        expect(screen.queryByRole("button", { name: "重新连接" })).toBeNull();
    });

    it("omits the callout for ordinary practice sessions without retry focus", async () => {
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
        await flushPreflightEffects();

        expect(screen.queryByText("本次练习聚焦上次复盘问题")).toBeNull();
    });

    it("shows degraded coach health in the learner page shell even when the right panel is mocked", async () => {
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
        await flushPreflightEffects();

        expect(screen.getByText("辅导状态提醒")).toBeTruthy();
        expect(screen.getByText("实时辅导暂不可用，训练仍可继续。", { exact: true })).toBeTruthy();
        expect(screen.getAllByTestId("right-panel-content")).toHaveLength(2);
    });

    it("passes live same-session summary through to the learner panel", async () => {
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
        await flushPreflightEffects();

        expect(screen.getAllByText("live-focus:evidence_gap")).toHaveLength(2);
        expect(screen.getAllByText("价值主张缺少案例、数据或ROI支撑，客户很难相信收益承诺。")).toHaveLength(2);
    });

    it("keeps the learner page shell quiet when coach health is healthy or missing a message", async () => {
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
        await flushPreflightEffects();

        expect(screen.queryByText("辅导状态提醒")).toBeNull();
        expect(screen.queryByText("实时辅导正常。", { exact: true })).toBeNull();
    });

    it("does not expose developer-only test-mic copy inside the learner practice shell", async () => {
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
        await flushPreflightEffects();

        expect(screen.queryByText("开发工具 · 不属于学员训练主流程", { exact: true })).toBeNull();
        expect(screen.queryByText("麦克风调试工具", { exact: true })).toBeNull();
        expect(screen.queryByText("正常学员练习请从 practice 主页面进入。", { exact: true })).toBeNull();
    });

    it("passes a waiting action completion status to the realtime panel before the learner attempts it", async () => {
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
                overall_score: 70,
                turn_count: 2,
                suggestions: ["先确认预算与决策人"],
                dimension_scores: { 价值表达: 70 },
            },
            liveSessionSummary: null,
            actionCard: {
                issue: "直接跳到报价",
                replacement: "我先确认预算审批链路，再给你报价区间。",
                next_turn_rule: "下一轮先确认预算与决策人。",
            },
            coachHealth: { status: "healthy", reason: null, message: "实时辅导正常。" },
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
        await flushPreflightEffects();

        expect(screen.getAllByText("等待你在下一轮尝试").length).toBeGreaterThan(0);
    });

    it("keeps elapsed practice time across a reconnect using the original start timestamp", async () => {
        vi.useFakeTimers();
        vi.setSystemTime(new Date("2026-04-21T00:00:00Z"));
        usePracticeRuntimeLockMock.mockReturnValue({
            lockedScenarioType: "sales",
            lockedVoiceMode: "legacy",
            lockedAgentId: "agent-1",
            lockedPersonaId: "persona-1",
            lockedPresentationId: undefined,
            focusIntent: null,
            sessionMetaError: null,
        });

        const connectedState = buildPracticeWebSocketMock();
        usePracticeWebSocketMock.mockReturnValue(connectedState);
        const { rerender } = render(<PracticeSessionPage />);
        await flushPreflightEffects();

        act(() => {
            vi.advanceTimersByTime(2000);
        });
        expect(screen.getByText("00:02")).toBeTruthy();

        usePracticeWebSocketMock.mockReturnValue(buildPracticeWebSocketMock({
            connectionState: "reconnecting",
            isConnected: false,
        }));
        rerender(<PracticeSessionPage />);

        act(() => {
            vi.advanceTimersByTime(3000);
        });

        usePracticeWebSocketMock.mockReturnValue(connectedState);
        rerender(<PracticeSessionPage />);

        act(() => {
            vi.advanceTimersByTime(1000);
        });

        expect(screen.getByText("00:06")).toBeTruthy();
    });

    it("does not force-scroll when the learner has intentionally scrolled up in history", async () => {
        usePracticeRuntimeLockMock.mockReturnValue({
            lockedScenarioType: "sales",
            lockedVoiceMode: "legacy",
            lockedAgentId: "agent-1",
            lockedPersonaId: "persona-1",
            lockedPresentationId: undefined,
            focusIntent: null,
            sessionMetaError: null,
        });
        const scrollIntoView = vi.fn();
        Element.prototype.scrollIntoView = scrollIntoView;

        usePracticeWebSocketMock.mockReturnValue(buildPracticeWebSocketMock({
            messages: [{
                id: "msg-1",
                sender: "ai",
                message: "第一条欢迎消息",
                timestamp: "10:00",
            }],
        }));

        const { rerender } = render(<PracticeSessionPage />);
        await flushPreflightEffects();
        scrollIntoView.mockClear();

        const messageList = screen.getByLabelText("练习对话消息");
        Object.defineProperty(messageList, "scrollHeight", { value: 1200, configurable: true });
        Object.defineProperty(messageList, "clientHeight", { value: 400, configurable: true });
        Object.defineProperty(messageList, "scrollTop", { value: 120, configurable: true });
        fireEvent.scroll(messageList);

        usePracticeWebSocketMock.mockReturnValue(buildPracticeWebSocketMock({
            messages: [
                {
                    id: "msg-1",
                    sender: "ai",
                    message: "第一条欢迎消息",
                    timestamp: "10:00",
                },
                {
                    id: "msg-2",
                    sender: "ai",
                    message: "用户仍在上方阅读时到达的新消息",
                    timestamp: "10:01",
                },
            ],
        }));
        rerender(<PracticeSessionPage />);

        expect(scrollIntoView).not.toHaveBeenCalled();
    });

    it("keeps auto-scroll enabled when the learner remains near the bottom", async () => {
        usePracticeRuntimeLockMock.mockReturnValue({
            lockedScenarioType: "sales",
            lockedVoiceMode: "legacy",
            lockedAgentId: "agent-1",
            lockedPersonaId: "persona-1",
            lockedPresentationId: undefined,
            focusIntent: null,
            sessionMetaError: null,
        });
        const scrollIntoView = vi.fn();
        Element.prototype.scrollIntoView = scrollIntoView;

        usePracticeWebSocketMock.mockReturnValue(buildPracticeWebSocketMock({
            messages: [{
                id: "msg-bottom-1",
                sender: "ai",
                message: "底部附近的消息",
                timestamp: "10:00",
            }],
        }));

        const { rerender } = render(<PracticeSessionPage />);
        await flushPreflightEffects();
        scrollIntoView.mockClear();

        const messageList = screen.getByLabelText("练习对话消息");
        Object.defineProperty(messageList, "scrollHeight", { value: 1200, configurable: true });
        Object.defineProperty(messageList, "clientHeight", { value: 400, configurable: true });
        Object.defineProperty(messageList, "scrollTop", { value: 730, configurable: true });
        fireEvent.scroll(messageList);

        usePracticeWebSocketMock.mockReturnValue(buildPracticeWebSocketMock({
            messages: [
                {
                    id: "msg-bottom-1",
                    sender: "ai",
                    message: "底部附近的消息",
                    timestamp: "10:00",
                },
                {
                    id: "msg-bottom-2",
                    sender: "ai",
                    message: "底部附近的新消息",
                    timestamp: "10:01",
                },
            ],
        }));
        rerender(<PracticeSessionPage />);

        expect(scrollIntoView).toHaveBeenCalledTimes(1);
    });

    it("allows immediate retry after microphone permission is denied without a fixed 300ms dead zone", async () => {
        usePracticeRuntimeLockMock.mockReturnValue({
            lockedScenarioType: "sales",
            lockedVoiceMode: "legacy",
            lockedAgentId: "agent-1",
            lockedPersonaId: "persona-1",
            lockedPresentationId: undefined,
            focusIntent: null,
            sessionMetaError: null,
        });
        const requestPermission = vi.fn().mockResolvedValue(false);
        const startRecording = vi.fn();
        useAudioRecorderMock.mockReturnValue(buildAudioRecorderMock({
            hasPermission: false,
            requestPermission,
            startRecording,
        }));

        render(<PracticeSessionPage />);
        await flushPreflightEffects();

        const recordButton = screen.getByRole("button", { name: "点击重新请求麦克风权限" });
        fireEvent.click(recordButton);
        await waitFor(() => {
            expect(requestPermission).toHaveBeenCalledTimes(1);
        });

        fireEvent.click(recordButton);
        await waitFor(() => {
            expect(requestPermission).toHaveBeenCalledTimes(2);
        });
        expect(startRecording).not.toHaveBeenCalled();
    });

});
