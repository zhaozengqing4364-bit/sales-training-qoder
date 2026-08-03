export type CurrentUserRole = "admin" | "user" | "support" | (string & {});

export const PLATFORM_ADMIN_ROLE_VALUES = ["admin", "super_admin"] as const;
export const SALES_TRAINER_CONTENT_ADMIN_ROLE_VALUES = [
    "content_admin",
    "newcomer_content_admin",
] as const;
export const SALES_TRAINER_MANAGER_ROLE_VALUES = [
    "support",
    "training_lead",
    "training_manager",
] as const;
export const SALES_TRAINER_OPERATIONS_ROLE_VALUES = [
    "operations",
    "ops",
    "operator",
    "sre",
] as const;
export const READONLY_AUDITOR_ROLE_VALUES = ["readonly_auditor"] as const;
export const ADMIN_CONSOLE_ROLE_VALUES = [
    ...PLATFORM_ADMIN_ROLE_VALUES,
    ...SALES_TRAINER_CONTENT_ADMIN_ROLE_VALUES,
    ...SALES_TRAINER_MANAGER_ROLE_VALUES,
    ...SALES_TRAINER_OPERATIONS_ROLE_VALUES,
    ...READONLY_AUDITOR_ROLE_VALUES,
] as const;
export const SALES_TRAINER_MANAGER_ENTRY_ROLE_VALUES = [
    ...SALES_TRAINER_CONTENT_ADMIN_ROLE_VALUES,
    ...SALES_TRAINER_MANAGER_ROLE_VALUES,
    ...SALES_TRAINER_OPERATIONS_ROLE_VALUES,
] as const;

const PLATFORM_ADMIN_ROLES = new Set<string>(PLATFORM_ADMIN_ROLE_VALUES);
const ADMIN_CONSOLE_ROLES = new Set<string>(ADMIN_CONSOLE_ROLE_VALUES);
const SALES_TRAINER_MANAGER_ENTRY_ROLES = new Set<string>(
    SALES_TRAINER_MANAGER_ENTRY_ROLE_VALUES,
);
const SALES_TRAINER_CONTENT_ADMIN_ROLES = new Set<string>(
    SALES_TRAINER_CONTENT_ADMIN_ROLE_VALUES,
);
const SALES_TRAINER_OPERATIONS_ROLES = new Set<string>(
    SALES_TRAINER_OPERATIONS_ROLE_VALUES,
);

export const SALES_TRAINER_ADMIN_CONSOLE_ROLE_VALUES = ADMIN_CONSOLE_ROLE_VALUES;

type CurrentUserRecord = {
    id?: unknown;
    user_id?: unknown;
    name?: unknown;
    display_name?: unknown;
    email?: unknown;
    role?: unknown;
    team?: unknown;
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
    team?: { team_id: string; code: string; name: string } | null;
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

function roleMatchesRequiredRole(role: CurrentUserRole, requiredRole: CurrentUserRole): boolean {
    if (role === requiredRole) {
        return true;
    }
    if (requiredRole === "admin" && PLATFORM_ADMIN_ROLES.has(role)) {
        return true;
    }
    if (
        requiredRole === "content_admin"
        && SALES_TRAINER_CONTENT_ADMIN_ROLES.has(role)
    ) {
        return true;
    }
    if (requiredRole === "operations" && SALES_TRAINER_OPERATIONS_ROLES.has(role)) {
        return true;
    }
    return false;
}

export function normalizeCurrentUser(input: unknown): CurrentUser {
    const raw = toRecord(input);
    const id = toStringValue(raw.id, toStringValue(raw.user_id));
    const displayName = toStringValue(raw.display_name, toStringValue(raw.name, "用户")) || "用户";
    const email = toStringValue(raw.email);
    const teamRecord = raw.team && typeof raw.team === "object"
        ? raw.team as Record<string, unknown>
        : null;
    const teamId = toStringValue(teamRecord?.team_id);
    const teamCode = toStringValue(teamRecord?.code);
    const teamName = toStringValue(teamRecord?.name);
    const avatarUrl = toStringValue(raw.avatar_url);

    return {
        user_id: id,
        id,
        name: displayName,
        display_name: displayName,
        email,
        role: normalizeRole(raw.role),
        team: teamId && teamCode && teamName
            ? { team_id: teamId, code: teamCode, name: teamName }
            : null,
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
    return Boolean(
        user
        && requiredRoles.some((requiredRole) =>
            roleMatchesRequiredRole(user.role, normalizeRole(requiredRole)),
        ),
    );
}

export function isPlatformAdminRole(role: string | undefined): boolean {
    return Boolean(role && PLATFORM_ADMIN_ROLES.has(normalizeRole(role)));
}

export function canUseAdminConsoleRole(role: string | undefined): boolean {
    return Boolean(role && ADMIN_CONSOLE_ROLES.has(normalizeRole(role)));
}

export function shouldStayInSalesTrainerAdmin(role: string | undefined): boolean {
    return Boolean(role && SALES_TRAINER_MANAGER_ENTRY_ROLES.has(normalizeRole(role)));
}
