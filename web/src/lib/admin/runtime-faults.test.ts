import { describe, expect, it } from "vitest";

import {
  buildLinkedRuntimeFaultEntries,
  buildRuntimeFaultBySessionId,
} from "./runtime-faults";
import type { SupportRuntimeFaultItem } from "@/lib/api/types";

describe("runtime-faults", () => {
  const runtimeFaults: SupportRuntimeFaultItem[] = [
    {
      kind: "kb_lock_blocked_search_failed",
      source: "session",
      severity: "blocking",
      summary: "知识库检索失败",
      detected_at: "2026-03-25T08:00:00Z",
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
            change_count_7d: 2,
            sessions_since_change: 5,
            impact_level: "high",
            health_status: "blocking",
          },
        ],
      },
    },
    {
      kind: "message_scores_missing",
      source: "session",
      severity: "warning",
      summary: "消息评分缺失",
      detected_at: "2026-03-25T09:00:00Z",
      session_id: "session-1",
      scenario_type: "sales",
      session_status: "completed",
      report_status: "completed",
      diagnostics: {
        linked_asset_changes: [
          {
            asset_type: "persona",
            asset_label: "角色",
            asset_id: "persona-1",
            asset_name: "预算压价角色",
            admin_path: "/admin/personas",
            latest_change_label: "最近策略：提高压价强度",
            latest_change_type: "policy_update",
            last_changed_at: "2026-03-25T09:00:00Z",
            change_count_7d: 1,
            sessions_since_change: 3,
            impact_level: "medium",
            health_status: "warning",
          },
        ],
      },
    },
    {
      kind: "stuck_scoring",
      source: "session",
      severity: "blocking",
      summary: "评分卡住",
      detected_at: "2026-03-25T09:30:00Z",
      session_id: "session-2",
      scenario_type: "sales",
      session_status: "scoring",
      report_status: "processing",
      diagnostics: {
        linked_asset_changes: [],
      },
    },
    {
      kind: "warning_without_session",
      source: "system_log",
      severity: "warning",
      summary: "系统警告",
      detected_at: "2026-03-25T10:00:00Z",
      session_id: null,
      scenario_type: null,
      session_status: null,
      report_status: null,
      diagnostics: {
        linked_asset_changes: [
          {
            asset_type: "runtime_profile",
            asset_label: "运行时配置",
            asset_id: "runtime-1",
            asset_name: "销售默认 Realtime",
            admin_path: "/admin/voice-runtime",
            latest_change_label: "最近配置：切换 KB 锁模式",
            latest_change_type: "config_update",
            last_changed_at: "2026-03-25T10:00:00Z",
            change_count_7d: 3,
            sessions_since_change: 6,
            impact_level: "high",
            health_status: "blocking",
          },
        ],
      },
    },
  ];

  it("builds analytics-linked runtime fault entries from only faults with linked assets", () => {
    expect(buildLinkedRuntimeFaultEntries(runtimeFaults)).toHaveLength(3);
    expect(buildLinkedRuntimeFaultEntries(runtimeFaults, { limit: 2 })).toHaveLength(2);
    expect(buildLinkedRuntimeFaultEntries(runtimeFaults)[0]).toMatchObject({
      fault: runtimeFaults[0],
      assetChanges: runtimeFaults[0].diagnostics.linked_asset_changes,
    });
  });

  it("indexes the first linked runtime fault per session for user-detail drill-ins", () => {
    const bySessionId = buildRuntimeFaultBySessionId(runtimeFaults);

    expect(Array.from(bySessionId.keys())).toEqual(["session-1"]);
    expect(bySessionId.get("session-1")).toMatchObject({
      fault: runtimeFaults[0],
      assetChanges: runtimeFaults[0].diagnostics.linked_asset_changes,
    });
    expect(bySessionId.has("session-2")).toBe(false);
  });
});
