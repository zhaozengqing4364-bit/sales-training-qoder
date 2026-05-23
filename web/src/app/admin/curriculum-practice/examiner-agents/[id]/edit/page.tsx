"use client";

import { useParams } from "next/navigation";

import { ExaminerAgentFormPage } from "@/components/admin/curriculum-practice/examiner-agents/examiner-agent-form-page";

export default function EditExaminerAgentPage() {
    const params = useParams();
    return <ExaminerAgentFormPage mode="edit" agentId={params.id as string} />;
}
