import { GovernedBusinessRulePage } from "../_components/governed-business-rule-page";

export default function GrowthAchievementsBusinessRulePage() {
    return (
        <GovernedBusinessRulePage
            configKey="growth.achievement.rules"
            title="成就徽章规则"
            description="管理成就解锁规则的草稿、校验、预览、发布、回滚与审计。规则默认值、校验范围和兜底策略来自后端业务规则定义。"
        />
    );
}
