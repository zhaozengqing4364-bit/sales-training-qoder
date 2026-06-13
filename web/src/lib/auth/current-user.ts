export type CurrentUserRole = "admin" | "user" | "support" | (string & {});

const PLATFORM_ADMIN_ROLES = new Set(["admin", "super_admin"]);
const SALES_TRAINER_ADMIN_CONSOLE_ROLES = new Set([
    "admin",
    "super_admin",
    "support",
    "content_admin",
    "newcomer_content_admin",
    "training_lead",
    "training_manager",
    "ops",
    "operator",
    "operations",
    "sre",
]);
const SALES_TRAINER_MANAGER_ENTRY_ROLES = new Set([
    "support",
    "content_admin",
    "newcomer_content_admin",
    "training_lead",
    "training_manager",
    "ops",
    "operator",
    "operations",
    "sre",
]);

type CurrentUserRecord = {
    id?: unknown;
    user_id?: unknown;
    name?: unknown;
    display_name?: unknown;
    email?: unknown;
    role?: unknown;
    department?: unknown;
    is_active?: unknown;
    created_at?: unknown;
    avatar_url?: unknown;
};

export interface CurrentUser {
    user_id: string;
    id: string;
    name: string;
    display_name: string;
    email: string;
    role: CurrentUserRole;
    department?: string;
    is_active: boolean;
    created_at: string;
    avatar_url?: string;
}

function toRecord(value: unknown): CurrentUserRecord {
    return value && typeof value === "object" ? value as CurrentUserRecord : {};
}

function toStringValue(value: unknown, fallback = ""): string {
    return typeof value === "string" ? value : fallback;
}

function normalizeRole(value: unknown): CurrentUserRole {
    if (typeof value === "string" && value.trim()) {
        return value.trim().toLowerCase();
    }
    return "user";
}

export function normalizeCurrentUser(input: unknown): CurrentUser {
    const raw = toRecord(input);
    const id = toStringValue(raw.id, toStringValue(raw.user_id));
    const displayName = toStringValue(raw.display_name, toStringValue(raw.name, "用户")) || "用户";
    const email = toStringValue(raw.email);
    const department = toStringValue(raw.department);
    const avatarUrl = toStringValue(raw.avatar_url);

    return {
        user_id: id,
        id,
        name: displayName,
        display_name: displayName,
        email,
        role: normalizeRole(raw.role),
        department: department || undefined,
        is_active: raw.is_active === false ? false : true,
        created_at: toStringValue(raw.created_at),
        avatar_url: avatarUrl || undefined,
    };
}

export function hasRequiredRole(
    user: Pick<CurrentUser, "role"> | null | undefined,
    requiredRoles?: CurrentUserRole[],
): boolean {
    if (!requiredRoles || requiredRoles.length === 0) {
        return true;
    }
    return Boolean(user && requiredRoles.includes(user.role));
}

export function isPlatformAdminRole(role: string | undefined): boolean {
    return Boolean(role && PLATFORM_ADMIN_ROLES.has(role));
}

export function canUseAdminConsoleRole(role: string | undefined): boolean {
    return Boolean(role && SALES_TRAINER_ADMIN_CONSOLE_ROLES.has(role));
}

export function shouldStayInSalesTrainerAdmin(role: string | undefined): boolean {
    return Boolean(role && SALES_TRAINER_MANAGER_ENTRY_ROLES.has(role));
}
