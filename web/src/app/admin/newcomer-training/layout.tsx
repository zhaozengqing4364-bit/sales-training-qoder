import type { ReactNode } from "react";

import { FoundationAdminWorkspaceNav } from "@/components/admin/newcomer-training/workspace-nav";

export default function NewcomerTrainingAdminLayout({ children }: { children: ReactNode }) {
    return (
        <div className="min-h-screen bg-slate-50">
            <div className="mx-auto max-w-[1600px] px-4 pt-4 md:px-6 md:pt-6">
                <FoundationAdminWorkspaceNav />
            </div>
            {children}
        </div>
    );
}
