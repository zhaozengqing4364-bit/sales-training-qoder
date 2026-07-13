import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Button } from "./button";

describe("Button motion", () => {
    it("limits transitions and provides a reduced-motion press state", () => {
        render(<Button>保存草稿</Button>);

        const button = screen.getByRole("button", { name: "保存草稿" });
        expect(button.className).not.toContain("transition-all");
        expect(button.className).toContain("transition-[color,background-color,border-color,box-shadow,transform]");
        expect(button.className).toContain("duration-[var(--duration-press)]");
        expect(button.className).toContain("ease-[var(--ease-out)]");
        expect(button.className).toContain("active:scale-[0.97]");
        expect(button.className).toContain("motion-reduce:active:scale-100");
    });
});
