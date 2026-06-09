import type { ReactNode } from "react";

export const markdownComponents = {
    h1: ({ children }: { readonly children?: ReactNode }) => (
        <h1 className="mb-4 mt-6 text-2xl font-black text-slate-900 first:mt-0">{children}</h1>
    ),
    h2: ({ children }: { readonly children?: ReactNode }) => (
        <h2 className="mb-3 mt-5 text-xl font-bold text-slate-900 first:mt-0">{children}</h2>
    ),
    h3: ({ children }: { readonly children?: ReactNode }) => (
        <h3 className="mb-2 mt-4 text-lg font-bold text-slate-900 first:mt-0">{children}</h3>
    ),
    p: ({ children }: { readonly children?: ReactNode }) => (
        <p className="mb-3 text-sm leading-relaxed text-slate-700 last:mb-0">{children}</p>
    ),
    ul: ({ children }: { readonly children?: ReactNode }) => (
        <ul className="mb-3 list-disc space-y-1 pl-5 text-sm text-slate-700">{children}</ul>
    ),
    ol: ({ children }: { readonly children?: ReactNode }) => (
        <ol className="mb-3 list-decimal space-y-1 pl-5 text-sm text-slate-700">{children}</ol>
    ),
    li: ({ children }: { readonly children?: ReactNode }) => (
        <li className="leading-relaxed">{children}</li>
    ),
    strong: ({ children }: { readonly children?: ReactNode }) => (
        <strong className="font-semibold text-slate-900">{children}</strong>
    ),
    blockquote: ({ children }: { readonly children?: ReactNode }) => (
        <blockquote className="mb-3 border-l-4 border-slate-200 pl-4 text-sm italic text-slate-600">
            {children}
        </blockquote>
    ),
    code: ({ children }: { readonly children?: ReactNode }) => (
        <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-800">{children}</code>
    ),
    pre: ({ children }: { readonly children?: ReactNode }) => (
        <pre className="mb-3 overflow-x-auto rounded-xl bg-slate-900 p-4 text-xs text-slate-100">{children}</pre>
    ),
    a: ({ href, children }: { readonly href?: string; readonly children?: ReactNode }) => (
        <a href={href} className="font-medium text-blue-600 underline underline-offset-2 hover:text-blue-800">
            {children}
        </a>
    ),
};
