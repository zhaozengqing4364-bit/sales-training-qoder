"use client";

import { Button } from "@/components/ui/button";

export default function NewcomerTrainingError({ reset }: { reset: () => void }) {
    return (
        <main className="mx-auto max-w-xl px-4 py-12">
            <section role="alert" className="rounded-2xl border border-red-200 bg-red-50 p-6 text-red-950">
                <h1 className="font-semibold">训练路径暂时无法加载</h1>
                <p className="mt-2 text-sm leading-6">当前页面没有丢失任何训练记录。请检查网络后重新加载。</p>
                <Button type="button" className="mt-4" variant="outline" onClick={reset}>重新加载训练路径</Button>
            </section>
        </main>
    );
}
