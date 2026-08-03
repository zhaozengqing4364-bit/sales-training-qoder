import { describe, expect, it, vi } from "vitest";

import {
    createAdminSalesTrainerDomain,
    createSalesTrainerDomain,
} from "./domains/sales-trainer";

describe("legacy audio client clean cut", () => {
    const dependencies = {
        request: vi.fn(),
        upload: vi.fn(),
        resolveApiBaseUrl: () => "/api/v1",
    };

    it("keeps legacy learner audio history read-only", () => {
        const client = createSalesTrainerDomain(dependencies);
        expect(client).toHaveProperty("getAudioSubmission");
        expect(client).toHaveProperty("listMyAudioSubmissions");
        expect(client).not.toHaveProperty("getAudioUploadUrl");
        expect(client).not.toHaveProperty("uploadAudioSubmission");
        expect(client).not.toHaveProperty("uploadAudioSubmissionDirect");
        expect(client).not.toHaveProperty("registerAudioSubmission");
    });

    it("removes legacy admin retry and audio regrade writers", () => {
        const client = createAdminSalesTrainerDomain(dependencies);
        expect(client).not.toHaveProperty("getAudioSubmission");
        expect(client).not.toHaveProperty("getAudioSubmissionFileUrl");
        expect(client).not.toHaveProperty("retryAudioTranscription");
        expect(client).not.toHaveProperty("retryAudioScoring");
        expect(client).not.toHaveProperty("previewAudioSubmissionRegrade");
        expect(client).not.toHaveProperty("runAudioSubmissionRegrade");
    });
});
