"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { api, getApiErrorMessage } from "@/lib/api/client";
import { buildNewcomerConfigCenter } from "@/lib/sales-trainer/config-center";
import {
    type PathAudioBindingValue,
    type PathBusinessBindingValue,
    updatePathAudioBinding,
    updatePathBusinessBinding,
} from "@/lib/sales-trainer/path-config-editing";

import {
    loadConfigCenterData,
    type ConfigCenterData,
} from "./page-data";

export function usePathConfigCenterWorkflow(options: { enabled?: boolean } = {}) {
    const { enabled = true } = options;
    const [data, setData] = useState<ConfigCenterData | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [isMutating, setIsMutating] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [actionMessage, setActionMessage] = useState<string | null>(null);
    const [changeReason, setChangeReason] = useState("");

    const load = useCallback(async () => {
        setIsLoading(true);
        setError(null);
        try {
            setData(await loadConfigCenterData());
        } catch (loadError) {
            setData(null);
            setError(getApiErrorMessage(loadError));
        } finally {
            setIsLoading(false);
        }
    }, []);

    useEffect(() => {
        if (!enabled) {
            setIsLoading(false);
            setData(null);
            setError(null);
            return;
        }
        let isActive = true;

        void loadConfigCenterData()
            .then((nextData) => {
                if (!isActive) {
                    return;
                }
                setData(nextData);
                setError(null);
            })
            .catch((loadError) => {
                if (!isActive) {
                    return;
                }
                setData(null);
                setError(getApiErrorMessage(loadError));
            })
            .finally(() => {
                if (isActive) {
                    setIsLoading(false);
                }
            });

        return () => {
            isActive = false;
        };
    }, [enabled]);

    const updateAudioBinding = useCallback((
        moduleKey: "ppt_explanation" | "elevator_pitch",
        value: PathAudioBindingValue,
    ) => {
        setData((current) => {
            if (!current?.pathConfig) {
                return current;
            }
            return {
                ...current,
                pathConfig: {
                    ...current.pathConfig,
                    path: updatePathAudioBinding(current.pathConfig.path, moduleKey, value),
                },
            };
        });
    }, []);

    const updateBusinessBinding = useCallback((value: PathBusinessBindingValue) => {
        setData((current) => {
            if (!current?.pathConfig) {
                return current;
            }
            return {
                ...current,
                pathConfig: {
                    ...current.pathConfig,
                    path: updatePathBusinessBinding(current.pathConfig.path, value),
                },
            };
        });
    }, []);

    const saveCurrentRevision = useCallback(async () => {
        if (!data?.pathConfig) {
            setError("路径配置尚未加载完成。");
            return;
        }
        const reason = changeReason.trim();
        if (!reason) {
            setError("请先填写本次变更说明。");
            return;
        }
        setIsMutating(true);
        setError(null);
        setActionMessage(null);
        try {
            await api.admin.newcomerTraining.savePathConfig({
                ...data.pathConfig.path,
                reason,
            });
            setActionMessage("已保存为待发布修订，发布后只影响后续学员。");
            await load();
        } catch (saveError) {
            setError(getApiErrorMessage(saveError));
        } finally {
            setIsMutating(false);
        }
    }, [changeReason, data, load]);

    const publishWorkingRevision = useCallback(async () => {
        const reason = changeReason.trim();
        if (!reason) {
            setError("请先填写本次变更说明。");
            return;
        }
        setIsMutating(true);
        setError(null);
        setActionMessage(null);
        try {
            await api.admin.newcomerTraining.publishPathConfig({
                reason,
            });
            setChangeReason("");
            setActionMessage("路径配置已发布生效；历史学员记录不会被改写。");
            await load();
        } catch (publishError) {
            setError(getApiErrorMessage(publishError));
        } finally {
            setIsMutating(false);
        }
    }, [changeReason, load]);

    const rollbackRevision = useCallback(async (revisionId: string, reason: string) => {
        setIsMutating(true);
        setError(null);
        setActionMessage(null);
        try {
            await api.admin.newcomerTraining.rollbackPathConfig({
                revision_id: revisionId,
                reason,
            });
            setActionMessage("路径配置已回滚；回滚只影响后续学员。");
            await load();
        } catch (rollbackError) {
            setError(getApiErrorMessage(rollbackError));
        } finally {
            setIsMutating(false);
        }
    }, [load]);

    const model = useMemo(
        () => data ? buildNewcomerConfigCenter(data) : null,
        [data],
    );

    return {
        actionMessage,
        changeReason,
        data,
        error,
        isLoading,
        isMutating,
        load,
        model,
        publishWorkingRevision,
        rollbackRevision,
        saveCurrentRevision,
        setChangeReason,
        updateAudioBinding,
        updateBusinessBinding,
    };
}
