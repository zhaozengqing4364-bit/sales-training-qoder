import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

const globalsCss = readFileSync(path.join(process.cwd(), "src/app/globals.css"), "utf8");

describe("global motion contract", () => {
    it("defines the shared easing and duration tokens", () => {
        expect(globalsCss).toContain("--ease-out: cubic-bezier(0.23, 1, 0.32, 1);");
        expect(globalsCss).toContain("--ease-in-out: cubic-bezier(0.77, 0, 0.175, 1);");
        expect(globalsCss).toContain("--ease-drawer: cubic-bezier(0.32, 0.72, 0, 1);");
        expect(globalsCss).toContain("--duration-press: 140ms;");
        expect(globalsCss).toContain("--duration-tooltip: 160ms;");
        expect(globalsCss).toContain("--duration-popover: 200ms;");
        expect(globalsCss).toContain("--duration-modal: 240ms;");
        expect(globalsCss).toContain("--duration-drawer: 320ms;");
    });

    it("preserves a component baseline transform when motion is reduced", () => {
        expect(globalsCss).toContain("@media (prefers-reduced-motion: reduce)");
        expect(globalsCss).toContain("[data-motion-kind=\"spatial\"]");
        expect(globalsCss).toContain("transform: var(--motion-reduced-transform, none) !important;");
        expect(globalsCss).toContain("[data-motion-kind=\"continuous\"]");
        expect(globalsCss).toContain("animation: none !important;");
    });

    it("defines mounted and unmounted feedback motion without plugin utilities", () => {
        expect(globalsCss).toContain(".motion-dialog-overlay");
        expect(globalsCss).toContain(".motion-dialog-content");
        expect(globalsCss).toContain(".motion-tooltip");
        expect(globalsCss).toContain(".motion-toast");
        expect(globalsCss).toContain("--motion-reduced-transform: translate(-50%, -50%);");
        expect(globalsCss).toContain("transform-origin: var(--radix-tooltip-content-transform-origin);");
    });

    it("defines a one-shot result reveal", () => {
        expect(globalsCss).toContain(".motion-result-reveal");
        expect(globalsCss).toContain("@starting-style");
        expect(globalsCss).toContain("transform: scale(0.97);");
    });

    it("defines a one-shot completion reveal", () => {
        expect(globalsCss).toContain(".motion-completion-reveal");
        expect(globalsCss).toContain("opacity var(--duration-modal) var(--ease-out)");
    });
});
