"use client";

import { useParams } from "next/navigation";

import { ExaminerAgentSimulationPage } from "@/components/admin/curriculum-practice/examiner-agents/examiner-agent-form-page";

export default function SimulateExaminerAgentPage() {
    const params = useParams();
    return <ExaminerAgentSimulationPage agentId={params.id as string} />;
}
