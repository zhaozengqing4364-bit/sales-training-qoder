
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { ArrowLeft, Search } from "lucide-react";

export default function NotFound() {
    return (
        <div className="min-h-screen bg-[#FAFAF9] flex items-center justify-center p-4 relative overflow-hidden">
            {/* Ambient Background */}
            <div className="absolute top-[-20%] left-[-10%] w-[1000px] h-[1000px] bg-blue-100/40 rounded-full blur-[120px] opacity-60" />
            <div className="absolute bottom-[-20%] right-[-10%] w-[1000px] h-[1000px] bg-purple-100/40 rounded-full blur-[120px] opacity-60" />

            <div className="relative z-10 text-center max-w-lg mx-auto">
                <h1 className="text-[150px] font-black text-slate-900/5 leading-none select-none">404</h1>
                <div className="relative -mt-20">
                    <h2 className="text-3xl font-bold text-slate-900 mb-4">Page Not Found</h2>
                    <p className="text-slate-500 mb-8">
                        The page you are looking for might have been removed, had its name changed,
                        or is temporarily unavailable.
                    </p>

                    <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
                        <Button asChild className="rounded-full bg-slate-900 hover:bg-slate-800 text-white shadow-lg w-full sm:w-auto h-12 px-8">
                            <Link href="/">
                                <ArrowLeft className="w-4 h-4 mr-2" /> Return Home
                            </Link>
                        </Button>
                    </div>
                </div>
            </div>
        </div>
    );
}
