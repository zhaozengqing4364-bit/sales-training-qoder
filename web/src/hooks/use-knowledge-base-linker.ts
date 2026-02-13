"use client";

import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api/client";
import type { AdminKnowledgeBase } from "@/lib/api/types";

interface UseKnowledgeBaseLinkerReturn {
    linkedKBs: AdminKnowledgeBase[];
    availableKBs: AdminKnowledgeBase[];
    selectedIds: string[];
    toggleKnowledgeBase: (kbId: string) => void;
    setSelectedIds: (ids: string[]) => void;
    isLoading: boolean;
    error: string | null;
}

export function useKnowledgeBaseLinker(agentId: string): UseKnowledgeBaseLinkerReturn {
    const [linkedKBs, setLinkedKBs] = useState<AdminKnowledgeBase[]>([]);
    const [availableKBs, setAvailableKBs] = useState<AdminKnowledgeBase[]>([]);
    const [selectedIds, setSelectedIds] = useState<string[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const loadKnowledgeBases = async () => {
            if (!agentId) return;

            setIsLoading(true);
            setError(null);

            try {
                const [allKBsResponse, agentData] = await Promise.all([
                    api.admin.getKnowledgeBases({ page_size: 100 }),
                    api.admin.getAgent(agentId),
                ]);

                const allKBs = allKBsResponse.items || [];
                const linkedIds = agentData.default_knowledge_base_ids || [];

                setAvailableKBs(allKBs);
                setSelectedIds(linkedIds);

                const linked = allKBs.filter((kb) => linkedIds.includes(kb.id));
                setLinkedKBs(linked);
            } catch (err) {
                setError(err instanceof Error ? err.message : "加载知识库失败");
            } finally {
                setIsLoading(false);
            }
        };

        loadKnowledgeBases();
    }, [agentId]);

    const toggleKnowledgeBase = useCallback((kbId: string) => {
        setSelectedIds((prev) => {
            if (prev.includes(kbId)) {
                return prev.filter((id) => id !== kbId);
            } else {
                return [...prev, kbId];
            }
        });
    }, []);

    return {
        linkedKBs,
        availableKBs,
        selectedIds,
        toggleKnowledgeBase,
        setSelectedIds,
        isLoading,
        error,
    };
}
