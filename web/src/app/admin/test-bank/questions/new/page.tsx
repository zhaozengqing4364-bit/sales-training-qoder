"use client";
import { useRouter } from "next/navigation";
import { AdminFormShell } from "@/components/admin/admin-layout-shells";
import { TestBankQuestionForm } from "@/components/admin/test-bank/test-bank-question-form";
export default function NewTestBankQuestionPage() {
    const router = useRouter();
    return (
        <AdminFormShell backHref="/admin/test-bank" title="新建题目" description="创建草稿题目后可返回列表发布。">
            <TestBankQuestionForm mode="create" onSaved={() => router.push("/admin/test-bank")} onCancel={() => router.push("/admin/test-bank")} />
        </AdminFormShell>
    );
}
