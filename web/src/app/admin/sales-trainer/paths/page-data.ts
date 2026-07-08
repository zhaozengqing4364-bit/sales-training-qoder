import { api, getApiErrorMessage } from "@/lib/api/client";
import type {
    LearningContent,
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

const BUSINESS_SKILLS_MODULE_KEY = "business_skills";

export type ConfigCenterData = {
    readonly articles: readonly NewcomerArticle[];
    readonly boundArticle: NewcomerArticle | null;
    readonly boundArticleLoadError: string | null;
    readonly materials: readonly SalesTrainerMaterial[];
    readonly papers: readonly NewcomerExamPaper[];
    readonly pathConfig: NewcomerPathConfigResponse | null;
    readonly pathRevisions: readonly NewcomerPathRevisionSummary[];
    readonly publishPreview: NewcomerPathPublishPreviewResponse | null;
    readonly publishPreviewLoadError: string | null;
    readonly scorePrompts: readonly SalesTrainerAudioScorePrompt[];
    readonly settings: SalesTrainerSettings | null;
    readonly units: readonly SalesTrainerUnit[];
};

export async function loadConfigCenterData(): Promise<ConfigCenterData> {
    const [
        units,
        contents,
        pathConfig,
        pathRevisions,
        papers,
        materials,
        scorePrompts,
        settings,
    ] = await Promise.all([
        api.admin.salesTrainer.listUnits({ include_archived: true, limit: 200 }),
        api.learningContents.list(),
        api.admin.newcomerTraining.getPathConfig(),
        api.admin.newcomerTraining.listPathConfigRevisions(),
        api.admin.newcomerTraining.listPapers({ include_archived: true, limit: 100 }),
        api.admin.salesTrainer.listMaterials({ include_archived: true, limit: 100 }),
        api.admin.salesTrainer.listScorePrompts({ include_archived: true }),
        api.admin.salesTrainer.getSettings(),
    ]);
    const publishPreviewResult = pathConfig.has_unpublished_revision
        ? await loadPublishPreview()
        : { preview: null, error: null };
    return {
        articles: contents.items.map(articleFromContent),
        boundArticle: boundArticleFromPathConfig(pathConfig, contents.items),
        boundArticleLoadError: boundArticleLoadErrorFromPathConfig(pathConfig, contents.items),
        materials: materials.items,
        papers: papers.items,
        pathConfig,
        pathRevisions: pathRevisions.items,
        publishPreview: publishPreviewResult.preview,
        publishPreviewLoadError: publishPreviewResult.error,
        scorePrompts: scorePrompts.items,
        settings,
        units: units.items,
    };
}

async function loadPublishPreview(): Promise<{
    readonly preview: NewcomerPathPublishPreviewResponse | null;
    readonly error: string | null;
}> {
    try {
        return {
            preview: await api.admin.newcomerTraining.previewPathConfigPublish(),
            error: null,
        };
    } catch (error) {
        return {
            preview: null,
            error: getApiErrorMessage(error),
        };
    }
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

function boundArticleIdFromPathConfig(pathConfig: NewcomerPathConfigResponse): string | null {
    return pathConfig.path.modules.find(
        (module) => module.module_key === BUSINESS_SKILLS_MODULE_KEY,
    )?.learning_content_id ?? null;
}

function boundArticleFromPathConfig(
    pathConfig: NewcomerPathConfigResponse,
    contents: readonly LearningContent[],
): NewcomerArticle | null {
    const boundArticleId = boundArticleIdFromPathConfig(pathConfig);
    if (!boundArticleId) {
        return null;
    }
    const content = contents.find((item) => item.learning_content_id === boundArticleId);
    return content ? articleFromContent(content) : null;
}

function boundArticleLoadErrorFromPathConfig(
    pathConfig: NewcomerPathConfigResponse,
    contents: readonly LearningContent[],
): string | null {
    const boundArticleId = boundArticleIdFromPathConfig(pathConfig);
    if (!boundArticleId) {
        return null;
    }
    if (contents.some((item) => item.learning_content_id === boundArticleId)) {
        return null;
    }
    return `当前路径配置绑定的学习专题内容不在内容列表中：${boundArticleId}`;
}
