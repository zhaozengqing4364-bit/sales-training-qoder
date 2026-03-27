import { formatIssueTypeLabel } from "@/lib/session-evidence";

export type AdminUserDrillInBucket = "not_passed" | "inactive_streak" | "improving";

export interface BuildAdminUserDrillInHrefArgs {
  kind: AdminUserDrillInBucket;
  userId: string;
  issueFamily?: string | null;
  note?: string | null;
}

export interface AdminUserDrillInBannerContext {
  badge: string;
  description: string;
  issueFamilyLabel?: string | null;
}

export interface AdminUserDrillInContext {
  focusBucket: AdminUserDrillInBucket | null;
  focusIssueFamily: string | null;
  focusNote: string | null;
  banner: AdminUserDrillInBannerContext | null;
}

type SearchParamsReader = {
  get(name: string): string | null;
};

const DEFAULT_NOT_PASSED_NOTE_BY_ISSUE_FAMILY: Record<string, string> = {
  value_expression: "先对照最近统一报告把价值表达说具体。",
  objection_response: "先对照最近统一报告把异议回应说完整。",
  structure_gap: "先对照最近统一报告把结构步骤说完整。",
  evidence_gap: "先对照最近统一报告补证据。",
};

function isAdminUserDrillInBucket(value: string | null): value is AdminUserDrillInBucket {
  return value === "not_passed" || value === "inactive_streak" || value === "improving";
}

function toOptionalSearchParam(value: string | null): string | null {
  const trimmed = value?.trim();
  return trimmed ? trimmed : null;
}

export function getDefaultAdminUserFocusNote(issueFamily?: string | null): string {
  return (
    DEFAULT_NOT_PASSED_NOTE_BY_ISSUE_FAMILY[issueFamily || ""]
    || DEFAULT_NOT_PASSED_NOTE_BY_ISSUE_FAMILY.evidence_gap
  );
}

export function buildAdminUserDrillInHref({
  kind,
  userId,
  issueFamily,
  note,
}: BuildAdminUserDrillInHrefArgs): string {
  const searchParams = new URLSearchParams({ focusBucket: kind });

  if (kind === "not_passed") {
    searchParams.set("focusIssueFamily", issueFamily || "evidence_gap");
    searchParams.set("focusNote", note || getDefaultAdminUserFocusNote(issueFamily));
  }

  return `/admin/users/${userId}?${searchParams.toString()}`;
}

export function readAdminUserDrillInContext(searchParams: SearchParamsReader): AdminUserDrillInContext {
  const focusBucket = isAdminUserDrillInBucket(searchParams.get("focusBucket"))
    ? searchParams.get("focusBucket")
    : null;
  const focusIssueFamily = toOptionalSearchParam(searchParams.get("focusIssueFamily"));
  const focusNote = toOptionalSearchParam(searchParams.get("focusNote"));

  if (!focusBucket) {
    return {
      focusBucket: null,
      focusIssueFamily,
      focusNote,
      banner: null,
    };
  }

  const issueFamilyLabel = formatIssueTypeLabel(focusIssueFamily) || focusIssueFamily;

  if (focusBucket === "not_passed") {
    const resolvedFocusNote = focusNote || (focusIssueFamily
      ? getDefaultAdminUserFocusNote(focusIssueFamily)
      : null);

    return {
      focusBucket,
      focusIssueFamily,
      focusNote: resolvedFocusNote,
      banner: {
        badge: "本周风险成员",
        description: issueFamilyLabel
          ? `当前这条 drill-in 仍落在「${issueFamilyLabel}」这个问题家族。`
          : "当前这条 drill-in 来自本周风险名单，建议先对照最近统一报告再决定主管动作。",
        issueFamilyLabel,
      },
    };
  }

  if (focusBucket === "inactive_streak") {
    return {
      focusBucket,
      focusIssueFamily,
      focusNote,
      banner: {
        badge: "本周连续未练",
        description: "当前这位成员来自本周连续未练名单，先确认节奏恢复，再决定是否补主管重点。",
      },
    };
  }

  return {
    focusBucket,
    focusIssueFamily,
    focusNote,
    banner: {
      badge: "本周显著回升",
      description: "当前这位成员来自本周显著回升名单，适合复盘最近有效动作并固化下一轮训练。",
    },
  };
}
