import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ActivityResourceLibrary } from "./activity-resource-library";

describe("ActivityResourceLibrary", () => {
    it("shows only the governed learning and quiz scope for this launch", () => {
        render(<ActivityResourceLibrary />);

        for (const label of ["学习资料与学习单元", "题目与测验"]) {
            expect(screen.getByRole("heading", { name: label })).toBeTruthy();
        }
        expect(screen.queryByRole("heading", { name: "实时对练" })).toBeNull();
        expect(screen.queryByRole("heading", { name: "AI 教练" })).toBeNull();
        expect(screen.queryByRole("link", { name: /管理学习内容|管理题库|管理作业任务/ })).toBeNull();
        expect(screen.getByText(/发布新版本不会改变在训学员已经分配的训练版本/)).toBeTruthy();
        expect(screen.getByRole("link", { name: "查看学员训练进度" }).getAttribute("href"))
            .toBe("/admin/newcomer-training/learners");
    });
});
