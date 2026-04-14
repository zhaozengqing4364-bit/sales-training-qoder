import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "./client";

const fetchMock = vi.fn();

describe("api governance contract normalization", () => {
    beforeEach(() => {
        fetchMock.mockReset();
        vi.stubGlobal("fetch", fetchMock);
    });

    afterEach(() => {
        vi.unstubAllGlobals();
    });

    it("normalizes governance summaries for admin knowledge lists", async () => {
        fetchMock.mockResolvedValue({
            ok: true,
            json: async () => ({
                success: true,
                data: {
                    items: [
                        {
                            id: "kb-1",
                            name: "石犀产品知识库",
                            description: "销售资料",
                            category: "product",
                            status: "active",
                            document_count: 4,
                            total_chunks: 22,
                            created_at: "2026-03-20T00:00:00Z",
                            updated_at: "2026-03-25T08:00:00Z",
                            governance_summary: {
                                impact_summary: {
                                    impact_level: "high",
                                    recent_session_count: "18",
                                    active_session_count: 3,
                                    impacted_user_count: "7",
                                    last_session_at: "2026-03-26T09:30:00Z",
                                },
                                recent_change_summary: {
                                    last_changed_at: "2026-03-25T08:00:00Z",
                                    latest_change_type: "document_replace",
                                    latest_change_label: "最近文档：竞品对比",
                                    change_count_7d: "2",
                                    sessions_since_change: "5",
                                },
                                health_summary: {
                                    status: "blocking",
                                    anomaly_count: "2",
                                    blocking_count: "1",
                                    warning_count: 1,
                                    sample_anomalies: [
                                        {
                                            kind: "kb_lock_blocked_search_failed",
                                            severity: "blocking",
                                            summary: "知识库锁定模式下检索失败。",
                                            detected_at: "2026-03-26T09:00:00Z",
                                            session_id: "session-1",
                                            source: "support_runtime",
                                        },
                                    ],
                                },
                            },
                        },
                    ],
                    total: 1,
                },
            }),
        });

        const result = await api.admin.getKnowledgeBases();

        expect(result.items[0].governance_summary).toEqual({
            impact_summary: {
                impact_level: "high",
                recent_session_count: 18,
                active_session_count: 3,
                impacted_user_count: 7,
                last_session_at: "2026-03-26T09:30:00Z",
            },
            recent_change_summary: {
                last_changed_at: "2026-03-25T08:00:00Z",
                latest_change_type: "document_replace",
                latest_change_label: "最近文档：竞品对比",
                change_count_7d: 2,
                sessions_since_change: 5,
            },
            health_summary: {
                status: "blocking",
                anomaly_count: 2,
                blocking_count: 1,
                warning_count: 1,
                sample_anomalies: [
                    {
                        kind: "kb_lock_blocked_search_failed",
                        severity: "blocking",
                        summary: "知识库锁定模式下检索失败。",
                        detected_at: "2026-03-26T09:00:00Z",
                        session_id: "session-1",
                        source: "support_runtime",
                    },
                ],
            },
        });
    });

    it("normalizes governance summaries for runtime profiles used by the admin runtime page", async () => {
        fetchMock.mockResolvedValue({
            ok: true,
            json: async () => ({
                success: true,
                data: {
                    items: [
                        {
                            id: "runtime-1",
                            name: "销售默认 Realtime",
                            description: "线上主配置",
                            is_default: true,
                            is_active: true,
                            voice_mode: "stepfun_realtime",
                            model_name: "step-audio-2",
                            voice_name: "qingchunshaonv",
                            temperature: 0.7,
                            input_audio_format: "pcm16",
                            output_audio_format: "pcm16",
                            output_sample_rate: 24000,
                            turn_detection: null,
                            tool_policy: {
                                kb_lock_mode: "strict_audit",
                            },
                            governance_summary: {
                                impact_summary: {
                                    impact_level: "medium",
                                    recent_session_count: "9",
                                    active_session_count: "2",
                                    impacted_user_count: 4,
                                    last_session_at: "2026-03-26T11:30:00Z",
                                },
                                recent_change_summary: {
                                    last_changed_at: "2026-03-25T10:00:00Z",
                                    latest_change_type: "config_update",
                                    latest_change_label: "切换 KB 锁模式",
                                    change_count_7d: "3",
                                    sessions_since_change: "6",
                                },
                                health_summary: {
                                    status: "warning",
                                    anomaly_count: "1",
                                    blocking_count: 0,
                                    warning_count: "1",
                                    sample_anomalies: [],
                                },
                            },
                        },
                    ],
                    total: 1,
                },
            }),
        });

        const result = await api.admin.getVoiceRuntimeProfiles();

        expect(result.items[0].governance_summary).toEqual({
            impact_summary: {
                impact_level: "medium",
                recent_session_count: 9,
                active_session_count: 2,
                impacted_user_count: 4,
                last_session_at: "2026-03-26T11:30:00Z",
            },
            recent_change_summary: {
                last_changed_at: "2026-03-25T10:00:00Z",
                latest_change_type: "config_update",
                latest_change_label: "切换 KB 锁模式",
                change_count_7d: 3,
                sessions_since_change: 6,
            },
            health_summary: {
                status: "warning",
                anomaly_count: 1,
                blocking_count: 0,
                warning_count: 1,
                sample_anomalies: [],
            },
        });
    });

    it("normalizes linked asset changes for support runtime faults and drops incomplete entries", async () => {
        fetchMock.mockResolvedValue({
            ok: true,
            json: async () => ({
                success: true,
                data: {
                    generated_at: "2026-03-26T09:40:00Z",
                    items: [
                        {
                            source: "session",
                            severity: "blocking",
                            kind: "kb_lock_blocked_search_failed",
                            summary: "知识库锁定模式下检索失败。",
                            detected_at: "2026-03-26T09:30:00Z",
                            session_id: "session-1",
                            scenario_type: "sales",
                            session_status: "completed",
                            report_status: "completed",
                            diagnostics: {
                                linked_asset_changes: [
                                    {
                                        asset_type: "knowledge_base",
                                        asset_label: "知识库",
                                        asset_id: "kb-1",
                                        asset_name: "石犀产品知识库",
                                        admin_path: "/admin/knowledge",
                                        latest_change_label: "最近文档：竞品对比",
                                        latest_change_type: "document_replace",
                                        last_changed_at: "2026-03-25T08:00:00Z",
                                        change_count_7d: "2",
                                        sessions_since_change: "5",
                                        impact_level: "high",
                                        health_status: "blocking",
                                    },
                                    {
                                        asset_type: "persona",
                                        asset_id: "persona-1",
                                        asset_name: "预算压价角色",
                                        latest_change_label: "缺少管理路径，应被过滤",
                                    },
                                ],
                                extra_note: "keep me",
                            },
                        },
                    ],
                    count: 1,
                    limit: 20,
                    severity: null,
                },
            }),
        });

        const result = await api.supportRuntime.getFaults();

        expect(result.items[0].diagnostics).toEqual({
            linked_asset_changes: [
                {
                    asset_type: "knowledge_base",
                    asset_label: "知识库",
                    asset_id: "kb-1",
                    asset_name: "石犀产品知识库",
                    admin_path: "/admin/knowledge",
                    latest_change_label: "最近文档：竞品对比",
                    latest_change_type: "document_replace",
                    last_changed_at: "2026-03-25T08:00:00Z",
                    change_count_7d: 2,
                    sessions_since_change: 5,
                    impact_level: "high",
                    health_status: "blocking",
                },
            ],
            extra_note: "keep me",
        });
    });
});
