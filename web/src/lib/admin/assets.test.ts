import { describe, expect, it } from "vitest";

import {
    getAdminAssetRegistration,
    resolveAdminAssetLink,
    resolveAdminAssetLabel,
} from "./assets";

describe("admin asset metadata registry", () => {
    it("matches the current backend registry labels and admin paths", () => {
        expect(getAdminAssetRegistration("knowledge_base")).toEqual({
            assetType: "knowledge_base",
            label: "知识库",
            adminPath: "/admin/knowledge",
        });
        expect(getAdminAssetRegistration("persona")).toEqual({
            assetType: "persona",
            label: "角色",
            adminPath: "/admin/personas",
        });
        expect(getAdminAssetRegistration("presentation")).toEqual({
            assetType: "presentation",
            label: "PPT",
            adminPath: "/admin/presentations",
        });
        expect(getAdminAssetRegistration("runtime_profile")).toEqual({
            assetType: "runtime_profile",
            label: "运行时配置",
            adminPath: "/admin/voice-runtime",
        });
    });

    it("falls back to the shared registry when linked-asset payloads omit label or admin path", () => {
        expect(resolveAdminAssetLabel({ asset_type: "presentation", asset_label: "" })).toBe("PPT");
        expect(resolveAdminAssetLink({ asset_type: "runtime_profile", admin_path: "" })).toBe("/admin/voice-runtime");
    });

    it("preserves explicit backend label and admin path overrides when present", () => {
        expect(resolveAdminAssetLabel({ asset_type: "knowledge_base", asset_label: "知识库别名" })).toBe("知识库别名");
        expect(resolveAdminAssetLink({ asset_type: "persona", admin_path: "/admin/personas/custom" })).toBe("/admin/personas/custom");
    });
});
