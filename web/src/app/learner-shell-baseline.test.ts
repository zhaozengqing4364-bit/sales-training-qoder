import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

const APP_ROOT = path.resolve(__dirname);
const WEB_SRC_ROOT = path.resolve(APP_ROOT, "..");
const LEARNER_CORE_ROUTE_SHELLS = [
    "(auth)/error.tsx",
    "(auth)/loading.tsx",
    "(dashboard)/error.tsx",
    "(dashboard)/history/loading.tsx",
    "(dashboard)/loading.tsx",
    "(user)/practice/[sessionId]/error.tsx",
    "(user)/practice/[sessionId]/loading.tsx",
    "(user)/practice/[sessionId]/replay/error.tsx",
    "(user)/practice/[sessionId]/replay/loading.tsx",
    "(user)/practice/[sessionId]/report/error.tsx",
    "(user)/practice/[sessionId]/report/loading.tsx",
] as const;
const SHARED_LOADING_SHELLS = [
    "app/(auth)/loading.tsx",
    "app/(dashboard)/loading.tsx",
    "app/(user)/practice/[sessionId]/loading.tsx",
] as const;
const EXPLICIT_STATUS_LOADING_SHELLS = [
    "app/(dashboard)/history/loading.tsx",
    "app/(user)/practice/[sessionId]/report/loading.tsx",
    "app/(user)/practice/[sessionId]/replay/loading.tsx",
] as const;
const SHARED_ERROR_SHELLS = [
    "app/(auth)/error.tsx",
    "app/(user)/practice/[sessionId]/error.tsx",
] as const;
const BROWSER_LOCAL_TIME_SURFACES = [
    "app/(dashboard)/history/page.tsx",
    "app/(user)/practice/[sessionId]/report/page.tsx",
    "app/(user)/practice/[sessionId]/replay/page.tsx",
] as const;

function collectRouteShells(dir: string): string[] {
    const entries = readdirSync(dir, { withFileTypes: true });
    const files: string[] = [];

    for (const entry of entries) {
        const fullPath = path.join(dir, entry.name);

        if (entry.isDirectory()) {
            files.push(...collectRouteShells(fullPath));
            continue;
        }

        if (!entry.isFile()) {
            continue;
        }

        if (entry.name !== "error.tsx" && entry.name !== "loading.tsx") {
            continue;
        }

        files.push(path.relative(APP_ROOT, fullPath));
    }

    return files.sort();
}

function readWebSrcSource(relativePath: string): string {
    return readFileSync(path.join(WEB_SRC_ROOT, relativePath), "utf8");
}

function isLearnerCoreRouteShell(relativePath: string): boolean {
    return relativePath.startsWith("(auth)/")
        || relativePath.startsWith("(dashboard)/")
        || relativePath.startsWith("(user)/practice/");
}

describe("learner shell baseline", () => {
    it("keeps the learner-core route shell inventory closed without pulling admin-only shells into learner scope", () => {
        const allShells = collectRouteShells(APP_ROOT);
        const learnerCoreShells = allShells.filter(isLearnerCoreRouteShell);

        expect(allShells).toContain("admin/error.tsx");
        expect(allShells).toContain("admin/loading.tsx");
        expect(learnerCoreShells).toEqual([...LEARNER_CORE_ROUTE_SHELLS]);
    });

    it("keeps the learner shell a11y baseline on shared loading and error seams", () => {
        for (const relativePath of SHARED_LOADING_SHELLS) {
            const source = readWebSrcSource(relativePath);
            expect(source).toContain("LearnerRouteLoadingState");
            expect(source).toContain('label="');
        }

        for (const relativePath of EXPLICIT_STATUS_LOADING_SHELLS) {
            const source = readWebSrcSource(relativePath);
            expect(source).toContain('role="status"');
            expect(source).toContain('aria-live="polite"');
            expect(source).toContain('aria-busy="true"');
            expect(source).toContain('className="sr-only"');
        }

        for (const relativePath of SHARED_ERROR_SHELLS) {
            expect(readWebSrcSource(relativePath)).toContain("LearnerRouteErrorState");
        }

        expect(readWebSrcSource("app/(dashboard)/error.tsx")).toContain('debug.durableError("route-error.dashboard"');
    });

    it("keeps responsive density and browser-local timezone handling as explicit deferred baseline facts", () => {
        const dashboardSkeletonSource = readWebSrcSource("components/dashboard-skeleton.tsx");
        const dashboardHomeSource = readWebSrcSource("app/(dashboard)/page.tsx");
        const profileSource = readWebSrcSource("app/(dashboard)/profile/page.tsx");

        // The shared dashboard shell baseline is already made narrow-screen-safe.
        expect(dashboardSkeletonSource).toContain("flex flex-col gap-4 px-2 md:flex-row");
        expect(dashboardSkeletonSource).toContain("grid min-h-[320px] grid-cols-1 gap-6 md:grid-cols-12");

        // Remaining page-density work is still intentionally deferred outside learner-shell closure.
        expect(dashboardHomeSource).toContain("header className=\"flex items-end justify-between px-2\"");
        expect(dashboardHomeSource).toContain("className=\"grid grid-cols-3 gap-4 py-6\"");
        expect(dashboardHomeSource).toContain("className=\"grid grid-cols-2 gap-3\"");
        expect(profileSource).toContain("className=\"grid grid-cols-1 md:grid-cols-4 gap-4\"");

        // History/report/replay still use browser-local zh-CN formatting until product picks a timezone contract.
        for (const relativePath of BROWSER_LOCAL_TIME_SURFACES) {
            const source = readWebSrcSource(relativePath);
            expect(source).toContain('toLocaleString("zh-CN"');
            expect(source).toContain("new Date(value)");
        }
    });
});
