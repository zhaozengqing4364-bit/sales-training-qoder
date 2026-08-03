"use client";

import { useEffect } from "react";

import {
    trackFoundationUxEvent,
    type FoundationUxDimension,
    type FoundationUxEvent,
} from "@/lib/newcomer-training/ux-events";

export function FoundationUxSignal({
    event,
    dimension,
}: {
    event: FoundationUxEvent;
    dimension?: FoundationUxDimension;
}) {
    useEffect(() => {
        trackFoundationUxEvent(event, dimension);
    }, [dimension, event]);

    return null;
}
