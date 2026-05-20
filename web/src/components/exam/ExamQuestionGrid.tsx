"use client";

import { cn } from "@/lib/utils";
import {
  examQuestionTypeLabel,
  type ExamQuestionType,
} from "@/lib/exam-question-type";

export interface ExamQuestionOutlineItem {
  question_index: number;
  question_id: string;
  title: string;
  question_type: ExamQuestionType;
}

interface ExamQuestionGridProps {
  items: ExamQuestionOutlineItem[];
  answeredIndices: number[];
  currentIndex: number;
  disabled?: boolean;
  onSelect: (questionIndex: number) => void;
  className?: string;
}

export function ExamQuestionGrid({
  items,
  answeredIndices,
  currentIndex,
  disabled = false,
  onSelect,
  className,
}: ExamQuestionGridProps) {
  const answeredSet = new Set(answeredIndices);

  return (
    <div className={cn("space-y-2", className)}>
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-medium text-slate-600">题目导航</p>
        <p className="text-xs tabular-nums text-slate-500">
          已答 {answeredIndices.length}/{items.length}
        </p>
      </div>
      <div
        className="grid grid-cols-5 gap-2 sm:grid-cols-8 lg:grid-cols-10"
        role="list"
        aria-label="题目导航"
      >
        {items.map((item) => {
          const isAnswered = answeredSet.has(item.question_index);
          const isCurrent = item.question_index === currentIndex;
          const typeLabel = examQuestionTypeLabel(item.question_type);

          return (
            <button
              key={item.question_id}
              type="button"
              role="listitem"
              disabled={disabled}
              aria-label={`第 ${item.question_index + 1} 题，${typeLabel}${isAnswered ? "，已作答" : ""}${isCurrent ? "，当前" : ""}`}
              aria-current={isCurrent ? "true" : undefined}
              onClick={() => onSelect(item.question_index)}
              className={cn(
                "flex flex-col items-center justify-center rounded-xl border px-1 py-2 text-center transition-all",
                "min-h-[3.25rem] focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500/60",
                isCurrent &&
                  "border-indigo-500 bg-indigo-50 shadow-sm ring-2 ring-indigo-400/40",
                !isCurrent &&
                  isAnswered &&
                  "border-emerald-200 bg-emerald-50/90 text-emerald-900",
                !isCurrent &&
                  !isAnswered &&
                  "border-slate-200/80 bg-white/40 text-slate-400 opacity-60 hover:opacity-90 hover:border-slate-300",
                disabled && "pointer-events-none opacity-50",
              )}
            >
              <span
                className={cn(
                  "text-sm font-bold tabular-nums leading-none",
                  isCurrent
                    ? "text-indigo-700"
                    : isAnswered
                      ? "text-emerald-800"
                      : "text-slate-500",
                )}
              >
                {item.question_index + 1}
              </span>
              <span
                className={cn(
                  "mt-1 text-[10px] leading-none font-medium",
                  isCurrent
                    ? "text-indigo-600"
                    : isAnswered
                      ? "text-emerald-700"
                      : "text-slate-400",
                )}
              >
                {typeLabel}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
