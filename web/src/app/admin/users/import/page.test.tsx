import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import UserProvisioningPage from "./page";

vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: vi.fn() }), useSearchParams: () => new URLSearchParams() }));
vi.mock("@/lib/api/client", () => ({ api: { admin: {} }, getApiErrorMessage: (error: unknown) => String(error) }));

describe("UserProvisioningPage", () => {
    it("在独立流程解释模板、预览和团队事务边界", () => {
        render(<UserProvisioningPage />);
        expect(screen.getByRole("heading", { name: "批量开户" })).toBeTruthy();
        expect(screen.getByText(/单个团队全成全败/)).toBeTruthy();
        expect(screen.getByLabelText("CSV 文件")).toBeTruthy();
        expect(screen.getByRole("button", { name: "预览并校验" }).hasAttribute("disabled")).toBe(true);
    });
});
