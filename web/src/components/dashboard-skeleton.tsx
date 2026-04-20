import { Skeleton } from "@/components/ui/skeleton";

export function DashboardSkeleton() {
    return (
        <div className="space-y-12 pb-20">
            {/* Header Skeleton */}
            <div className="flex flex-col gap-4 px-2 md:flex-row md:items-end md:justify-between">
                <div className="space-y-3">
                    <Skeleton className="h-6 w-32 rounded-full" />
                    <Skeleton className="h-10 w-64 max-w-full rounded-lg" />
                    <Skeleton className="h-6 w-48 max-w-full rounded-lg" />
                </div>
                <Skeleton className="h-14 w-40 rounded-full" />
            </div>

            {/* Bento Grid Skeleton */}
            <div className="grid min-h-[320px] grid-cols-1 gap-6 md:grid-cols-12 md:min-h-[500px]">
                {/* Large Card */}
                <div className="col-span-1 h-full md:col-span-12 lg:col-span-8">
                    <Skeleton className="h-full min-h-[200px] w-full rounded-[2.5rem]" />
                </div>
                {/* Side Stack */}
                <div className="col-span-1 flex h-full flex-col gap-6 md:col-span-12 lg:col-span-4">
                    <Skeleton className="w-full flex-1 rounded-[2.5rem]" />
                    <Skeleton className="h-48 w-full rounded-[2.5rem]" />
                </div>
            </div>

            {/* Stats Skeleton */}
            <div className="space-y-8">
                <div className="flex items-center justify-between px-2">
                    <Skeleton className="w-48 h-8 rounded-lg" />
                    <Skeleton className="w-24 h-8 rounded-lg" />
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    <Skeleton className="w-full h-40 rounded-[2rem]" />
                    <Skeleton className="w-full h-40 rounded-[2rem]" />
                    <Skeleton className="w-full h-40 rounded-[2rem]" />
                </div>
            </div>
        </div>
    );
}
