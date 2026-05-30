import { describe, expect, it } from "vitest";

import type { AdminAiGovernanceExplainabilityResponse } from "@/lib/api/types";

import { extractRuntimeGovernanceArtifacts } from "./runtime-governance-artifacts";

describe("runtime-governance-artifacts", () => {
    it("extracts published_asset_refs and runtime dossier metadata from explainability payload", () => {
        const data = {
            session: {
                session_id: "ses-1",
                scenario_id: "scn-1",
                scenario_type: "sales",
                user_id: "usr-1",
                status: "completed",
                report_status: "completed",
                report_generated_at: "2026-05-27T10:00:00",
            },
            model: null,
            prompt: null,
            rag: null,
            knowledge: null,
            scoring: null,
            evidence: {
                input_reference: {},
                completeness: {},
                report_evidence: null,
            },
            evaluation: {
                run_id: "run-1",
                status: "succeeded",
                started_at: null,
                finished_at: null,
                input_evidence_reference: {},
                result_payload: {},
                result_summary: null,
                error_message: null,
                config_bundle_id: null,
                config_version_id: null,
                created_at: null,
                updated_at: null,
            },
            report: {
                payload: {
                    runtime_dossier: {
                        dossier_hash: "sha256:dossier",
                        asset_refs: [{ asset_type: "persona", asset_id: "persona-1" }],
                    },
                },
                lineage: {
                    snapshot_id: "snap-1",
                    evaluation_run_id: "run-1",
                    generated_at: "2026-05-27T10:00:00",
                    ruleset_source: "sales_ruleset",
                    ruleset_version: "2026.05",
                    score_basis: "persisted_snapshot",
                    non_evaluable_reason: null,
                    config_bundle_id: null,
                    config_version_id: null,
                    bundle_key: null,
                    source: null,
                    config_bundle_snapshot: {
                        published_asset_refs: {
                            persona_ref: {
                                asset_type: "persona",
                                asset_id: "persona-1",
                                version: "3",
                                content_hash: "sha256:persona",
                                snapshot_label: "published",
                            },
                        },
                    },
                    created_at: "2026-05-27T10:00:00",
                },
            },
        } satisfies AdminAiGovernanceExplainabilityResponse;

        const artifacts = extractRuntimeGovernanceArtifacts(data);

        expect(artifacts.publishedAssetRefs.persona_ref.asset_id).toBe("persona-1");
        expect(artifacts.runtimeDossier?.dossier_hash).toBe("sha256:dossier");
    });
});
