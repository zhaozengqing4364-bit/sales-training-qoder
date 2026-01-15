import { Skeleton } from "@/components/ui/skeleton";

export function DashboardSkeleton() {
    return (
        <div className="space-y-12 pb-20">
            {/* Header Skeleton */}
            <div className="flex items-end justify-between px-2">
                <div className="space-y-3">
                    <Skeleton className="w-32 h-6 rounded-full" />
                    <Skeleton className="w-64 h-10 rounded-lg" />
                    <Skeleton className="w-48 h-6 rounded-lg" />
                </div>
                <Skeleton className="w-40 h-14 rounded-full" />
            </div>

            {/* Bento Grid Skeleton */}
            <div className="grid grid-cols-1 md:grid-cols-12 gap-6 h-[500px]">
                {/* Large Card */}
                <div className="col-span-1 md:col-span-12 lg:col-span-8 h-full">
                    <Skeleton className="w-full h-full rounded-[2.5rem]" />
                </div>
                {/* Side Stack */}
                <div className="col-span-1 md:col-span-12 lg:col-span-4 flex flex-col gap-6 h-full">
                    <Skeleton className="w-full flex-1 rounded-[2.5rem]" />
                    <Skeleton className="w-full h-48 rounded-[2.5rem]" />
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
