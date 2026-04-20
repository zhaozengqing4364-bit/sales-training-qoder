/**
 * Error Boundary - Catch React errors and display fallback UI
 * 
 * Prevents white screen of death
 * Provides graceful error recovery
 * Logs errors to monitoring service
 * 
 * Requirements: P2-FIXES.md Issue #29
 */

import React, { Component, ErrorInfo, ReactNode } from 'react';

import { debug } from '@/lib/debug';
import { postTelemetryEvent } from '@/lib/performance';

interface Props {
    children: ReactNode;
    fallback?: ReactNode;
    onError?: (error: Error, errorInfo: ErrorInfo) => void;
}

interface State {
    hasError: boolean;
    error: Error | null;
}

interface SentryWindow extends Window {
    Sentry?: {
        captureException: (error: Error, context?: { extra?: ErrorInfo }) => void;
    };
}

/**
 * Error Boundary component
 * 
 * Usage:
 *   <ErrorBoundary>
 *     <MyComponent />
 *   </ErrorBoundary>
 * 
 *   <ErrorBoundary fallback={<CustomErrorUI />}>
 *     <MyComponent />
 *   </ErrorBoundary>
 */
export class ErrorBoundary extends Component<Props, State> {
    constructor(props: Props) {
        super(props);
        this.state = {
            hasError: false,
            error: null
        };
    }

    static getDerivedStateFromError(error: Error): State {
        return {
            hasError: true,
            error
        };
    }

    componentDidCatch(error: Error, errorInfo: ErrorInfo) {
        // M015/S01 inventory note: ErrorBoundary is a durable route error surface.
        // Keep the fallback UI + reporting side effects here, but route the durable
        // report through the shared seam instead of leaving a bespoke raw console call.
        debug.durableError('react.error-boundary', error, {
            componentStack: errorInfo.componentStack,
            boundary: 'ErrorBoundary',
        });

        // Send to monitoring service if available
        if (typeof window !== 'undefined') {
            // Sentry
            const sentryWindow = window as SentryWindow;
            if (sentryWindow.Sentry) {
                sentryWindow.Sentry.captureException(error, {
                    extra: errorInfo
                });
            }

            postTelemetryEvent('error', JSON.stringify({
                error: error.message,
                stack: error.stack,
                componentStack: errorInfo.componentStack,
                url: window.location.href,
                userAgent: navigator.userAgent,
                timestamp: new Date().toISOString(),
                source: 'react.error-boundary',
                boundary: 'ErrorBoundary',
            }));
        }

        // Call custom error handler
        this.props.onError?.(error, errorInfo);
    }

    private handleRetry = () => {
        this.setState({ hasError: false, error: null });
    };

    private handleReload = () => {
        window.location.reload();
    };

    render() {
        if (this.state.hasError) {
            // Custom fallback UI
            if (this.props.fallback) {
                return this.props.fallback;
            }

            // Default error UI
            return (
                <div className="min-h-screen flex items-center justify-center bg-stone-50 p-4">
                    <div className="max-w-md w-full bg-white rounded-2xl shadow-card p-8 text-center">
                        <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
                            <svg 
                                className="w-8 h-8 text-red-500" 
                                fill="none" 
                                stroke="currentColor" 
                                viewBox="0 0 24 24"
                            >
                                <path 
                                    strokeLinecap="round" 
                                    strokeLinejoin="round" 
                                    strokeWidth={2} 
                                    d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" 
                                />
                            </svg>
                        </div>
                        
                        <h2 className="text-xl font-semibold text-zinc-900 mb-2">
                            出错了
                        </h2>
                        
                        <p className="text-zinc-500 mb-6">
                            页面遇到了一些问题，请尝试刷新页面或返回重试
                        </p>

                        {process.env.NODE_ENV === 'development' && this.state.error && (
                            <div className="mb-6 p-4 bg-red-50 rounded-lg text-left overflow-auto">
                                <p className="text-sm font-mono text-red-600">
                                    {this.state.error.message}
                                </p>
                            </div>
                        )}
                        
                        <div className="flex gap-3 justify-center">
                            <button
                                onClick={this.handleRetry}
                                className="px-4 py-2 bg-white border border-zinc-200 rounded-lg text-zinc-700 hover:bg-zinc-50 transition-colors"
                            >
                                重试
                            </button>
                            <button
                                onClick={this.handleReload}
                                className="px-4 py-2 bg-zinc-900 text-white rounded-lg hover:bg-zinc-800 transition-colors"
                            >
                                刷新页面
                            </button>
                        </div>
                    </div>
                </div>
            );
        }

        return this.props.children;
    }
}

/**
 * Higher-order component for error boundary
 * 
 * Usage:
 *   const SafeComponent = withErrorBoundary(MyComponent);
 */
export function withErrorBoundary<P extends object>(
    Component: React.ComponentType<P>,
    fallback?: ReactNode
) {
    return function WithErrorBoundaryWrapper(props: P) {
        return (
            <ErrorBoundary fallback={fallback}>
                <Component {...props} />
            </ErrorBoundary>
        );
    };
}

/**
 * Async error boundary for data fetching
 * 
 * Usage:
 *   <AsyncErrorBoundary>
 *     <DataComponent />
 *   </AsyncErrorBoundary>
 */
export class AsyncErrorBoundary extends Component<Props, State> {
    constructor(props: Props) {
        super(props);
        this.state = { hasError: false, error: null };
    }

    static getDerivedStateFromError(error: Error): State {
        return { hasError: true, error };
    }

    componentDidCatch(error: Error, errorInfo: ErrorInfo) {
        // M015/S01 inventory note: Async boundary failures are also durable route-level
        // errors, so they belong on the shared debug seam instead of bespoke console use.
        debug.durableError('react.async-error-boundary', error, {
            componentStack: errorInfo.componentStack,
            boundary: 'AsyncErrorBoundary',
        });
    }

    render() {
        if (this.state.hasError) {
            return (
                <div className="p-8 text-center">
                    <p className="text-zinc-500 mb-4">数据加载失败</p>
                    <button
                        onClick={() => this.setState({ hasError: false, error: null })}
                        className="px-4 py-2 bg-zinc-900 text-white rounded-lg"
                    >
                        重新加载
                    </button>
                </div>
            );
        }

        return this.props.children;
    }
}
