import { describe, expect, it } from "vitest";

import type { SupportRuntimeFaultItem } from "@/lib/api/types";
import {
  buildLinkedRuntimeFaultEntries,
  buildRuntimeFaultBySessionId,
} from "./runtime-faults";
import type { SupportRuntimeFaultItem } from "@/lib/api/types";

describe("runtime-faults", () => {
  const faultBase = {
    source: "session",
    severity: "warning",
    summary: "runtime fault",
    detected_at: "2026-03-25T08:00:00Z",
    scenario_type: "sales",
    session_status: "completed",
    report_status: "completed",
  } satisfies Omit<SupportRuntimeFaultItem, "kind" | "session_id" | "diagnostics">;

  const runtimeFaults = [
    {
      source: "session",
      severity: "blocking",
      kind: "kb_lock_blocked_search_failed",
      summary: "知识库锁定检索失败。",
      detected_at: "2026-03-25T08:10:00Z",
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
      source: "session",
      severity: "warning",
      kind: "message_scores_missing",
      summary: "消息评分缺失。",
      detected_at: "2026-03-25T09:10:00Z",
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
      source: "session",
      severity: "blocking",
      kind: "stuck_scoring",
      summary: "评分卡住。",
      detected_at: "2026-03-25T09:20:00Z",
      session_id: "session-2",
      scenario_type: "sales",
      session_status: "scoring",
      report_status: "processing",
      diagnostics: {
        linked_asset_changes: [],
      },
    },
    {
      source: "system_log",
      severity: "warning",
      kind: "warning_without_session",
      summary: "没有会话的运行时告警。",
      detected_at: "2026-03-25T10:10:00Z",
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
  ] satisfies SupportRuntimeFaultItem[];

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
