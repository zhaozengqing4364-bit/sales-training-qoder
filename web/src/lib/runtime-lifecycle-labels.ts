import type { SessionRuntimeLifecycleState } from '@/lib/api/types';

const LABELS: Record<SessionRuntimeLifecycleState, string> = {
    draft: '草稿',
    validated: '已校验',
    runnable: '可连接',
    started: '进行中',
    completed: '已完成',
    failed: '不可运行',
};

export function formatRuntimeLifecycleState(
    state: SessionRuntimeLifecycleState | null | undefined,
): string | null {
    if (!state) return null;
    return LABELS[state] ?? state;
}
