import { GovernedBusinessRulePage } from "../_components/governed-business-rule-page";

export default function NextPracticeRecommendationsBusinessRulePage() {
    return (
        <GovernedBusinessRulePage
            configKey="recommendation.next_practice.ruleset"
            title="练后推荐规则"
            description="管理练后下一步推荐的维度、弱项阈值、CTA 文案和兜底推荐。预览只读，发布后才会影响运行时推荐服务。"
        />
    );
}
