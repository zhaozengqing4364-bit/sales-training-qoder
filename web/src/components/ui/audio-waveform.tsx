"use client";

import { cn } from "@/lib/utils";
import { motion } from "framer-motion";

interface AudioWaveformProps {
    isAnimate?: boolean;
    barCount?: number;
    className?: string;
    color?: string;
}

export function AudioWaveform({
    isAnimate = false,
    barCount = 5,
    className,
    color = "bg-blue-500",
}: AudioWaveformProps) {
    return (
        <div className={cn("flex items-center gap-1 h-8", className)}>
            {Array.from({ length: barCount }).map((_, index) => (
                <motion.div
                    key={index}
                    className={cn("w-1 rounded-full", color)}
                    animate={
                        isAnimate
                            ? {
                                height: [8, 24, 8],
                            }
                            : { height: 4 }
                    }
                    transition={{
                        duration: 0.8,
                        repeat: Infinity,
                        delay: index * 0.1,
                        ease: "easeInOut",
                    }}
                />
            ))}
        </div>
    );
}
