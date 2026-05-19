import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { formatPracticeElapsedTime, PracticeHeader } from "./PracticeHeader";

describe("PracticeHeader", () => {
    it("formats elapsed time exactly as the previous inline practice header did", () => {
        expect(formatPracticeElapsedTime(0)).toBe("00:00");
        expect(formatPracticeElapsedTime(65)).toBe("01:05");
        expect(formatPracticeElapsedTime(3600 + 9)).toBe("60:09");
    });

    it("renders sales status labels and wires lifecycle actions without changing button semantics", () => {
        const onExit = vi.fn();
        const onBackToTraining = vi.fn();
        const onTogglePauseResume = vi.fn();
        const onEndSession = vi.fn();

        render(
            <PracticeHeader
                scenarioType="sales"
                connectionState="connected"
                connectionStatusLabel="已连接"
                sessionStatusLabel="进行中"
                voiceMode="legacy"
                sessionTime={125}
                canToggleLifecycle={true}
                pendingLifecycleAction={null}
                isSessionPaused={false}
                isEndingSession={false}
                isSessionTerminal={false}
                endButtonLabel="生成报告中..."
                onExit={onExit}
                onBackToTraining={onBackToTraining}
                onTogglePauseResume={onTogglePauseResume}
                onEndSession={onEndSession}
            />,
        );

        expect(screen.getByText("销售对练")).toBeTruthy();
        expect(screen.getByText("已连接")).toBeTruthy();
        expect(screen.getByText("02:05")).toBeTruthy();
        expect(screen.getByText("进行中")).toBeTruthy();
        expect(screen.getByText("经典模式")).toBeTruthy();

        fireEvent.click(screen.getByRole("button", { name: "退出练习并返回首页" }));
        fireEvent.click(screen.getByRole("button", { name: /返回训练大厅/ }));
        fireEvent.click(screen.getAllByRole("button", { name: /暂停/ })[0]);

        // Ending session now requires confirmation — click "结束练习" should not call onEndSession yet
        fireEvent.click(screen.getByRole("button", { name: /结束练习/ }));
        expect(onEndSession).not.toHaveBeenCalled();

        expect(onExit).toHaveBeenCalledTimes(1);
        expect(onBackToTraining).toHaveBeenCalledTimes(1);
        expect(onTogglePauseResume).toHaveBeenCalledTimes(1);
    });

    it("requires confirmation before ending a practice session", () => {
        const onEndSession = vi.fn();

        render(
            <PracticeHeader
                scenarioType="sales"
                connectionState="connected"
                connectionStatusLabel="已连接"
                sessionStatusLabel="进行中"
                voiceMode="legacy"
                sessionTime={60}
                canToggleLifecycle={true}
                pendingLifecycleAction={null}
                isSessionPaused={false}
                isEndingSession={false}
                isSessionTerminal={false}
                endButtonLabel="生成报告中..."
                onExit={vi.fn()}
                onBackToTraining={vi.fn()}
                onTogglePauseResume={vi.fn()}
                onEndSession={onEndSession}
            />,
        );

        // Click "结束练习" — should show confirmation dialog, not fire onEndSession yet
        fireEvent.click(screen.getByRole("button", { name: /结束练习/ }));
        expect(onEndSession).not.toHaveBeenCalled();

        // Confirm dialog should be visible with learner-friendly copy
        expect(screen.getByText("确认结束练习")).toBeTruthy();
        expect(screen.getByText(/将生成练习报告/)).toBeTruthy();

        // Confirm — should now call onEndSession
        fireEvent.click(screen.getByRole("button", { name: "确认结束" }));
        expect(onEndSession).toHaveBeenCalledTimes(1);
    });

    it("cancels ending session when user dismisses confirmation dialog", () => {
        const onEndSession = vi.fn();

        render(
            <PracticeHeader
                scenarioType="sales"
                connectionState="connected"
                connectionStatusLabel="已连接"
                sessionStatusLabel="进行中"
                voiceMode="legacy"
                sessionTime={60}
                canToggleLifecycle={true}
                pendingLifecycleAction={null}
                isSessionPaused={false}
                isEndingSession={false}
                isSessionTerminal={false}
                endButtonLabel="生成报告中..."
                onExit={vi.fn()}
                onBackToTraining={vi.fn()}
                onTogglePauseResume={vi.fn()}
                onEndSession={onEndSession}
            />,
        );

        // Open confirmation dialog
        fireEvent.click(screen.getByRole("button", { name: /结束练习/ }));
        expect(screen.getByText("确认结束练习")).toBeTruthy();

        // Cancel
        fireEvent.click(screen.getByRole("button", { name: "取消" }));
        expect(onEndSession).not.toHaveBeenCalled();
    });

    it("renders presentation realtime paused state with continue copy", () => {
        render(
            <PracticeHeader
                scenarioType="presentation"
                connectionState="reconnecting"
                connectionStatusLabel="重连中..."
                sessionStatusLabel="已暂停"
                voiceMode="stepfun_realtime"
                sessionTime={9}
                canToggleLifecycle={true}
                pendingLifecycleAction={null}
                isSessionPaused={true}
                isEndingSession={false}
                isSessionTerminal={false}
                endButtonLabel="保存音频中..."
                onExit={vi.fn()}
                onBackToTraining={vi.fn()}
                onTogglePauseResume={vi.fn()}
                onEndSession={vi.fn()}
            />,
        );

        expect(screen.getByText("PPT演讲练习")).toBeTruthy();
        expect(screen.getByText("重连中...")).toBeTruthy();
        expect(screen.getByText("00:09")).toBeTruthy();
        expect(screen.getByText("实时语音模式")).toBeTruthy();
        expect(screen.getByRole("button", { name: /继续练习/ })).toBeTruthy();
    });
});
