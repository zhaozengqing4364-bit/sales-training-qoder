import { GovernedBusinessRulePage } from "../_components/governed-business-rule-page";

export default function SalesTrainerPhase2BusinessRulePage() {
    return (
        <GovernedBusinessRulePage
            configKey="sales_trainer.phase2.closed_loop_policy"
            title="销售训练阶段 2 闭环策略"
            description="管理弱项阈值、重复训练阈值、看板窗口、主管干预动作和补救入口。预览只读，发布后影响训练记录投影和管理者看板。"
        />
    );
}
