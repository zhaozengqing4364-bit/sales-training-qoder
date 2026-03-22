"use client";

import * as React from "react";

import { api } from "@/lib/api/client";
import type { PracticeSessionRuntime } from "@/lib/api/types";
import { debug } from "@/lib/debug";

type ScenarioType = "sales" | "presentation";
type VoiceMode = "legacy" | "stepfun_realtime";

export interface PracticeRuntimeQueryState {
    scenarioType: ScenarioType;
    voiceMode: VoiceMode;
    agentId?: string;
    personaId?: string;
    presentationId?: string;
}

interface BuildRuntimeLockStateParams {
    sessionId: string;
    session: PracticeSessionRuntime;
    query: PracticeRuntimeQueryState;
    searchParams: URLSearchParams;
}

interface PracticeRuntimeLockState {
    lockedScenarioType: ScenarioType;
    lockedVoiceMode: VoiceMode;
    lockedAgentId?: string;
    lockedPersonaId?: string;
    lockedPresentationId?: string;
    rewriteHref: string | null;
}

export interface UsePracticeRuntimeLockParams {
    sessionId: string;
    query: PracticeRuntimeQueryState;
    searchParams: URLSearchParams;
    onRewriteQuery: (href: string) => void;
}

export interface UsePracticeRuntimeLockResult {
    lockedScenarioType: ScenarioType;
    lockedVoiceMode: VoiceMode;
    lockedAgentId?: string;
    lockedPersonaId?: string;
    lockedPresentationId?: string;
    sessionMetaError: string | null;
}

export function normalizeVoiceMode(value: string | null | undefined): VoiceMode {
    return value === "stepfun_realtime" ? "stepfun_realtime" : "legacy";
}

export function buildRuntimeLockState({
    sessionId,
    session,
    query,
    searchParams,
}: BuildRuntimeLockStateParams): PracticeRuntimeLockState {
    const lockedScenarioType = session.scenario_type || query.scenarioType;
    const lockedVoiceMode = normalizeVoiceMode(session.voice_mode || query.voiceMode);
    const lockedAgentId = session.agent_id || undefined;
    const lockedPersonaId = session.persona_id || undefined;
    const lockedPresentationId = session.presentation_id || query.presentationId;

    const shouldRewriteQuery =
        lockedScenarioType !== query.scenarioType
        || lockedVoiceMode !== query.voiceMode
        || (lockedAgentId || "") !== (query.agentId || "")
        || (lockedPersonaId || "") !== (query.personaId || "")
        || (lockedPresentationId || "") !== (query.presentationId || "");

    if (!shouldRewriteQuery) {
        return {
            lockedScenarioType,
            lockedVoiceMode,
            lockedAgentId,
            lockedPersonaId,
            lockedPresentationId,
            rewriteHref: null,
        };
    }

    searchParams.set("scenario_type", lockedScenarioType);
    searchParams.set("voice_mode", lockedVoiceMode);

    if (lockedAgentId) {
        searchParams.set("agent_id", lockedAgentId);
    } else {
        searchParams.delete("agent_id");
    }

    if (lockedPersonaId) {
        searchParams.set("persona_id", lockedPersonaId);
    } else {
        searchParams.delete("persona_id");
    }

    if (lockedPresentationId) {
        searchParams.set("presentation_id", lockedPresentationId);
    } else {
        searchParams.delete("presentation_id");
    }

    return {
        lockedScenarioType,
        lockedVoiceMode,
        lockedAgentId,
        lockedPersonaId,
        lockedPresentationId,
        rewriteHref: `/practice/${sessionId}?${searchParams.toString()}`,
    };
}

export function usePracticeRuntimeLock({
    sessionId,
    query,
    searchParams,
    onRewriteQuery,
}: UsePracticeRuntimeLockParams): UsePracticeRuntimeLockResult {
    const {
        scenarioType: queryScenarioType,
        voiceMode: queryVoiceMode,
        agentId: queryAgentId,
        personaId: queryPersonaId,
        presentationId: queryPresentationId,
    } = query;
    const searchParamsKey = searchParams.toString();
    const [state, setState] = React.useState<UsePracticeRuntimeLockResult>({
        lockedScenarioType: queryScenarioType,
        lockedVoiceMode: queryVoiceMode,
        lockedAgentId: queryAgentId,
        lockedPersonaId: queryPersonaId,
        lockedPresentationId: queryPresentationId,
        sessionMetaError: null,
    });

    React.useEffect(() => {
        let isCancelled = false;

        const syncSessionRuntimeLock = async () => {
            try {
                const session = await api.practice.getSession(sessionId);
                if (isCancelled) {
                    return;
                }

                const nextState = buildRuntimeLockState({
                    sessionId,
                    session,
                    query: {
                        scenarioType: queryScenarioType,
                        voiceMode: queryVoiceMode,
                        agentId: queryAgentId,
                        personaId: queryPersonaId,
                        presentationId: queryPresentationId,
                    },
                    searchParams: new URLSearchParams(searchParamsKey),
                });

                debug.log("[PracticeSession] Runtime lock synced", {
                    sessionId,
                    scenarioType: nextState.lockedScenarioType,
                    voiceMode: nextState.lockedVoiceMode,
                    agentId: nextState.lockedAgentId || null,
                    personaId: nextState.lockedPersonaId || null,
                    presentationId: nextState.lockedPresentationId || null,
                    shouldRewriteQuery: Boolean(nextState.rewriteHref),
                });

                setState({
                    lockedScenarioType: nextState.lockedScenarioType,
                    lockedVoiceMode: nextState.lockedVoiceMode,
                    lockedAgentId: nextState.lockedAgentId,
                    lockedPersonaId: nextState.lockedPersonaId,
                    lockedPresentationId: nextState.lockedPresentationId,
                    sessionMetaError: null,
                });

                if (nextState.rewriteHref) {
                    onRewriteQuery(nextState.rewriteHref);
                }
            } catch (error) {
                if (isCancelled) {
                    return;
                }

                debug.warn("[PracticeSession] Failed to sync runtime lock", {
                    sessionId,
                    error,
                });

                setState((current) => ({
                    ...current,
                    sessionMetaError: "会话配置加载失败，已使用入口参数尝试连接。",
                }));
            }
        };

        void syncSessionRuntimeLock();

        return () => {
            isCancelled = true;
        };
    }, [
        onRewriteQuery,
        queryAgentId,
        queryPersonaId,
        queryPresentationId,
        queryScenarioType,
        queryVoiceMode,
        searchParamsKey,
        sessionId,
    ]);

    return state;
}
