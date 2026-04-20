"use client";

import { ErrorBoundary } from "@/components/ErrorBoundary";
import { ReactNode } from "react";

interface ClientErrorBoundaryProps {
  children: ReactNode;
}

export function ClientErrorBoundary({ children }: ClientErrorBoundaryProps) {
  return <ErrorBoundary>{children}</ErrorBoundary>;
}
