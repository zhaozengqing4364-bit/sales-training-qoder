import { describe, expect, it } from "vitest";

import {
    formatAdminRecordStatus,
    formatAdminStatus,
    formatAudioSourceLabel,
    formatScorePromptPurpose,
    formatTrainingTaskDisplay,
    filterNewcomerAdminUnits,
    normalizeNewcomerUnitDisplay,
} from "./admin-display";
import type { SalesTrainerUnit } from "@/lib/api/types";

describe("sales trainer admin display helpers", () => {
    it("maps lifecycle and runtime statuses to admin-facing Chinese labels", () => {
        expect(formatAdminStatus("draft")).toBe("草稿");
        expect(formatAdminStatus("published")).toBe("已发布");
        expect(formatAdminStatus("archived")).toBe("已归档");
        expect(formatAdminRecordStatus("scored")).toBe("已评分");
        expect(formatAdminRecordStatus("submitted")).toBe("已提交，待判分");
        expect(formatAdminRecordStatus("transcription_failed")).toBe("转写失败");
        expect(formatAdminRecordStatus("unknown_status")).toBe("未识别状态");
    });

    it("keeps technical ids as secondary diagnostics instead of primary task names", () => {
        expect(formatTrainingTaskDisplay("PPT 讲解录音", "unit-1")).toEqual({
            title: "PPT 讲解录音",
            detail: "编号：unit-1",
        });
        expect(formatTrainingTaskDisplay(null, "unit-1")).toEqual({
            title: "未命名训练任务",
            detail: "编号：unit-1",
        });
    });

    it("maps score prompt purpose codes to business labels", () => {
        expect(formatScorePromptPurpose("ppt_pitch")).toBe("PPT 讲解录音");
        expect(formatScorePromptPurpose("general_audio_scoring")).toBe("通用录音评分");
        expect(formatScorePromptPurpose("unknown_purpose")).toBe("自定义用途");
    });

    it("maps technical audio sources to business labels", () => {
        expect(formatAudioSourceLabel("/sales-trainer/audio/unit-1")).toBe("学员录音上传页");
        expect(formatAudioSourceLabel("sales_trainer_audio_upload")).toBe("学员录音上传页");
        expect(formatAudioSourceLabel("/sales-trainer/business-skills")).toBe("商务技巧学习页");
        expect(formatAudioSourceLabel("/sales-trainer")).toBe("新人训练路径首页");
        expect(formatAudioSourceLabel("/custom/internal")).toBe("自定义入口");
        expect(formatAudioSourceLabel(null)).toBe("未知来源");
    });

    it("normalizes legacy module seed wording before showing newcomer units", () => {
        const legacyUnit = {
            unit_id: "unit-legacy",
            name: "模块二：拜访前商务",
            description: "阅读 COO 谈市场十五讲，章节可任意顺序浏览，无强制通关顺序。",
            unit_type: "quiz",
            config: { path: { module_key: "business_skills" } },
            status: "published",
            created_by: "admin-1",
            updated_by: "admin-1",
            created_at: "2026-06-01T00:00:00Z",
            updated_at: "2026-06-02T00:00:00Z",
            questions: [],
        } satisfies SalesTrainerUnit;

        expect(normalizeNewcomerUnitDisplay(legacyUnit)).toMatchObject({
            name: "模块二：商务技巧",
            description: "阅读见客户前商务礼仪学习内容，并完成商务技巧考卷。",
        });
    });

    it("scopes admin unit lists to current newcomer path units when they exist", () => {
        const currentUnit = {
            unit_id: "unit-current",
            name: "商务技巧",
            description: "阅读见客户前商务礼仪文章并完成考卷。",
            unit_type: "quiz",
            config: { path: { path_key: "newcomer_training_path_v1", module_key: "business_skills" } },
            status: "published",
            created_by: "admin-1",
            updated_by: "admin-1",
            created_at: "2026-06-01T00:00:00Z",
            updated_at: "2026-06-02T00:00:00Z",
            questions: [],
        } satisfies SalesTrainerUnit;
        const legacyCooUnit = {
            ...currentUnit,
            unit_id: "unit-coo",
            name: "COO系列之1：陌拜实战测验",
            description: "COO谈市场系列之1配套测验。",
            config: { path: { path_key: "new_seller_goal_path" } },
        } satisfies SalesTrainerUnit;

        expect(filterNewcomerAdminUnits([legacyCooUnit, currentUnit])).toEqual([currentUnit]);
    });
});
