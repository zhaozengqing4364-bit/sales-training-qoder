import { describe, expect, it } from "vitest";

import {
  buildAdminUserDrillInHref,
  getDefaultAdminUserFocusNote,
  readAdminUserDrillInContext,
  type AdminUserDrillInBucket,
} from "./drill-in";

function searchParamsFromHref(href: string): URLSearchParams {
  return new URL(href, "https://example.com").searchParams;
}

describe("admin drill-in helpers", () => {
  it("builds the current not-passed drill-in URL with the shared default note", () => {
    expect(
      buildAdminUserDrillInHref({
        kind: "not_passed",
        userId: "user-1",
        issueFamily: "value_expression",
      }),
    ).toBe(
      "/admin/users/user-1?focusBucket=not_passed&focusIssueFamily=value_expression&focusNote=%E5%85%88%E5%AF%B9%E7%85%A7%E6%9C%80%E8%BF%91%E7%BB%9F%E4%B8%80%E6%8A%A5%E5%91%8A%E6%8A%8A%E4%BB%B7%E5%80%BC%E8%A1%A8%E8%BE%BE%E8%AF%B4%E5%85%B7%E4%BD%93%E3%80%82",
    );
  });

  it("falls back to the shared evidence-gap note when issue family is missing", () => {
    expect(getDefaultAdminUserFocusNote()).toBe("先对照最近统一报告补证据。");
    expect(
      buildAdminUserDrillInHref({
        kind: "not_passed",
        userId: "user-2",
      }),
    ).toBe(
      "/admin/users/user-2?focusBucket=not_passed&focusIssueFamily=evidence_gap&focusNote=%E5%85%88%E5%AF%B9%E7%85%A7%E6%9C%80%E8%BF%91%E7%BB%9F%E4%B8%80%E6%8A%A5%E5%91%8A%E8%A1%A5%E8%AF%81%E6%8D%AE%E3%80%82",
    );
  });

  it.each<[AdminUserDrillInBucket, string]>([
    ["inactive_streak", "/admin/users/user-3?focusBucket=inactive_streak"],
    ["improving", "/admin/users/user-3?focusBucket=improving"],
  ])("keeps %s drill-ins on the current route family", (kind, expectedHref) => {
    expect(
      buildAdminUserDrillInHref({
        kind,
        userId: "user-3",
      }),
    ).toBe(expectedHref);
  });

  it("parses the shipped not-passed drill-in contract into banner and prefill state", () => {
    const context = readAdminUserDrillInContext(
      searchParamsFromHref(
        buildAdminUserDrillInHref({
          kind: "not_passed",
          userId: "user-4",
          issueFamily: "objection_response",
        }),
      ),
    );

    expect(context).toEqual({
      focusBucket: "not_passed",
      focusIssueFamily: "objection_response",
      focusNote: "先对照最近统一报告把异议回应说完整。",
      banner: {
        badge: "本周风险成员",
        description: "当前这条 drill-in 仍落在「异议回应」这个问题家族。",
        issueFamilyLabel: "异议回应",
      },
    });
  });

  it("keeps direct issue-family prefills even when the drill-in bucket is absent", () => {
    expect(
      readAdminUserDrillInContext(new URLSearchParams("focusIssueFamily=evidence_gap&focusNote=%E5%85%88%E8%A1%A5%E8%AF%81%E6%8D%AE%E3%80%82")),
    ).toEqual({
      focusBucket: null,
      focusIssueFamily: "evidence_gap",
      focusNote: "先补证据。",
      banner: null,
    });
  });
});
