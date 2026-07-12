import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import Page from "./page";

vi.mock("@/lib/api/client", () => ({ api: { newcomerTraining: { getJourney: vi.fn().mockResolvedValue({ enrollment_id: "e", path_revision_id: "r", path_title: "新人训练", phases: [], progress: { completed: false, completed_count: 0, total_required: 0, percent: 0 }, primary_next_action: null }) } } }));

describe("newcomer training page", () => {
    it("loads the canonical learner journey", async () => {
        render(<Page />);
        expect(screen.getByText("正在准备你的训练路径…")).toBeTruthy();
        expect(await screen.findByText("新人训练")).toBeTruthy();
    });
});
