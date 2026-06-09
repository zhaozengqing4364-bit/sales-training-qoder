from __future__ import annotations

from typing import Literal

PracticeTemplateStatus = Literal["draft", "published", "archived"]
ExaminerAgentStatus = Literal["draft", "published", "archived"]
ContentAssetStatus = Literal["draft", "published", "archived"]
LearningContentStatus = Literal["draft", "published", "archived"]
CurriculumStageType = Literal["study", "exam", "practice", "report"]
QuestionDifficulty = Literal["easy", "medium", "hard"]
QuestionLifecycleStatus = Literal["draft", "published", "archived"]
TestBankImportStatus = Literal["pending", "processing", "completed", "failed"]
RoleProfilePressureLevel = Literal["low", "medium", "high"]
PracticeTemplateScenarioType = Literal["sales", "presentation"]
PracticeTemplateVoiceMode = Literal["legacy", "stepfun_realtime"]
LearnerLevel = Literal["conservative", "beginner", "intermediate", "advanced"]
PracticeTemplateMode = Literal[
    "learning",
    "expert_qa",
    "examiner",
    "customer_roleplay",
    "mixed_path",
]
GateStatus = Literal["passed", "failed", "warning"]
RuntimeDossierStatus = Literal["passed", "failed", "warning"]
