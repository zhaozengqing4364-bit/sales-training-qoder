import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const ROOT = join(process.cwd(), "src");
const forbidden = [
    "ppt_explanation",
    "company_product_demo",
    "business_skills",
    "elevator_pitch",
    "customer_faq_oral_drill",
    "@/lib/sales-trainer/config-center",
    "@/lib/sales-trainer/module-path",
    '"/admin/sales-trainer/paths"',
];

function runtimeFiles(directory: string): string[] {
    return readdirSync(directory).flatMap((name) => {
        const path = join(directory, name);
        if (statSync(path).isDirectory()) return runtimeFiles(path);
        return /\.(ts|tsx)$/.test(name) && !/\.test\.(ts|tsx)$/.test(name) ? [path] : [];
    });
}

describe("newcomer runtime authority boundary", () => {
    it("contains no fixed newcomer module keys or compatibility imports", () => {
        const violations = runtimeFiles(ROOT).flatMap((path) => {
            const source = readFileSync(path, "utf8");
            return forbidden
                .filter((key) => source.includes(key))
                .map((key) => `${path.replace(ROOT, "src")}: ${key}`);
        });
        expect(violations).toEqual([]);
    });
});
