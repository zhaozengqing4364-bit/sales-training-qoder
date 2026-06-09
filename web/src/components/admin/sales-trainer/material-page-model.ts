import type {
    SalesTrainerMaterial,
    SalesTrainerMaterialCreateRequest,
    SalesTrainerMaterialType,
    SalesTrainerMaterialVersionCreateRequest,
} from "@/lib/api/types";

export type VersionDraft = SalesTrainerMaterialVersionCreateRequest;

const MATERIAL_UPLOAD_ACCEPT_TYPES = [
    ".ppt",
    ".pptx",
    ".pdf",
    ".doc",
    ".docx",
    ".md",
    ".txt",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
] as const;

export const MATERIAL_UPLOAD_ACCEPT = MATERIAL_UPLOAD_ACCEPT_TYPES.join(",");

export const MATERIAL_TYPE_OPTIONS = [
    { value: "ppt_deck", label: "PPT 主胶片" },
    { value: "script", label: "逐字稿" },
    { value: "example_audio", label: "示例录音" },
    { value: "attachment", label: "附件" },
] as const satisfies readonly {
    readonly value: SalesTrainerMaterialType;
    readonly label: string;
}[];

export const MATERIAL_TYPE_LABELS: Readonly<Record<SalesTrainerMaterialType, string>> = {
    ppt_deck: "PPT 主胶片",
    script: "逐字稿",
    example_audio: "示例录音",
    attachment: "附件",
};

export function createEmptyMaterialDraft(purpose: string | null): SalesTrainerMaterialCreateRequest {
    return {
        material_key: "",
        name: "",
        material_type: "ppt_deck",
        description: "",
        purpose: purpose || "ppt_pitch",
    };
}

export function createEmptyVersionDraft(): VersionDraft {
    return {
        version_label: "",
        title: "",
        file_name: "",
        content_type: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        file_size_bytes: 1,
        storage_key: "",
        file_hash: "",
        release_notes: "",
    };
}

export function createDefaultVersionLabel(date = new Date()): string {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    const hour = String(date.getHours()).padStart(2, "0");
    const minute = String(date.getMinutes()).padStart(2, "0");
    return `v${year}.${month}.${day}-${hour}${minute}`;
}

export function applyFileToVersionDraft(
    current: VersionDraft,
    file: File,
    materialName: string,
): VersionDraft {
    const versionLabel = current.version_label.trim() || createDefaultVersionLabel();
    return {
        ...current,
        version_label: versionLabel,
        title: current.title.trim() || `${materialName} ${versionLabel}`,
        file_name: file.name,
        content_type: file.type || "application/octet-stream",
        file_size_bytes: file.size || 1,
        storage_key: "",
    };
}

export function formatFileSize(sizeBytes: number): string {
    if (sizeBytes >= 1024 * 1024) {
        return `${(sizeBytes / (1024 * 1024)).toFixed(1)} MB`;
    }
    if (sizeBytes >= 1024) {
        return `${(sizeBytes / 1024).toFixed(1)} KB`;
    }
    return `${sizeBytes} B`;
}

export function toMaterialType(value: string): SalesTrainerMaterialType {
    switch (value) {
        case "ppt_deck":
        case "script":
        case "example_audio":
        case "attachment":
            return value;
        default:
            return "ppt_deck";
    }
}

export function firstSelectedMaterial(
    items: readonly SalesTrainerMaterial[],
    selectedMaterialId: string | null,
): SalesTrainerMaterial | null {
    return items.find((item) => item.material_id === selectedMaterialId) ?? items[0] ?? null;
}
