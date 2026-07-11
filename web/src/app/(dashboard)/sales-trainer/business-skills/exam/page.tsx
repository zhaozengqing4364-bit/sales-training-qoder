import { redirect } from "next/navigation";

/**
 * Compatibility entry for bookmarks created before quizzes moved into the
 * learning-topic workbench. The workbench owns reading, quiz, remediation,
 * and result state, so this route must not reconstruct the retired path module.
 */
export default function BusinessSkillsExamPage() {
    redirect("/sales-trainer/business-skills");
}
