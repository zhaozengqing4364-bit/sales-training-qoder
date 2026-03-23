import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import PresentationDetailPage from "./page";

const {
    getPresentationMock,
    getForbiddenWordsMock,
    getTalkingPointsMock,
    getThumbnailBlobMock,
    addTalkingPointMock,
    deleteTalkingPointMock,
    addForbiddenWordMock,
    deleteForbiddenWordMock,
    replacePresentationMock,
    successToastMock,
    errorToastMock,
} = vi.hoisted(() => ({
    getPresentationMock: vi.fn(),
    getForbiddenWordsMock: vi.fn(),
    getTalkingPointsMock: vi.fn(),
    getThumbnailBlobMock: vi.fn(),
    addTalkingPointMock: vi.fn(),
    deleteTalkingPointMock: vi.fn(),
    addForbiddenWordMock: vi.fn(),
    deleteForbiddenWordMock: vi.fn(),
    replacePresentationMock: vi.fn(),
    successToastMock: vi.fn(),
    errorToastMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    useParams: () => ({ id: "ppt-1" }),
}));

vi.mock("next/link", () => ({
    default: ({ href, children }: { href: string; children: ReactNode }) => <a href={href}>{children}</a>,
}));

vi.mock("next/image", () => ({
    default: ({ alt, ...props }: { alt: string }) => <img alt={alt} {...props} />,
}));

vi.mock("@/components/ui/toast", () => ({
    useToast: () => ({
        success: successToastMock,
        error: errorToastMock,
    }),
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            presentations: {
                ...actual.api.presentations,
                get: getPresentationMock,
                getForbiddenWords: getForbiddenWordsMock,
                getTalkingPoints: getTalkingPointsMock,
                getThumbnailBlob: getThumbnailBlobMock,
                addTalkingPoint: addTalkingPointMock,
                deleteTalkingPoint: deleteTalkingPointMock,
                addForbiddenWord: addForbiddenWordMock,
                deleteForbiddenWord: deleteForbiddenWordMock,
                replace: replacePresentationMock,
            },
        },
    };
});

describe("PresentationDetailPage", () => {
    beforeEach(() => {
        getPresentationMock.mockReset();
        getForbiddenWordsMock.mockReset();
        getTalkingPointsMock.mockReset();
        getThumbnailBlobMock.mockReset();
        addTalkingPointMock.mockReset();
        deleteTalkingPointMock.mockReset();
        addForbiddenWordMock.mockReset();
        deleteForbiddenWordMock.mockReset();
        replacePresentationMock.mockReset();
        successToastMock.mockReset();
        errorToastMock.mockReset();

        getPresentationMock.mockResolvedValue({
            presentation_id: "ppt-1",
            title: "标准销售演示",
            status: "ready",
            version_number: 2,
            file_size_bytes: 2 * 1024 * 1024,
            page_count: 2,
            total_pages: 2,
            created_at: "2026-03-23T00:00:00Z",
            pages: [
                {
                    page_id: "page-1",
                    page_number: 1,
                    image_url: "/thumb-1.png",
                    extracted_text: "第一页内容",
                },
                {
                    page_id: "page-2",
                    page_number: 2,
                    image_url: "/thumb-2.png",
                    extracted_text: "第二页内容",
                },
            ],
        });
        getForbiddenWordsMock.mockResolvedValue([]);
        getTalkingPointsMock.mockResolvedValue([]);
        getThumbnailBlobMock.mockRejectedValue(new Error("thumbnail unavailable in test"));
        replacePresentationMock.mockResolvedValue({
            presentation_id: "ppt-1",
            title: "标准销售演示",
            status: "processing",
            version_number: 3,
            file_size_bytes: 3 * 1024 * 1024,
            page_count: 1,
            total_pages: 1,
            created_at: "2026-03-23T00:00:00Z",
            pages: [
                {
                    page_id: "page-new-1",
                    page_number: 1,
                    image_url: "/thumb-new-1.png",
                    extracted_text: "新版第一页内容",
                },
            ],
        });
    });

    it("shows version and material status plus a replace CTA", async () => {
        render(<PresentationDetailPage />);

        await screen.findByText("标准销售演示");

        expect(screen.getByText("版本 v2")).toBeTruthy();
        expect(screen.getByText("当前材料状态")).toBeTruthy();
        expect(screen.getByText("可用")).toBeTruthy();
        expect(screen.getByRole("button", { name: /替换标准PPT/i })).toBeTruthy();
    });

    it("replaces the current presentation in place and updates the version badge", async () => {
        const { container } = render(<PresentationDetailPage />);

        await screen.findByText("标准销售演示");

        const fileInput = container.querySelector('input[type="file"]') as HTMLInputElement | null;
        expect(fileInput).toBeTruthy();

        const file = new File(["fake-ppt"], "标准销售演示-v3.pptx", {
            type: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        });
        fireEvent.change(fileInput as HTMLInputElement, {
            target: { files: [file] },
        });

        fireEvent.click(screen.getByRole("button", { name: /替换标准PPT/i }));

        await waitFor(() => {
            expect(replacePresentationMock).toHaveBeenCalledTimes(1);
        });
        expect(replacePresentationMock).toHaveBeenCalledWith("ppt-1", {
            file,
            title: "标准销售演示",
        });

        expect(await screen.findByText("版本 v3")).toBeTruthy();
        expect(screen.getByText("处理中")).toBeTruthy();
        expect(successToastMock).toHaveBeenCalled();
    });

    it("renders a blocker message when replacement is rejected by an active session", async () => {
        const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
        replacePresentationMock.mockRejectedValue(
            new actual.ApiRequestError({
                status: 409,
                errorCode: "[PRESENTATION_REPLACE_BLOCKED_ACTIVE_SESSION]",
                message: "当前有进行中的演练正在使用该标准PPT，请结束后再替换。",
            }),
        );

        const { container } = render(<PresentationDetailPage />);
        await screen.findByText("标准销售演示");

        const fileInput = container.querySelector('input[type="file"]') as HTMLInputElement | null;
        const file = new File(["fake-ppt"], "blocked-replace.pptx", {
            type: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        });
        fireEvent.change(fileInput as HTMLInputElement, {
            target: { files: [file] },
        });

        fireEvent.click(screen.getByRole("button", { name: /替换标准PPT/i }));

        expect(
            await screen.findByText("当前有进行中的演练正在使用该标准PPT，请结束后再替换。"),
        ).toBeTruthy();
        expect(errorToastMock).toHaveBeenCalled();
    });
});
