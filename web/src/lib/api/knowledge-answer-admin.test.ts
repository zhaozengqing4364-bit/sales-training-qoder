import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "./client";
import type { AdminKnowledgeChunkingPreset } from "./types";

const fetchMock = vi.fn();

describe("knowledge answer admin api client", () => {
    beforeEach(() => {
        fetchMock.mockReset();
        vi.stubGlobal("fetch", fetchMock);
    });

    afterEach(() => {
        vi.unstubAllGlobals();
    });

    it("loads the active admin knowledge-answer config", async () => {
        fetchMock.mockResolvedValue({
            ok: true,
            json: async () => ({
                success: true,
                data: {
                    active_version: {
                        id: "cfg-1",
                        version_name: "rollout-v1",
                        status: "active",
                        enabled: true,
                        updated_at: "2026-03-31T07:00:00Z",
                    },
                    profile_source: "database",
                    summary: {
                        query_profile_count: 1,
                        intent_rule_count: 2,
                        entity_alias_count: 3,
                        ranking_profile_count: 1,
                        answerability_profile_count: 1,
                    },
                    selected_profiles: {
                        query_profile_keys: ["intro_v1"],
                        ranking_profile_keys: ["default_rank"],
                        answerability_profile_keys: ["default_answerability"],
                    },
                },
            }),
        });

        const result = await api.admin.getKnowledgeAnswerAdminConfig();

        expect(result.active_version?.version_name).toBe("rollout-v1");
        expect(result.summary.intent_rule_count).toBe(2);
        expect(result.selected_profiles.query_profile_keys).toEqual(["intro_v1"]);
        expect(fetchMock).toHaveBeenCalledWith(
            expect.stringContaining("/admin/knowledge-answer/config"),
            expect.any(Object),
        );
    });

    it("loads enabled config options for the selector", async () => {
        fetchMock.mockResolvedValue({
            ok: true,
            json: async () => ({
                success: true,
                data: {
                    versions: [
                        {
                            id: "cfg-2",
                            version_name: "rollout-v2",
                            status: "draft",
                            enabled: true,
                            updated_at: "2026-03-31T08:00:00Z",
                        },
                    ],
                },
            }),
        });

        const result = await api.admin.getKnowledgeAnswerAdminConfigOptions();

        expect(result.versions).toHaveLength(1);
        expect(result.versions[0].id).toBe("cfg-2");
        expect(result.versions[0].enabled).toBe(true);
    });

    it("updates the active admin config version", async () => {
        fetchMock.mockResolvedValue({
            ok: true,
            json: async () => ({
                success: true,
                data: {
                    active_version: {
                        id: "cfg-2",
                        version_name: "rollout-v2",
                        status: "active",
                        enabled: true,
                        updated_at: "2026-03-31T08:05:00Z",
                    },
                    profile_source: "database",
                    summary: {
                        query_profile_count: 1,
                        intent_rule_count: 1,
                        entity_alias_count: 1,
                        ranking_profile_count: 1,
                        answerability_profile_count: 1,
                    },
                    selected_profiles: {
                        query_profile_keys: ["intro_v2"],
                        ranking_profile_keys: ["default_rank"],
                        answerability_profile_keys: ["default_answerability"],
                    },
                },
            }),
        });

        const result = await api.admin.updateKnowledgeAnswerAdminConfig({ config_version_id: "cfg-2" });

        expect(result.active_version?.id).toBe("cfg-2");
        expect(fetchMock).toHaveBeenCalledWith(
            expect.stringContaining("/admin/knowledge-answer/config"),
            expect.objectContaining({
                method: "PUT",
                body: JSON.stringify({ config_version_id: "cfg-2" }),
            }),
        );
    });

    it("loads recent knowledge-answer runs and step details", async () => {
        fetchMock
            .mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    success: true,
                    data: {
                        items: [
                            {
                                id: "run-1",
                                session_id: "session-1",
                                config_version_id: "cfg-1",
                                entrypoint: "stepfun_realtime",
                                query_text: "请介绍一下石犀科技",
                                answerability: "sufficient",
                                final_status: "completed",
                                blocked_reason: null,
                                step_count: 3,
                                created_at: "2026-03-31T10:00:00Z",
                                updated_at: "2026-03-31T10:00:02Z",
                            },
                        ],
                        total: 1,
                        limit: 10,
                        page: 2,
                        offset: 10,
                        session_id: null,
                    },
                }),
            })
            .mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    success: true,
                    data: {
                        id: "run-1",
                        session_id: "session-1",
                        config_version_id: "cfg-1",
                        entrypoint: "stepfun_realtime",
                        query_text: "请介绍一下石犀科技",
                        answerability: "sufficient",
                        final_status: "completed",
                        blocked_reason: null,
                        citations: [{ document_title: "产品手册" }],
                        retrieval_summary: { hit_count: 1 },
                        created_at: "2026-03-31T10:00:00Z",
                        updated_at: "2026-03-31T10:00:02Z",
                    },
                }),
            })
            .mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    success: true,
                    data: {
                        run_id: "run-1",
                        items: [
                            {
                                id: "step-1",
                                answer_run_id: "run-1",
                                step_name: "resolve",
                                step_order: 1,
                                status: "completed",
                                input_payload: { query: "请介绍一下石犀科技" },
                                output_payload: { canonical_entity: "石犀科技" },
                                duration_ms: 4,
                                created_at: "2026-03-31T10:00:00Z",
                                updated_at: "2026-03-31T10:00:00Z",
                            },
                        ],
                        total: 1,
                    },
                }),
            });

        const runs = await api.admin.listKnowledgeAnswerRuns({
            limit: 10,
            page: 2,
            query: "石犀",
            answerability: "sufficient",
            final_status: "completed",
        });
        const detail = await api.admin.getKnowledgeAnswerRunDetail("run-1");
        const steps = await api.admin.getKnowledgeAnswerRunSteps("run-1");

        expect(runs.items[0].query_text).toBe("请介绍一下石犀科技");
        expect(detail.retrieval_summary.hit_count).toBe(1);
        expect(steps.items[0].step_name).toBe("resolve");
        expect(fetchMock).toHaveBeenNthCalledWith(
            1,
            expect.stringContaining("/knowledge-debug/runs?limit=10&page=2&query=%E7%9F%B3%E7%8A%80&answerability=sufficient&final_status=completed"),
            expect.any(Object),
        );
    });

    it("unwraps chunking preset envelopes across list and mutation calls", async () => {
        const preset: AdminKnowledgeChunkingPreset = {
            id: "preset-1",
            config_version_id: "cfg-1",
            profile_key: "default",
            description: "默认分块预设",
            chunking_strategy: "element_boundary",
            chunk_size: 500,
            chunk_overlap: 50,
            is_default: true,
            enabled: true,
            created_at: "2026-04-01T00:00:00Z",
            updated_at: "2026-04-01T00:00:00Z",
        };

        fetchMock
            .mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    success: true,
                    data: {
                        items: [preset],
                        total: 1,
                    },
                }),
            })
            .mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    success: true,
                    data: preset,
                }),
            })
            .mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    success: true,
                    data: preset,
                }),
            })
            .mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    success: true,
                    data: preset,
                }),
            })
            .mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    success: true,
                    data: preset,
                }),
            })
            .mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    success: true,
                    data: preset,
                }),
            });

        const list = await api.admin.getKnowledgeChunkingPresets("cfg-1");
        const created = await api.admin.createKnowledgeChunkingPreset("cfg-1", {
            profile_key: "default",
            description: "默认分块预设",
            chunking_strategy: "element_boundary",
            chunk_size: 500,
            chunk_overlap: 50,
            is_default: true,
            enabled: true,
        });
        const updated = await api.admin.updateKnowledgeChunkingPreset("cfg-1", "preset-1", {
            profile_key: "default-v2",
            enabled: false,
        });
        const deleted = await api.admin.deleteKnowledgeChunkingPreset("cfg-1", "preset-1");
        const setDefault = await api.admin.setDefaultChunkingPreset("cfg-1", "preset-1");
        const toggled = await api.admin.updateKnowledgeChunkingPreset("cfg-1", "preset-1", { enabled: false });

        expect(list).toEqual([preset]);
        expect(created).toEqual(preset);
        expect(updated).toEqual(preset);
        expect(deleted).toEqual(preset);
        expect(setDefault).toEqual(preset);
        expect(toggled).toEqual(preset);
        expect(fetchMock).toHaveBeenNthCalledWith(
            1,
            expect.stringContaining("/admin/knowledge-answer/versions/cfg-1/chunking-presets"),
            expect.any(Object),
        );
        expect(fetchMock).toHaveBeenNthCalledWith(
            2,
            expect.stringContaining("/admin/knowledge-answer/versions/cfg-1/chunking-presets"),
            expect.objectContaining({
                method: "POST",
                body: JSON.stringify({
                    profile_key: "default",
                    description: "默认分块预设",
                    chunking_strategy: "element_boundary",
                    chunk_size: 500,
                    chunk_overlap: 50,
                    is_default: true,
                    enabled: true,
                }),
            }),
        );
    });
});
