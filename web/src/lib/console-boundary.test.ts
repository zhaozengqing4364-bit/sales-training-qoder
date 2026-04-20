import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

const WEB_SRC_ROOT = path.resolve(__dirname, "..");
const RAW_CONSOLE_PATTERN = /console\.(log|error|warn|info)\s*\(/;
const ALLOWED_RAW_CONSOLE_FILES = new Set([
    path.resolve(WEB_SRC_ROOT, "instrumentation.ts"),
    path.resolve(WEB_SRC_ROOT, "instrumentation-client.ts"),
    path.resolve(WEB_SRC_ROOT, "lib/debug.ts"),
]);
const SCANNED_DIRECTORIES = ["app", "components", "hooks", "lib"] as const;

function collectSourceFiles(dir: string): string[] {
    const entries = readdirSync(dir, { withFileTypes: true });
    const files: string[] = [];

    for (const entry of entries) {
        const fullPath = path.join(dir, entry.name);

        if (entry.isDirectory()) {
            files.push(...collectSourceFiles(fullPath));
            continue;
        }

        if (!entry.isFile()) {
            continue;
        }

        if (!fullPath.endsWith(".ts") && !fullPath.endsWith(".tsx")) {
            continue;
        }

        if (fullPath.endsWith(".test.ts") || fullPath.endsWith(".test.tsx")) {
            continue;
        }

        files.push(fullPath);
    }

    return files;
}

function scanForRawConsole(): string[] {
    return SCANNED_DIRECTORIES
        .flatMap((directory) => collectSourceFiles(path.join(WEB_SRC_ROOT, directory)))
        .filter((filePath) => !ALLOWED_RAW_CONSOLE_FILES.has(filePath))
        .filter((filePath) => {
            const file = readFileSync(filePath, "utf8");
            return RAW_CONSOLE_PATTERN.test(file);
        })
        .map((filePath) => path.relative(WEB_SRC_ROOT, filePath))
        .sort();
}

describe("frontend raw-console boundary", () => {
    it("keeps raw console scoped to the explicit observability exceptions", () => {
        for (const filePath of ALLOWED_RAW_CONSOLE_FILES) {
            expect(statSync(filePath).isFile()).toBe(true);
        }

        expect(scanForRawConsole()).toEqual([]);
    });
});
