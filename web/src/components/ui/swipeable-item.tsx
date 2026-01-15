"use client";

import React, { useState } from "react";
import { motion, PanInfo, useAnimation } from "framer-motion";
import { Trash2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface SwipeableItemProps {
    children: React.ReactNode;
    onDelete: () => void;
    className?: string;
}

export function SwipeableItem({ children, onDelete, className }: SwipeableItemProps) {
    const controls = useAnimation();
    const [isDeleting, setIsDeleting] = useState(false);

    const handleDragEnd = async (event: any, info: PanInfo) => {
        const offset = info.offset.x;
        const velocity = info.velocity.x;

        // Swipe left to delete threshold
        if (offset < -100 || (offset < -50 && velocity < -500)) {
            setIsDeleting(true);
            await controls.start({ x: "-100%", opacity: 0, transition: { duration: 0.2 } });
            onDelete();
        } else {
            controls.start({ x: 0, opacity: 1 });
        }
    };

    if (isDeleting) {
        return null; // or keep it unmounted by parent
    }

    return (
        <div className={cn("relative overflow-hidden group", className)}>
            {/* Delete Action Background */}
            <div className="absolute inset-0 bg-red-500 rounded-[1.5rem] flex items-center justify-end pr-8">
                <Trash2 className="w-6 h-6 text-white animate-pulse" />
            </div>

            {/* Swipeable Content */}
            <motion.div
                drag="x"
                dragConstraints={{ left: 0, right: 0 }}
                dragElastic={{ left: 0.5, right: 0.1 }} // Allow drag left easier
                onDragEnd={handleDragEnd}
                animate={controls}
                className="relative bg-white rounded-[1.5rem] z-10" // added bg-white to cover background
                style={{ touchAction: "pan-y" }} // allow vertical scroll
            >
                {children}
            </motion.div>
        </div>
    );
}
