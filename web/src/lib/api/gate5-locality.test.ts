import fs from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

const API_ROOT = path.resolve(process.cwd(), "src/lib/api");
const read = (relativePath: string) => fs.readFileSync(path.join(API_ROOT, relativePath), "utf8");

describe("Gate 5 frontend domain locality", () => {
    it("moves journey, readiness, and report definitions out of the global type barrel", () => {
        const globalTypes = read("types.ts");

        expect(globalTypes).not.toMatch(/export interface TrainingJourneyResponse/);
        expect(globalTypes).not.toMatch(/export interface ReadinessDossier/);
        expect(globalTypes).not.toMatch(/export interface PracticeSessionReport/);
        expect(globalTypes).toContain('from "./types/training-journey"');
        expect(globalTypes).toContain('from "./types/session-report"');
    });

    it("moves session transport rules out of the global domain aggregation file", () => {
        const clientDomains = read("client-domains.ts");
        const sessionsDomain = read("domains/sessions.ts");

        expect(clientDomains).not.toContain("export function createSessionsDomain");
        expect(clientDomains).not.toContain("getReport: async");
        expect(clientDomains).not.toContain("/practice/sessions/${sessionId}/report");
        expect(clientDomains).toContain('from "./domains/sessions"');
        expect(sessionsDomain).toContain("export function createSessionsDomain");
    });

    it("keeps UI callers on the outward client facade", () => {
        const reportPage = fs.readFileSync(
            path.resolve(process.cwd(), "src/app/(user)/practice/[sessionId]/report/page.tsx"),
            "utf8",
        );
        const readinessPage = fs.readFileSync(
            path.resolve(process.cwd(), "src/app/admin/sales-trainer/readiness/[learnerId]/page.tsx"),
            "utf8",
        );

        for (const source of [reportPage, readinessPage]) {
            expect(source).toContain('from "@/lib/api/client"');
            expect(source).not.toContain("@/lib/api/domains/");
            expect(source).not.toContain("@/lib/api/client-domains");
        }
    });
});
