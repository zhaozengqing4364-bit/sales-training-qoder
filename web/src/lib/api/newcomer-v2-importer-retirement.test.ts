import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const SOURCE_ROOT = path.resolve(
    path.dirname(fileURLToPath(import.meta.url)),
    "../..",
);

const RETIRED_ENDPOINT_FRAGMENTS = [
    "/admin/newcomer-training/readiness/workbench",
    "/admin/newcomer-training/readiness/dossiers/",
    "/admin/newcomer-training/resources/{resource_type}/{resource_id}/commands/publish",
    "/admin/sales-trainer/audio-submissions",
    "/admin/sales-trainer/score-results",
    "/admin/sales-trainer/training-records",
    "/admin/sales-trainer/quiz-attempts",
    "/admin/sales-trainer/regrades/quiz-attempts",
] as const;

const RETIRED_ENDPOINT_PATTERNS = [
    /\/admin\/newcomer-training\/path(?:\/|["'`])/,
] as const;

function productionSources(directory: string): string[] {
    return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
        const candidate = path.join(directory, entry.name);
        if (entry.isDirectory()) {
            return productionSources(candidate);
        }
        if (!/\.(ts|tsx)$/.test(entry.name) || /\.(test|spec)\./.test(entry.name)) {
            return [];
        }
        return [candidate];
    });
}

describe("newcomer v2 importer retirement", () => {
    it("keeps production frontend sources off every retired endpoint", () => {
        const violations = productionSources(SOURCE_ROOT).flatMap((filename) => {
            const source = fs.readFileSync(filename, "utf8");
            const fragmentViolations = RETIRED_ENDPOINT_FRAGMENTS.filter((fragment) =>
                source.includes(fragment),
            ).map((fragment) => ({
                file: path.relative(SOURCE_ROOT, filename),
                fragment,
            }));
            const patternViolations = RETIRED_ENDPOINT_PATTERNS.filter((pattern) =>
                pattern.test(source),
            ).map((pattern) => ({
                file: path.relative(SOURCE_ROOT, filename),
                fragment: pattern.source,
            }));
            return [...fragmentViolations, ...patternViolations];
        });

        expect(violations).toEqual([]);
    });
});
