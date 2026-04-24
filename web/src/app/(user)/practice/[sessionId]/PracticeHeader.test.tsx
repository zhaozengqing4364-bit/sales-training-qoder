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
        fireEvent.click(screen.getAllByRole("button", { name: /暂停/ })[0]);
        fireEvent.click(screen.getByRole("button", { name: /结束练习/ }));

        expect(onExit).toHaveBeenCalledTimes(1);
        expect(onTogglePauseResume).toHaveBeenCalledTimes(1);
        expect(onEndSession).toHaveBeenCalledTimes(1);
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
                onTogglePauseResume={vi.fn()}
                onEndSession={vi.fn()}
            />,
        );

        expect(screen.getByText("PPT演讲练习")).toBeTruthy();
        expect(screen.getByText("重连中...")).toBeTruthy();
        expect(screen.getByText("00:09")).toBeTruthy();
        expect(screen.getByText("Realtime 模式")).toBeTruthy();
        expect(screen.getByRole("button", { name: /继续练习/ })).toBeTruthy();
    });
});
