import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogTitle,
} from "./glass-modal";
import {
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,
} from "./glass-tooltip";
import { ToastProvider, useToast } from "./toast";

function ToastTrigger() {
    const toast = useToast();
    return <button type="button" onClick={() => toast.success("保存成功")}>显示通知</button>;
}

describe("shared feedback motion", () => {
    it("keeps the root toast provider free of a page-wide motion dependency", () => {
        const source = readFileSync(path.join(process.cwd(), "src/components/ui/toast.tsx"), "utf8");
        expect(source).not.toContain('from "framer-motion"');
        expect(source).toContain('data-state={toast.exiting ? "closed" : "open"}');
    });

    it("uses real dialog motion classes while preserving dialog semantics", () => {
        render(
            <Dialog open>
                <DialogContent>
                    <DialogTitle>确认发布</DialogTitle>
                    <DialogDescription>发布后对新学员生效</DialogDescription>
                </DialogContent>
            </Dialog>,
        );

        const dialog = screen.getByRole("dialog", { name: "确认发布" });
        expect(dialog.classList.contains("motion-dialog-content")).toBe(true);
        expect(dialog.getAttribute("data-motion-kind")).toBe("spatial");
        expect(document.querySelector(".motion-dialog-overlay")).not.toBeNull();
    });

    it("uses transform-origin-aware tooltip motion", () => {
        render(
            <TooltipProvider delayDuration={0}>
                <Tooltip open>
                    <TooltipTrigger>路径说明</TooltipTrigger>
                    <TooltipContent>按阶段配置训练内容</TooltipContent>
                </Tooltip>
            </TooltipProvider>,
        );

        expect(screen.getByRole("tooltip")).not.toBeNull();
        const tooltipContent = document.querySelector<HTMLElement>(".motion-tooltip");
        expect(tooltipContent).not.toBeNull();
        expect(tooltipContent?.getAttribute("data-motion-kind")).toBe("spatial");
    });

    it("renders an accessible animated toast that can be dismissed", async () => {
        render(<ToastProvider><ToastTrigger /></ToastProvider>);

        fireEvent.click(screen.getByRole("button", { name: "显示通知" }));

        const status = screen.getByRole("status");
        expect(status.textContent).toContain("保存成功");
        expect(status.getAttribute("data-motion-kind")).toBe("spatial");
        fireEvent.click(screen.getByRole("button", { name: "关闭通知" }));
        expect(screen.queryByText("保存成功")).not.toBeNull();
        await waitFor(() => expect(screen.queryByText("保存成功")).toBeNull());
    });
});
