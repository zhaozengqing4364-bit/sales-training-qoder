import { describe, expect, it } from "vitest";

import type { PracticeSessionRuntime } from "@/lib/api/types";

import { buildRuntimeLockState } from "./runtime-lock";

function createSessionRuntime(overrides: Partial<PracticeSessionRuntime> = {}): PracticeSessionRuntime {
    return {
        session_id: "session-1",
        status: "preparing",
        scenario_type: "sales",
        voice_mode: "legacy",
        start_time: "2026-03-14T08:00:00.000Z",
        ...overrides,
    };
}

describe("buildRuntimeLockState", () => {
    it("prefers persisted runtime config and rewrites mismatched query params", () => {
        const result = buildRuntimeLockState({
            sessionId: "session-1",
            session: createSessionRuntime({
                scenario_type: "presentation",
                voice_mode: "stepfun_realtime",
                agent_id: "agent-runtime",
                persona_id: "persona-runtime",
                presentation_id: "presentation-runtime",
                runtime_descriptor: {
                    subject: "training_scenario_runtime",
                    session_id: "session-1",
                    scenario_type: "presentation",
                    presentation_id: "presentation-runtime",
                    voice_mode: "stepfun_realtime",
                    runtime_profile_id: null,
                    focus_intent: {
                        version: "retry_focus_v1",
                        source_session_id: "session-source",
                        main_issue: {
                            issue_type: "value_unclear",
                            issue_text: "客户没有听懂收益点。",
                            recovery_rule: "先复述痛点，再给案例。",
                        },
                    },
                },
            }),
            query: {
                scenarioType: "sales",
                voiceMode: "legacy",
                agentId: "agent-entry",
                personaId: "persona-entry",
                presentationId: undefined,
            },
            searchParams: new URLSearchParams("scenario_type=sales&voice_mode=legacy&agent_id=agent-entry"),
        });

        expect(result.lockedScenarioType).toBe("presentation");
        expect(result.lockedVoiceMode).toBe("stepfun_realtime");
        expect(result.lockedAgentId).toBe("agent-runtime");
        expect(result.lockedPersonaId).toBe("persona-runtime");
        expect(result.lockedPresentationId).toBe("presentation-runtime");
        expect(result.focusIntent).toEqual({
            version: "retry_focus_v1",
            source_session_id: "session-source",
            main_issue: {
                issue_type: "value_unclear",
                issue_text: "客户没有听懂收益点。",
                recovery_rule: "先复述痛点，再给案例。",
            },
        });
        expect(result.rewriteHref).toBe(
            "/practice/session-1?scenario_type=presentation&voice_mode=stepfun_realtime&agent_id=agent-runtime&persona_id=persona-runtime&presentation_id=presentation-runtime",
        );
    });

    it("does not rewrite when persisted runtime already matches query", () => {
        const result = buildRuntimeLockState({
            sessionId: "session-2",
            session: createSessionRuntime({
                scenario_type: "sales",
                voice_mode: "legacy",
                agent_id: "agent-1",
            }),
            query: {
                scenarioType: "sales",
                voiceMode: "legacy",
                agentId: "agent-1",
                personaId: undefined,
                presentationId: undefined,
            },
            searchParams: new URLSearchParams("scenario_type=sales&voice_mode=legacy&agent_id=agent-1"),
        });

        expect(result.focusIntent).toBeNull();
        expect(result.rewriteHref).toBeNull();
    });
});
