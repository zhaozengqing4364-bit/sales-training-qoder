import { GovernedBusinessRulePage } from "../_components/governed-business-rule-page";

export default function AiCoachBusinessRulePage() {
    return (
        <GovernedBusinessRulePage
            configKey="growth.ai_coach.rules"
            title="AI 教练触达规则"
            description="管理 AI 教练主动触达阈值、维度映射和通知模板配置。页面不内置阈值或文案，所有规则由后端配置服务校验和发布。"
        />
    );
}
