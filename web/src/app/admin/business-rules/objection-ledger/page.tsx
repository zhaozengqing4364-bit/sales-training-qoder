import { GovernedBusinessRulePage } from "../_components/governed-business-rule-page";

export default function ObjectionLedgerBusinessRulePage() {
    return (
        <GovernedBusinessRulePage
            configKey="sales.objection_ledger.ruleset"
            title="异议台账规则"
            description="管理异议识别、证据要求、压力词和合成维度配置。配置缺失、非法或停用时由后端规则服务统一兜底。"
        />
    );
}
