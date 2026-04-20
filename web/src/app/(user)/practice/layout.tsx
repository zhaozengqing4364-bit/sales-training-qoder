import { LearnerHelpEntry } from "@/components/layout/learner-help-entry";

export default function PracticeLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <div className="relative flex flex-col h-screen w-full bg-slate-50 overflow-hidden">
            <div className="absolute right-4 top-4 z-20 w-[min(18rem,calc(100%-2rem))] sm:w-72">
                <LearnerHelpEntry />
            </div>

            {/* Immersive background or specific practice background can go here */}
            <div className="flex-1 w-full h-full">
                {children}
            </div>
        </div>
    );
}
