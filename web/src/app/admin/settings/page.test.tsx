import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SettingsPage from "./page";

const {
    getModelConfigsMock,
    getAdminSettingsSurfaceMock,
    previewAdminSettingsMock,
    saveAdminSettingsDraftMock,
    publishAdminSettingsMock,
    rollbackAdminSettingsMock,
} = vi.hoisted(() => ({
    getModelConfigsMock: vi.fn(),
    getAdminSettingsSurfaceMock: vi.fn(),
    previewAdminSettingsMock: vi.fn(),
    saveAdminSettingsDraftMock: vi.fn(),
    publishAdminSettingsMock: vi.fn(),
    rollbackAdminSettingsMock: vi.fn(),
}));

vi.mock("@/components/ui/toast", () => ({
    useToast: () => ({ success: vi.fn(), error: vi.fn() }),
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            admin: {
                ...actual.api.admin,
                getModelConfigs: getModelConfigsMock,
                getAdminSettingsSurface: getAdminSettingsSurfaceMock,
                previewAdminSettings: previewAdminSettingsMock,
                saveAdminSettingsDraft: saveAdminSettingsDraftMock,
                publishAdminSettings: publishAdminSettingsMock,
                rollbackAdminSettings: rollbackAdminSettingsMock,
            },
        },
    };
});

describe("SettingsPage", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        getModelConfigsMock.mockResolvedValue({ llm: [], embedding: [], asr: [], tts: [] });
        getAdminSettingsSurfaceMock.mockImplementation(async (surface: string) => ({
            surface,
            key: `admin.settings.${surface}`,
            definition: {
                domain: "admin_settings",
                schema_version: "business_rule_config_v1",
                default_value: {},
                type: "settings_json",
                range_or_allowlist: {},
                read_path: `admin.api.settings:${surface}`,
                admin_entry: `/admin/settings?tab=${surface}`,
                permission: "admin_settings_manage",
                audit_policy: "audit",
                fallback_policy: "fallback",
                rollback_policy: "rollback",
            },
            active: {
                value: {
                    version: `admin_${surface}_settings_v1`,
                    enabled: true,
                    platform_name: "Intelligent Coach AI",
                    support_email: "support@company.com",
                    welcome_message: "欢迎使用高级训练平台，开启您的学习之旅！",
                    default_language: "zh-CN",
                    timezone: "Asia/Shanghai",
                    date_format: "YYYY-MM-DD",
                    enforce_admin_2fa: true,
                    new_device_login_alert: true,
                    password_min_length: 8,
                    password_expiry_days: 90,
                    email_notifications: {
                        user_registration_admin: true,
                        system_exception_alert: true,
                        weekly_report: false,
                        knowledge_base_update: false,
                    },
                },
                source: "default",
                config_id: null,
                version: null,
                status: null,
                fallback_reason: "active_missing",
            },
            drafts: [{ id: "draft-1", key: `admin.settings.${surface}`, status: "draft", version: 2, value: {}, default_value: {}, enabled: true, validation_errors: [] }],
            history: [{ id: "history-1", key: `admin.settings.${surface}`, status: "archived", version: 1, value: {}, default_value: {}, enabled: true, validation_errors: [], updated_at: "2026-05-01T10:00:00Z" }],
            audit_logs: [{ id: "audit-1", action: "publish", reason: "baseline", trace_id: "trace-1", created_at: "2026-05-01T10:00:00Z" }],
            permissions: { can_view: true, can_mutate: true, can_publish: true, permission: "admin_settings.manage" },
        }));
        previewAdminSettingsMock.mockResolvedValue({ valid: true, summary: { platform_name: "Coach QA" } });
        saveAdminSettingsDraftMock.mockResolvedValue({ id: "draft-1" });
        publishAdminSettingsMock.mockResolvedValue({ id: "draft-1" });
        rollbackAdminSettingsMock.mockResolvedValue({ id: "history-1" });
    });

    it("loads governed general settings and supports preview save publish and audit display", async () => {
        render(<SettingsPage />);

        expect(await screen.findByText(/已接入后端配置 API/)).toBeTruthy();
        expect(screen.getByDisplayValue("Intelligent Coach AI")).toBeTruthy();
        expect(screen.getByText("配置审计")).toBeTruthy();
        expect(screen.getByText(/baseline/)).toBeTruthy();

        fireEvent.change(screen.getByPlaceholderText("变更原因（必填）"), {
            target: { value: "update general settings" },
        });
        fireEvent.change(screen.getByDisplayValue("Intelligent Coach AI"), {
            target: { value: "Coach QA" },
        });
        fireEvent.click(screen.getByRole("button", { name: /预览/ }));
        expect(await screen.findByText(/预览完成/)).toBeTruthy();
        expect(previewAdminSettingsMock).toHaveBeenCalledWith("general", expect.objectContaining({ platform_name: "Coach QA" }), "update general settings");

        fireEvent.click(screen.getByRole("button", { name: /保存草稿/ }));
        await waitFor(() => {
            expect(saveAdminSettingsDraftMock).toHaveBeenCalledWith("general", expect.objectContaining({ platform_name: "Coach QA" }), "update general settings");
        });

        fireEvent.click(screen.getByRole("button", { name: /发布配置/ }));
        await waitFor(() => {
            expect(publishAdminSettingsMock).toHaveBeenCalledWith("general", "draft-1", "update general settings");
        });
    });

    it("keeps the model tab as the only active persisted settings surface", async () => {
        render(<SettingsPage />);

        fireEvent.click(screen.getByText("模型配置"));

        expect((await screen.findByRole("button", { name: /刷新/ }) as HTMLButtonElement).disabled).toBe(false);
        expect(getModelConfigsMock).toHaveBeenCalledTimes(1);
    });

    it("links governed settings to the dedicated governance matrix", () => {
        render(<SettingsPage />);

        fireEvent.click(screen.getByText("治理矩阵"));

        expect(screen.getByText(/常规、安全和通知设置已接入配置 API/)).toBeTruthy();
        expect(screen.getByRole("link", { name: "打开治理矩阵" }).getAttribute("href")).toBe("/admin/governance");
    });
});
