import type { SupportRuntimeFaultItem } from "@/lib/api/types";

import {
  extractLinkedAssetChanges,
  type LinkedAssetChange,
} from "@/lib/admin/linked-assets";

export interface LinkedRuntimeFaultEntry {
  fault: SupportRuntimeFaultItem;
  assetChanges: LinkedAssetChange[];
}

export function buildLinkedRuntimeFaultEntries(
  runtimeFaults: SupportRuntimeFaultItem[] | null | undefined,
  options?: { limit?: number },
): LinkedRuntimeFaultEntry[] {
  const entries = (runtimeFaults || [])
    .map((fault) => ({
      fault,
      assetChanges: extractLinkedAssetChanges(fault),
    }))
    .filter((entry) => entry.assetChanges.length > 0);

  if (typeof options?.limit === "number") {
    return entries.slice(0, options.limit);
  }

  return entries;
}

export function buildRuntimeFaultBySessionId(
  runtimeFaults: SupportRuntimeFaultItem[] | null | undefined,
): Map<string, LinkedRuntimeFaultEntry> {
  const lookup = new Map<string, LinkedRuntimeFaultEntry>();

  (runtimeFaults || []).forEach((fault) => {
    if (!fault.session_id || lookup.has(fault.session_id)) {
      return;
    }

    const assetChanges = extractLinkedAssetChanges(fault);
    if (!assetChanges.length) {
      return;
    }

    lookup.set(fault.session_id, { fault, assetChanges });
  });

  return lookup;
}
