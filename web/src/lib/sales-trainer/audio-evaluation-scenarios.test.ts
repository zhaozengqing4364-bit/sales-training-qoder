import { describe, expect, it } from "vitest";

import {
    audioEvaluationScenarioForModule,
    audioEvaluationScenarioForPurpose,
    audioEvaluationScenarioForSlug,
    isAudioEvaluationModuleKey,
} from "./audio-evaluation-scenarios";

describe("audio evaluation scenarios", () => {
    it("registers product demo as the same audio evaluation capability as PPT explanation", () => {
        const productDemo = audioEvaluationScenarioForSlug("company-product-demo");

        expect(productDemo?.scenarioKey).toBe("company_product_demo");
        expect(productDemo?.moduleType).toBe("audio_scoring");
        expect(productDemo?.purposeKey).toBe("company_product_demo");
        expect(productDemo?.materialRequired).toBe(true);
    });

    it("maps legacy PPT purpose to the PPT explanation scenario", () => {
        expect(audioEvaluationScenarioForPurpose("ppt_pitch")?.scenarioKey).toBe("ppt_explanation");
        expect(audioEvaluationScenarioForModule("ppt_explanation").purposeKey).toBe("ppt_pitch");
    });

    it("keeps non-audio path modules out of audio scenario editing", () => {
        expect(isAudioEvaluationModuleKey("company_product_demo")).toBe(true);
        expect(isAudioEvaluationModuleKey("business_skills")).toBe(false);
    });
});
