"use client";

import { cn } from "@/lib/utils";
import {
  examQuestionTypeLabel,
  type ExamQuestionType,
} from "@/lib/exam-question-type";
import type { ExamQuestionOutlineItem } from "./ExamQuestionGrid";

const TYPE_SECTION_ORDER: ExamQuestionType[] = [
  "single_choice",
  "multiple_choice",
  "short_answer",
];

interface ExamQuestionNavGroupedProps {
  items: ExamQuestionOutlineItem[];
  answeredIndices: number[];
  currentIndex: number;
  disabled?: boolean;
  onSelect: (questionIndex: number) => void;
  className?: string;
}

function groupByType(
  items: ExamQuestionOutlineItem[],
): Map<ExamQuestionType, ExamQuestionOutlineItem[]> {
  const groups = new Map<ExamQuestionType, ExamQuestionOutlineItem[]>();
  for (const type of TYPE_SECTION_ORDER) {
    groups.set(type, []);
  }
  for (const item of items) {
    const list = groups.get(item.question_type) ?? [];
    list.push(item);
    groups.set(item.question_type, list);
  }
  for (const [, list] of groups) {
    list.sort((a, b) => a.question_index - b.question_index);
  }
  return groups;
}

export function ExamQuestionNavGrouped({
  items,
  answeredIndices,
  currentIndex,
  disabled = false,
  onSelect,
  className,
}: ExamQuestionNavGroupedProps) {
  const answeredSet = new Set(answeredIndices);
  const groups = groupByType(items);
  const visibleSections = TYPE_SECTION_ORDER.filter(
    (type) => (groups.get(type)?.length ?? 0) > 0,
  );

  return (
    <div className={cn("space-y-4", className)}>
      {visibleSections.map((type, sectionIndex) => {
        const sectionItems = groups.get(type) ?? [];
        const sectionLabel = examQuestionTypeLabel(type);

        return (
          <section
            key={type}
            className={cn(sectionIndex > 0 && "pt-1 border-t border-slate-200/60")}
            aria-label={`${sectionLabel}题目`}
          >
            <div
              className="grid grid-cols-5 gap-2"
              role="list"
            >
              {sectionItems.map((item) => {
                const isAnswered = answeredSet.has(item.question_index);
                const isCurrent = item.question_index === currentIndex;

                return (
                  <button
                    key={item.question_id}
                    type="button"
                    role="listitem"
                    disabled={disabled}
                    aria-label={`第 ${item.question_index + 1} 题${isAnswered ? "，已作答" : ""}${isCurrent ? "，当前" : ""}`}
                    aria-current={isCurrent ? "true" : undefined}
                    onClick={() => onSelect(item.question_index)}
                    className={cn(
                      "flex aspect-square items-center justify-center rounded-xl border text-sm font-bold tabular-nums transition-all",
                      "focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500/60",
                      isAnswered &&
                        "border-indigo-500 bg-indigo-600 text-white shadow-sm",
                      !isAnswered &&
                        "border-slate-200/80 bg-slate-100/80 text-slate-400 hover:border-slate-300 hover:text-slate-600",
                      isCurrent &&
                        !isAnswered &&
                        "ring-2 ring-indigo-400/50 ring-offset-1",
                      isCurrent &&
                        isAnswered &&
                        "ring-2 ring-indigo-300 ring-offset-1",
                      disabled && "pointer-events-none opacity-50",
                    )}
                  >
                    {item.question_index + 1}
                  </button>
                );
              })}
            </div>
          </section>
        );
      })}
    </div>
  );
}
