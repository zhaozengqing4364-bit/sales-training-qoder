import type {
    NewcomerTrainingModuleType,
    SalesTrainerUnit,
} from "@/lib/api/types";

type PathConfig = NonNullable<SalesTrainerUnit["config"]["path"]>;

export function getPathConfig(unit?: SalesTrainerUnit | null): PathConfig {
    const config = unit?.config?.path;
    return config && typeof config === "object" && !Array.isArray(config) ? config : {};
}

export function pathConfigString(config: PathConfig, key: string): string {
    const value = config[key];
    return typeof value === "string" ? value : "";
}

export function pathConfigNumberText(config: PathConfig, key: string): string {
    const value = config[key];
    return typeof value === "number" && Number.isFinite(value) ? String(value) : "";
}

export function pathConfigModuleType(value: unknown): NewcomerTrainingModuleType | "" {
    switch (value) {
        case "audio_scoring":
        case "article_exam":
        case "audio_scoring_group":
        case "realtime_placeholder":
            return value;
        default:
            return "";
    }
}

export function guidanceTemplateText(config: PathConfig): string {
    const templates = config.guidance_templates;
    if (!templates || typeof templates !== "object" || Array.isArray(templates)) {
        return "";
    }
    return Object.entries(templates).map(([key, value]) => `${key}: ${String(value)}`).join("\n");
}
