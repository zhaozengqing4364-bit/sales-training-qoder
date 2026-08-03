import { FoundationQuestionReviewWorkspace } from "@/components/admin/newcomer-training/question-review-workspace";
import { ADMIN_CONSOLE_ROLE_VALUES } from "@/lib/auth/current-user";
import { requireServerSession } from "@/lib/server-auth";

export default async function FoundationQuestionsPage() {
    await requireServerSession({ requiredRoles: [...ADMIN_CONSOLE_ROLE_VALUES], unauthorizedRedirectTo: "/" });
    return <FoundationQuestionReviewWorkspace />;
}
