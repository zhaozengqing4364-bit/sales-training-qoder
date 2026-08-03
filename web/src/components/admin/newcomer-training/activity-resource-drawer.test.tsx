import { fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ActivityResourceDrawer } from "./activity-resource-drawer";

const listBindingResources = vi.hoisted(() => vi.fn());
const listResourcesV2 = vi.hoisted(() => vi.fn());
const listSourceAnchorsV2 = vi.hoisted(() => vi.fn());
const createResourceV2 = vi.hoisted(() => vi.fn());

vi.mock("@/components/ui/glass-sheet", () => ({
    GlassSheet: ({ children, isOpen }: { children: ReactNode; isOpen: boolean }) => isOpen ? <div>{children}</div> : null,
}));
vi.mock("@/lib/api/client", () => ({
    api: {
        admin: {
            newcomerTraining: {
                listBindingResources,
                listResourcesV2,
                listSourceAnchorsV2,
                createResourceV2,
                createSourceAnchorV2: vi.fn(),
            },
        },
    },
    getApiErrorMessage: (error: unknown) => error instanceof Error ? error.message : "操作失败",
}));

function renderDrawer(onBind = vi.fn()) {
    const client = new QueryClient({
        defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    render(
        <QueryClientProvider client={client}>
            <ActivityResourceDrawer
                open
                activityType="lesson"
                field="learning_unit_revision_id"
                currentRevisionId=""
                onClose={vi.fn()}
                onBind={onBind}
            />
        </QueryClientProvider>,
    );
    return onBind;
}

describe("ActivityResourceDrawer", () => {
    beforeEach(() => {
        listBindingResources.mockReset();
        listResourcesV2.mockReset();
        listSourceAnchorsV2.mockReset();
        createResourceV2.mockReset();
        listResourcesV2.mockResolvedValue({ items: [] });
        listSourceAnchorsV2.mockResolvedValue({ items: [] });
    });

    it("binds an exact working revision without leaving the path editor", async () => {
        const onBind = vi.fn();
        listBindingResources.mockResolvedValue({
            items: [{
                resource_type: "learning_unit",
                revision_id: "unit-working-1",
                stable_key: "product-value",
                title: "产品价值学习单元",
                status: "working",
                revision_no: 2,
                created_at: "2026-07-17T08:00:00Z",
                bindable: true,
                needs_approval: true,
                quick_create_supported: true,
            }],
        });
        renderDrawer(onBind);

        fireEvent.click(await screen.findByRole("button", { name: /产品价值学习单元/ }));

        expect(onBind).toHaveBeenCalledWith(
            "unit-working-1",
            "产品价值学习单元 · 第 2 版",
        );
    });

    it("keeps quick-create input and context when creating a unit fails", async () => {
        listBindingResources.mockResolvedValue({ items: [] });
        listResourcesV2.mockResolvedValue({ items: [] });
        createResourceV2.mockRejectedValue(new Error("原始材料暂时无法保存，请稍后重试。"));
        const onBind = renderDrawer();

        fireEvent.click(await screen.findByRole("button", { name: "快速新建学习单元" }));
        fireEvent.change(screen.getByLabelText("学习单元名称"), {
            target: { value: "产品价值学习" },
        });
        fireEvent.change(screen.getByLabelText("业务编码"), {
            target: { value: "product-value" },
        });
        fireEvent.change(screen.getByLabelText("学习目标"), {
            target: { value: "能够说明产品核心价值" },
        });
        fireEvent.change(screen.getByLabelText("核心内容"), {
            target: { value: "围绕客户问题表达产品价值。" },
        });
        fireEvent.change(screen.getByLabelText("必修检查点"), {
            target: { value: "复述核心价值" },
        });
        fireEvent.change(await screen.findByLabelText("来源名称"), {
            target: { value: "新人销售基础手册" },
        });
        fireEvent.change(screen.getByLabelText("来源地址"), {
            target: { value: "https://example.com/foundation-handbook" },
        });
        fireEvent.click(screen.getByRole("button", { name: "创建并选择来源" }));

        expect((await screen.findByRole("alert")).textContent).toContain("原始材料暂时无法保存");
        expect((screen.getByLabelText("学习单元名称") as HTMLInputElement).value)
            .toBe("产品价值学习");
        expect((screen.getByLabelText("来源名称") as HTMLInputElement).value)
            .toBe("新人销售基础手册");
        expect((screen.getByLabelText("来源地址") as HTMLInputElement).value)
            .toBe("https://example.com/foundation-handbook");
        expect(onBind).not.toHaveBeenCalled();
    });
});
