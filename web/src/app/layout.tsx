import type { Metadata } from "next";
import { AppProviders } from "@/components/providers/app-providers";
import { ToastProvider } from "@/components/ui/toast";
import "./globals.css";

export const metadata: Metadata = {
  title: "新人销售训练平台",
  description: "新人销售学习与能力训练",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <body
        className="antialiased bg-stone-50 text-slate-900 relative min-h-screen overflow-x-hidden selection:bg-amber-100 selection:text-amber-900"
      >
        <AppProviders>
          <ToastProvider>
            {children}
          </ToastProvider>
        </AppProviders>
      </body>
    </html>
  );
}
