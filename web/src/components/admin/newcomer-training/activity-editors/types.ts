import type { ActivityConfig } from "@/lib/api/types/newcomer-training";

export interface ResourceOption {
    id: string;
    title: string;
    status: string;
}

export interface ActivityEditorResources {
    learning_contents: ResourceOption[];
    exam_papers: ResourceOption[];
    scoring_rubrics: ResourceOption[];
    materials: ResourceOption[];
    practice_templates: ResourceOption[];
    runtime_profiles: ResourceOption[];
    coach_profiles: ResourceOption[];
}

export type QuickCreateKind = "learning_content" | "exam_paper" | "material" | "scoring_rubric";

export interface ActivityEditorProps<T extends ActivityConfig> {
    value: T;
    disabled?: boolean;
    resources: ActivityEditorResources;
    onChange: (value: T) => void;
    onQuickCreate?: (kind: QuickCreateKind) => void;
}
