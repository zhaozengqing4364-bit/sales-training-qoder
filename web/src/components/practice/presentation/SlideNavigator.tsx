"use client";

import React from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

export interface SlideNavigatorProps {
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  disabled?: boolean;
}

export function SlideNavigator({
  currentPage,
  totalPages,
  onPageChange,
  disabled = false,
}: SlideNavigatorProps) {
  const canGoPrevious = currentPage > 1 && !disabled;
  const canGoNext = currentPage < totalPages && !disabled;

  const handlePrevious = () => {
    if (canGoPrevious) {
      onPageChange(currentPage - 1);
    }
  };

  const handleNext = () => {
    if (canGoNext) {
      onPageChange(currentPage + 1);
    }
  };

  return (
    <div className="flex items-center gap-4 bg-white rounded-full px-4 py-2 shadow-sm border border-stone-200">
      <button
        onClick={handlePrevious}
        disabled={!canGoPrevious}
        className={cn(
          "p-2 rounded-full transition-colors",
          canGoPrevious
            ? "hover:bg-stone-100 text-stone-700"
            : "text-stone-300 cursor-not-allowed"
        )}
        aria-label="上一页"
      >
        <ChevronLeft className="w-5 h-5" />
      </button>

      <div className="flex items-center gap-1 min-w-[80px] justify-center">
        <span className="text-lg font-semibold text-stone-900">{currentPage}</span>
        <span className="text-stone-400">/</span>
        <span className="text-sm text-stone-500">{totalPages}</span>
      </div>

      <button
        onClick={handleNext}
        disabled={!canGoNext}
        className={cn(
          "p-2 rounded-full transition-colors",
          canGoNext
            ? "hover:bg-stone-100 text-stone-700"
            : "text-stone-300 cursor-not-allowed"
        )}
        aria-label="下一页"
      >
        <ChevronRight className="w-5 h-5" />
      </button>
    </div>
  );
}
