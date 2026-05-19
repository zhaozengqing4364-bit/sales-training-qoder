"use client";

import { LearnerHelpEntry } from "@/components/layout/learner-help-entry";
import { cn } from "@/lib/utils";
import { usePathname } from "next/navigation";

export default function PracticeLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    const pathname = usePathname();
    const isScrollablePage = pathname?.endsWith("/report") || pathname?.endsWith("/replay");

    return (
        <div
            data-testid="practice-layout"
            className={cn(
                "relative flex flex-col w-full bg-slate-50",
                isScrollablePage ? "min-h-screen overflow-y-auto" : "h-screen overflow-hidden",
            )}
        >
            {!isScrollablePage && (
                <div className="absolute right-4 top-4 z-20 w-[min(18rem,calc(100%-2rem))] sm:w-72">
                    <LearnerHelpEntry />
                </div>
            )}

            {/* Immersive background or specific practice background can go here */}
            <div className={cn("flex-1 w-full", isScrollablePage ? "min-h-screen" : "h-full")}>
                {children}
            </div>
        </div>
    );
}
