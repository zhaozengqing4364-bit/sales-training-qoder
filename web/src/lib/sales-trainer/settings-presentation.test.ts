import { describe, expect, it } from "vitest";

import {
    formatAsrMode,
    formatAsrModel,
    formatFallbackReason,
    formatPolicySource,
    formatStorageBackend,
} from "./settings-presentation";

describe("sales trainer settings presentation", () => {
    it("maps internal configuration values into administrator language", () => {
        expect(formatStorageBackend("file")).toBe("服务器存储");
        expect(formatAsrMode("file")).toBe("录音文件识别");
        expect(formatAsrModel("fun-asr")).toBe("标准中文语音识别");
        expect(formatFallbackReason("active_missing")).toBe("当前没有已发布策略，已使用安全默认值");
        expect(formatPolicySource("config_service")).toBe("配置中心");
        expect(formatPolicySource("database_previous")).toBe("上一版已发布配置");
    });

    it("does not echo unknown internal enum values", () => {
        expect(formatStorageBackend("internal-store-v9")).toBe("其他存储方案");
        expect(formatAsrMode("internal-asr-v9")).toBe("其他识别方案");
        expect(formatAsrModel("internal-model-v9")).toBe("其他识别模型");
        expect(formatFallbackReason("internal_reason_9")).toBe("已使用安全默认值");
        expect(formatPolicySource("internal-source-v9")).toBe("系统配置");
    });
});
