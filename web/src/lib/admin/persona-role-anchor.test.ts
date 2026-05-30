import { describe, expect, it } from "vitest";

import { ApiRequestError } from "@/lib/api/client";

import {
    buildRoleAnchorFormState,
    buildRoleAnchorPayload,
    mapPersonaPolicyValidationErrors,
    parsePersonaPolicyValidationErrors,
    previewRoleAnchorText,
} from "./persona-role-anchor";

describe("persona-role-anchor helpers", () => {
    it("builds form state from persona_policy.role_anchor", () => {
        const form = buildRoleAnchorFormState({
            role_anchor: {
                identity_template: "你是{role_name}，{relationship_stage}。{bottom_line}。",
                bottom_line: "你不认识对方，保持审慎距离。",
                must_do: "追问 ROI。",
                must_not: "主动让步。",
            },
        });

        expect(form.enabled).toBe(true);
        expect(form.bottomLine).toContain("审慎距离");
        expect(form.mustDo).toBe("追问 ROI。");
    });

    it("omits role_anchor payload when disabled", () => {
        expect(buildRoleAnchorPayload({
            enabled: false,
            identityTemplate: "",
            bottomLine: "",
            mustDo: "",
            mustNot: "",
        })).toBeUndefined();
    });

    it("maps backend validation errors to inline field keys", () => {
        const fieldErrors = mapPersonaPolicyValidationErrors([
            {
                field: "persona_policy.role_anchor.bottom_line",
                reason_code: "role_anchor_bottom_line_required",
                message: "bottom_line is required when role_anchor is configured.",
            },
        ]);

        expect(fieldErrors.bottomLine).toContain("role_anchor_bottom_line_required");
    });

    it("parses persona policy validation errors from ApiRequestError details", () => {
        const error = new ApiRequestError({
            status: 400,
            errorCode: "[PERSONA_POLICY_VALIDATION_FAILED]",
            message: "Persona policy validation failed",
            details: {
                error: "[PERSONA_POLICY_VALIDATION_FAILED]",
                errors: [
                    {
                        field: "persona_policy.role_anchor.identity_template",
                        reason_code: "role_anchor_identity_template_invalid_vars",
                        message: "identity_template contains unsupported placeholders.",
                    },
                ],
            },
        });

        expect(parsePersonaPolicyValidationErrors(error)).toEqual([
            {
                field: "persona_policy.role_anchor.identity_template",
                reason_code: "role_anchor_identity_template_invalid_vars",
                message: "identity_template contains unsupported placeholders.",
            },
        ]);
    });

    it("previews compiled role anchor text with placeholder substitution", () => {
        const preview = previewRoleAnchorText(
            {
                enabled: true,
                identityTemplate: "你是{role_name}，{relationship_stage}。{bottom_line}。",
                bottomLine: "你不认识对方，保持审慎距离。",
                mustDo: "追问 ROI。",
                mustNot: "主动让步。",
            },
            "制造业 CIO",
        );

        expect(preview).toContain("【角色锚】");
        expect(preview).toContain("制造业 CIO");
        expect(preview).toContain("这是你们首次正式见面");
        expect(preview).toContain("必须：追问 ROI。");
        expect(preview).toContain("禁止：主动让步。");
    });
});
