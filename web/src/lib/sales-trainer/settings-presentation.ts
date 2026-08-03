const STORAGE_BACKEND_LABELS: Readonly<Record<string, string>> = {
    file: "服务器存储",
    local: "服务器存储",
    cos: "腾讯云对象存储",
    oss: "阿里云对象存储",
};

const ASR_MODE_LABELS: Readonly<Record<string, string>> = {
    file: "录音文件识别",
    legacy: "兼容识别流程",
    mock: "未接入正式识别服务",
    dashscope: "云端语音识别",
    local: "本地语音识别",
    disabled: "未启用语音识别",
};

const ASR_MODEL_LABELS: Readonly<Record<string, string>> = {
    "fun-asr": "标准中文语音识别",
    "paraformer-v2": "标准中文语音识别",
    "qwen3-asr-flash-realtime": "实时中文语音识别",
};

const POLICY_SOURCE_LABELS: Readonly<Record<string, string>> = {
    config_service: "配置中心",
    active_config: "已发布配置",
    database: "已发布配置",
    database_previous: "上一版已发布配置",
    default: "安全默认值",
};

const FALLBACK_REASON_LABELS: Readonly<Record<string, string>> = {
    active_missing: "当前没有已发布策略，已使用安全默认值",
    active_invalid: "已发布策略校验未通过，已使用安全默认值",
    load_failed: "策略读取失败，已使用安全默认值",
};

export function formatStorageBackend(value: string): string {
    return STORAGE_BACKEND_LABELS[value] ?? "其他存储方案";
}

export function formatAsrMode(value: string): string {
    return ASR_MODE_LABELS[value] ?? "其他识别方案";
}

export function formatAsrModel(value: string): string {
    return ASR_MODEL_LABELS[value] ?? "其他识别模型";
}

export function formatPolicySource(value: unknown): string {
    return typeof value === "string"
        ? POLICY_SOURCE_LABELS[value] ?? "系统配置"
        : "--";
}

export function formatFallbackReason(value: unknown): string {
    if (value == null || value === "") {
        return "未使用安全默认值";
    }
    return typeof value === "string"
        ? FALLBACK_REASON_LABELS[value] ?? "已使用安全默认值"
        : "已使用安全默认值";
}
