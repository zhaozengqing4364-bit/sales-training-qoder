export type AdminAssetRegistration = {
    assetType: string;
    label: string;
    adminPath: string;
};

const ADMIN_ASSET_REGISTRATIONS: Record<string, AdminAssetRegistration> = {
    persona: {
        assetType: "persona",
        label: "角色",
        adminPath: "/admin/personas",
    },
    presentation: {
        assetType: "presentation",
        label: "PPT",
        adminPath: "/admin/presentations",
    },
    runtime_profile: {
        assetType: "runtime_profile",
        label: "运行时配置",
        adminPath: "/admin/voice-runtime",
    },
    knowledge_base: {
        assetType: "knowledge_base",
        label: "知识库",
        adminPath: "/admin/knowledge",
    },
};

export function getAdminAssetRegistration(assetType?: string | null): AdminAssetRegistration | null {
    if (!assetType) {
        return null;
    }
    return ADMIN_ASSET_REGISTRATIONS[assetType] || null;
}

export function resolveAdminAssetTypeLabel(assetType?: string | null, fallback = "资产"): string {
    return getAdminAssetRegistration(assetType)?.label || fallback;
}

export function resolveAdminAssetTypeLink(assetType?: string | null, fallback = "/admin"): string {
    return getAdminAssetRegistration(assetType)?.adminPath || fallback;
}

export function resolveAdminAssetLabel(
    asset: Pick<{ asset_type?: string | null; asset_label?: string | null }, "asset_type" | "asset_label">,
    fallback = "资产",
): string {
    return asset.asset_label || resolveAdminAssetTypeLabel(asset.asset_type, fallback);
}

export function resolveAdminAssetLink(
    asset: Pick<{ asset_type?: string | null; admin_path?: string | null }, "asset_type" | "admin_path">,
    fallback = "/admin",
): string {
    return asset.admin_path || resolveAdminAssetTypeLink(asset.asset_type, fallback);
}
