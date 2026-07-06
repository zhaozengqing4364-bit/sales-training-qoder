import type {
    NewcomerArticle,
    NewcomerExamPaper,
    NewcomerPathConfigResponse,
    NewcomerPathPublishPreviewResponse,
    NewcomerPathRevisionSummary,
    SalesTrainerAudioScorePrompt,
    SalesTrainerMaterial,
    SalesTrainerSettings,
    SalesTrainerUnit,
} from "@/lib/api/types";

export type NewcomerConfigModuleKey =
    | "ppt_explanation"
    | "business_skills"
    | "elevator_pitch"
    | "realtime_roleplay"
    | "realtime_roleplay_placeholder";

export type NewcomerConfigStatus = "ready" | "warning" | "missing" | "disabled";

export interface NewcomerConfigIssue {
    readonly code: string;
    readonly message: string;
    readonly href: string;
}

export interface NewcomerConfigModuleSummary {
    readonly moduleKey: NewcomerConfigModuleKey;
    readonly title: string;
    readonly orderLabel: string;
    readonly description: string;
    readonly status: NewcomerConfigStatus;
    readonly enabled: boolean;
    readonly canPublish: boolean;
    readonly unitIds: readonly string[];
    readonly bindings: readonly string[];
    readonly issues: readonly NewcomerConfigIssue[];
    readonly remediationHref: string;
    readonly learnerPreview: string;
}

export interface NewcomerOperationalCheck {
    readonly key: string;
    readonly label: string;
    readonly ok: boolean;
    readonly detail: string;
    readonly href: string;
}

export interface NewcomerConfigCenterSummary {
    readonly ready: boolean;
    readonly readyCount: number;
    readonly missingCount: number;
    readonly warningCount: number;
    readonly disabledCount: number;
}

export interface NewcomerConfigCenterGovernance {
    readonly source: "active_revision" | "legacy_migration_snapshot" | "legacy_units";
    readonly sourceLabel: string;
    readonly activeRevisionLabel: string;
    readonly workingRevisionLabel: string;
    readonly hasUnpublishedRevision: boolean;
    readonly revisionCount: number;
    readonly latestReason: string | null;
    readonly revisions: readonly NewcomerPathRevisionSummary[];
    readonly fallbackApplied: boolean;
    readonly fallbackReason: string | null;
    readonly publishPreview: NewcomerPathPublishPreviewResponse | null;
    readonly publishPreviewLoadError: string | null;
}

export interface NewcomerConfigCenterModel {
    readonly modules: readonly NewcomerConfigModuleSummary[];
    readonly operationalChecks: readonly NewcomerOperationalCheck[];
    readonly summary: NewcomerConfigCenterSummary;
    readonly governance: NewcomerConfigCenterGovernance;
}

export interface NewcomerConfigCenterInput {
    readonly units: readonly SalesTrainerUnit[];
    readonly articles: readonly NewcomerArticle[];
    readonly papers: readonly NewcomerExamPaper[];
    readonly materials: readonly SalesTrainerMaterial[];
    readonly scorePrompts: readonly SalesTrainerAudioScorePrompt[];
    readonly settings: SalesTrainerSettings | null;
    readonly boundArticle: NewcomerArticle | null;
    readonly boundArticleLoadError?: string | null;
    readonly pathConfig?: NewcomerPathConfigResponse | null;
    readonly pathRevisions?: readonly NewcomerPathRevisionSummary[];
    readonly publishPreview?: NewcomerPathPublishPreviewResponse | null;
    readonly publishPreviewLoadError?: string | null;
}

export interface ModuleDefinition {
    readonly moduleKey: NewcomerConfigModuleKey;
    readonly title: string;
    readonly orderLabel: string;
    readonly description: string;
    readonly remediationHref: string;
    readonly learnerPreview: string;
}
