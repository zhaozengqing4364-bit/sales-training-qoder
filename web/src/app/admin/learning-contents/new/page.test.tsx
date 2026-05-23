import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import NewLearningContentPage from "./page";

const createMock = vi.hoisted(() => vi.fn());
const pushMock = vi.hoisted(() => vi.fn());

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: pushMock }) }));
vi.mock("next/link", () => ({ default: ({ href, children }: { href: string; children: React.ReactNode }) => <a href={href}>{children}</a> }));
vi.mock("@/components/ui/button", () => ({ Button: ({ children, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) => <button type="button" {...props}>{children}</button> }));
vi.mock("@/components/ui/glass-card", () => ({ GlassCard: ({ children }: { children: React.ReactNode }) => <div>{children}</div> }));
vi.mock("@/lib/debug", () => ({ debug: { error: vi.fn() } }));
vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return { ...actual, api: { ...actual.api, learningContents: { create: createMock } } };
});

describe("NewLearningContentPage", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        createMock.mockResolvedValue({ learning_content_id: "content-new", title: "新学习内容" });
    });

    it("creates learning content and navigates to detail", async () => {
        render(<NewLearningContentPage />);
        fireEvent.change(screen.getByLabelText("标题"), { target: { value: "新学习内容" } });
        fireEvent.click(screen.getByRole("button", { name: "创建内容" }));
        await waitFor(() => expect(createMock).toHaveBeenCalled());
        expect(pushMock).toHaveBeenCalledWith("/admin/learning-contents/content-new");
    });
});
