import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SettingsPage from "./page";

const getModelConfigsMock = vi.hoisted(() => vi.fn());

vi.mock("@/components/ui/toast", () => ({
    useToast: () => ({ success: vi.fn(), error: vi.fn() }),
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            admin: {
                ...actual.api.admin,
                getModelConfigs: getModelConfigsMock,
            },
        },
    };
});

describe("SettingsPage", () => {
    beforeEach(() => {
        getModelConfigsMock.mockReset();
        getModelConfigsMock.mockResolvedValue({ llm: [], embedding: [], asr: [], tts: [] });
    });

    it("marks non-model settings as read-only instead of offering fake persistence", () => {
        render(<SettingsPage />);

        expect(screen.getAllByText("这些配置项当前仅展示目标状态，尚未接入持久化接口，暂不会保存。").length).toBeGreaterThan(0);
        expect((screen.getByRole("button", { name: /保存配置/ }) as HTMLButtonElement).disabled).toBe(true);
        expect((screen.getByRole("button", { name: /放弃更改/ }) as HTMLButtonElement).disabled).toBe(true);
        expect(screen.getByDisplayValue("Intelligent Coach AI").hasAttribute("readonly")).toBe(true);
        expect(screen.getByDisplayValue("support@company.com").hasAttribute("readonly")).toBe(true);
    });

    it("keeps the model tab as the only active persisted settings surface", async () => {
        render(<SettingsPage />);

        fireEvent.click(screen.getByText("模型配置"));

        expect((await screen.findByRole("button", { name: /刷新/ }) as HTMLButtonElement).disabled).toBe(false);
        expect(getModelConfigsMock).toHaveBeenCalledTimes(1);
    });
});
