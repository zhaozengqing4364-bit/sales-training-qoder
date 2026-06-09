import { ApiRequestError, api } from "@/lib/api/client";
import type {
    LearningContent,
    NewcomerArticle,
    NewcomerExamPaper,
    NewcomerPathConfigResponse,
    NewcomerPathRevisionSummary,
    SalesTrainerAudioScorePrompt,
    SalesTrainerMaterial,
    SalesTrainerSettings,
    SalesTrainerUnit,
} from "@/lib/api/types";

const BUSINESS_SKILLS_MODULE_KEY = "business_skills";

export type ConfigCenterData = {
    readonly articles: readonly NewcomerArticle[];
    readonly boundArticle: NewcomerArticle | null;
    readonly materials: readonly SalesTrainerMaterial[];
    readonly papers: readonly NewcomerExamPaper[];
    readonly pathConfig: NewcomerPathConfigResponse | null;
    readonly pathRevisions: readonly NewcomerPathRevisionSummary[];
    readonly scorePrompts: readonly SalesTrainerAudioScorePrompt[];
    readonly settings: SalesTrainerSettings | null;
    readonly units: readonly SalesTrainerUnit[];
};

export async function loadConfigCenterData(): Promise<ConfigCenterData> {
    const [
        units,
        contents,
        boundArticle,
        pathConfig,
        pathRevisions,
        papers,
        materials,
        scorePrompts,
        settings,
    ] = await Promise.all([
        api.admin.salesTrainer.listUnits({ include_archived: true, limit: 200 }),
        api.learningContents.list(),
        loadBoundArticle(),
        api.admin.newcomerTraining.getPathConfig(),
        api.admin.newcomerTraining.listPathConfigRevisions(),
        api.admin.newcomerTraining.listPapers({ include_archived: true, limit: 100 }),
        api.admin.salesTrainer.listMaterials({ include_archived: true, limit: 100 }),
        api.admin.salesTrainer.listScorePrompts({ include_archived: true }),
        api.admin.salesTrainer.getSettings(),
    ]);
    return {
        articles: contents.items.map(articleFromContent),
        boundArticle,
        materials: materials.items,
        papers: papers.items,
        pathConfig,
        pathRevisions: pathRevisions.items,
        scorePrompts: scorePrompts.items,
        settings,
        units: units.items,
    };
}

function articleFromContent(content: LearningContent): NewcomerArticle {
    return {
        module_key: BUSINESS_SKILLS_MODULE_KEY,
        learning_content_id: content.learning_content_id,
        title: content.title,
        summary: content.summary ?? null,
        owner: content.owner ?? null,
        source: content.source ?? null,
        chapters: content.chapters.map((chapter) => ({
            chapter_id: chapter.chapter_id,
            title: chapter.title,
            content: chapter.content,
            order_index: chapter.order_index,
        })),
    };
}

async function loadBoundArticle(): Promise<NewcomerArticle | null> {
    try {
        return await api.newcomerTraining.getModuleArticle(BUSINESS_SKILLS_MODULE_KEY);
    } catch (error) {
        if (error instanceof ApiRequestError && error.status === 404) {
            return null;
        }
        if (error instanceof Error) {
            return null;
        }
        throw error;
    }
}
