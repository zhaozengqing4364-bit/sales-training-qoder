export const DEFAULT_RECOMMENDATION_FALLBACK_PATH = "/training";

const RECOMMENDATION_ROUTE_BASE_URL = "https://qoder.local";
const ALLOWED_RECOMMENDATION_ROUTE_PREFIXES = [
    "/training",
    "/agents",
    "/practice",
    "/history",
] as const;

export type RecommendationPathDowngradeReason =
    | "not_string"
    | "empty"
    | "control_character"
    | "absolute_or_protocol_url"
    | "malformed_url"
    | "unsafe_encoded_path"
    | "path_traversal"
    | "unsupported_route";

export interface NormalizedRecommendationPath {
    href: string;
    downgraded: boolean;
    reason: RecommendationPathDowngradeReason | null;
}

function safeDecodePath(value: string): string | null {
    try {
        let current = value;
        for (let attempts = 0; attempts < 3; attempts += 1) {
            const decoded = decodeURIComponent(current);
            if (decoded === current) {
                return decoded;
            }
            current = decoded;
        }
        return current;
    } catch {
        return null;
    }
}

function reject(reason: RecommendationPathDowngradeReason, fallbackPath: string): NormalizedRecommendationPath {
    return {
        href: fallbackPath,
        downgraded: true,
        reason,
    };
}

function isAllowedRecommendationRoute(pathname: string): boolean {
    return ALLOWED_RECOMMENDATION_ROUTE_PREFIXES.some((prefix) => (
        pathname === prefix || pathname.startsWith(`${prefix}/`)
    ));
}

function getRawPathname(value: string): string {
    const queryIndex = value.indexOf("?");
    const hashIndex = value.indexOf("#");
    const cutPoints = [queryIndex, hashIndex].filter((index) => index >= 0);
    const endIndex = cutPoints.length > 0 ? Math.min(...cutPoints) : value.length;
    return value.slice(0, endIndex);
}

export function normalizeInternalRecommendationPath(
    targetPath: unknown,
    fallbackPath = DEFAULT_RECOMMENDATION_FALLBACK_PATH,
): NormalizedRecommendationPath {
    if (typeof targetPath !== "string") {
        return reject("not_string", fallbackPath);
    }

    const trimmed = targetPath.trim();
    if (!trimmed) {
        return reject("empty", fallbackPath);
    }

    if (/[\u0000-\u001f\u007f]/.test(trimmed)) {
        return reject("control_character", fallbackPath);
    }

    if (/^[a-z][a-z0-9+.-]*:/i.test(trimmed) || trimmed.startsWith("//")) {
        return reject("absolute_or_protocol_url", fallbackPath);
    }

    const rawPathname = getRawPathname(trimmed);
    const decodedRawPathname = safeDecodePath(rawPathname);
    if (!decodedRawPathname) {
        return reject("unsafe_encoded_path", fallbackPath);
    }

    if (
        decodedRawPathname.includes("\\")
        || decodedRawPathname.includes("://")
        || decodedRawPathname.includes("//")
        || decodedRawPathname.toLowerCase().includes("javascript:")
    ) {
        return reject("unsafe_encoded_path", fallbackPath);
    }

    if (decodedRawPathname.split("/").includes("..")) {
        return reject("path_traversal", fallbackPath);
    }

    let parsed: URL;
    try {
        parsed = new URL(trimmed, RECOMMENDATION_ROUTE_BASE_URL);
    } catch {
        return reject("malformed_url", fallbackPath);
    }

    if (parsed.origin !== RECOMMENDATION_ROUTE_BASE_URL) {
        return reject("absolute_or_protocol_url", fallbackPath);
    }

    if (!isAllowedRecommendationRoute(parsed.pathname)) {
        return reject("unsupported_route", fallbackPath);
    }

    return {
        href: `${parsed.pathname}${parsed.search}${parsed.hash}`,
        downgraded: false,
        reason: null,
    };
}
