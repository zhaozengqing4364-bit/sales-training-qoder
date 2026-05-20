export type ExamQuestionType =
  | "short_answer"
  | "single_choice"
  | "multiple_choice";

export function normalizeExamQuestionType(raw: string | undefined): ExamQuestionType {
  if (raw === "single_choice" || raw === "multiple_choice") {
    return raw;
  }
  return "short_answer";
}

export function examQuestionTypeLabel(type: ExamQuestionType): string {
  switch (type) {
    case "single_choice":
      return "单选";
    case "multiple_choice":
      return "多选";
    default:
      return "简答";
  }
}
