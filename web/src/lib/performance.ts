import { debug } from "./debug";
/**
 * Performance Monitor - Track Web Vitals and custom metrics
 * 
 * Monitors:
 * - Core Web Vitals (CLS, FID, FCP, LCP, TTFB)
 * - Custom business metrics
 * - Resource loading times
 * 
 * Requirements: P2-FIXES.md Issue #30
 */

import { useEffect } from 'react';

const LOOPBACK_HOST_FALLBACK_MAP: Record<string, string> = {
    localhost: '127.0.0.1',
    '127.0.0.1': 'localhost',
    '::1': '127.0.0.1',
};

const DEFAULT_API_BASE_URL = 'http://localhost:3444/api/v1';

type TelemetryEventType = 'custom' | 'error' | 'performance';

// Core Web Vitals types
interface Metric {
    name: string;
    value: number;
    rating: 'good' | 'needs-improvement' | 'poor';
    delta: number;
    id: string;
    entries: PerformanceEntry[];
}

interface LayoutShiftPerformanceEntry extends PerformanceEntry {
    hadRecentInput: boolean;
    value: number;
}

interface FirstInputPerformanceEntry extends PerformanceEntry {
    processingStart: number;
    id?: string;
}

type ReportHandler = (metric: Metric) => void;

function isLoopbackHost(hostname: string): boolean {
    return hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '::1';
}

function resolveTelemetryApiBaseUrl(): string | null {
    const configuredApiBaseUrl = (process.env.NEXT_PUBLIC_API_URL || DEFAULT_API_BASE_URL).trim();
    if (!configuredApiBaseUrl) {
        return null;
    }

    try {
        const parsed = new URL(configuredApiBaseUrl);
        if (typeof window !== 'undefined') {
            const pageHost = window.location.hostname;
            if (pageHost && !isLoopbackHost(pageHost) && isLoopbackHost(parsed.hostname)) {
                parsed.hostname = pageHost;
            }
        }

        return parsed.toString().replace(/\/+$/, '');
    } catch {
        debug.warn('[Performance] Telemetry disabled: invalid NEXT_PUBLIC_API_URL', configuredApiBaseUrl);
        return null;
    }
}

export function resolveTelemetryUrl(eventType: TelemetryEventType): string | null {
    const apiBaseUrl = resolveTelemetryApiBaseUrl();
    if (!apiBaseUrl) {
        return null;
    }

    return `${apiBaseUrl}/analytics/${eventType}`;
}

function getLoopbackFallbackUrl(url: string): string | null {
    try {
        const parsed = new URL(url);
        const fallbackHost = LOOPBACK_HOST_FALLBACK_MAP[parsed.hostname];
        if (!fallbackHost) {
            return null;
        }

        parsed.hostname = fallbackHost;
        return parsed.toString();
    } catch {
        return null;
    }
}

async function fetchTelemetry(targetUrl: string, body: string): Promise<void> {
    try {
        await fetch(targetUrl, {
            method: 'POST',
            body,
            keepalive: true,
            headers: { 'Content-Type': 'application/json' },
        });
    } catch (error) {
        if (!(error instanceof TypeError)) {
            throw error;
        }

        const fallbackUrl = getLoopbackFallbackUrl(targetUrl);
        if (!fallbackUrl) {
            throw error;
        }

        await fetch(fallbackUrl, {
            method: 'POST',
            body,
            keepalive: true,
            headers: { 'Content-Type': 'application/json' },
        });
    }
}

export function postTelemetryEvent(eventType: TelemetryEventType, body: string): void {
    const targetUrl = resolveTelemetryUrl(eventType);
    if (!targetUrl) {
        return;
    }

    const beaconBody = new Blob([body], { type: 'application/json' });
    if (typeof navigator !== 'undefined' && typeof navigator.sendBeacon === 'function') {
        const accepted = navigator.sendBeacon(targetUrl, beaconBody);
        if (accepted) {
            return;
        }
    }

    fetchTelemetry(targetUrl, body).catch(() => {
        debug.warn(`[Performance] Failed to deliver ${eventType} telemetry beacon`, targetUrl);
    });
}

/**
 * Get CLS (Cumulative Layout Shift)
 */
function getCLS(onReport: ReportHandler) {
    if (typeof window === 'undefined' || !('PerformanceObserver' in window)) return;

    let clsValue = 0;
    const clsEntries: PerformanceEntry[] = [];

    const observer = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
            const layoutShiftEntry = entry as LayoutShiftPerformanceEntry;
            if (!layoutShiftEntry.hadRecentInput) {
                clsValue += layoutShiftEntry.value;
                clsEntries.push(entry);
            }
        }
    });

    observer.observe({ entryTypes: ['layout-shift'] });

    // Report on visibility change
    const reportCLS = () => {
        onReport({
            name: 'CLS',
            value: clsValue,
            rating: clsValue <= 0.1 ? 'good' : clsValue <= 0.25 ? 'needs-improvement' : 'poor',
            delta: clsValue,
            id: Math.random().toString(36).slice(2),
            entries: clsEntries
        });
    };

    document.addEventListener('visibilitychange', reportCLS);
}

/**
 * Get FID (First Input Delay)
 */
function getFID(onReport: ReportHandler) {
    if (typeof window === 'undefined' || !('PerformanceObserver' in window)) return;

    const observer = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
            const firstInputEntry = entry as FirstInputPerformanceEntry;
            const fid = firstInputEntry.processingStart - entry.startTime;
            onReport({
                name: 'FID',
                value: fid,
                rating: fid <= 100 ? 'good' : fid <= 300 ? 'needs-improvement' : 'poor',
                delta: fid,
                id: firstInputEntry.id || Math.random().toString(36).slice(2),
                entries: [entry]
            });
        }
    });

    observer.observe({ entryTypes: ['first-input'] });
}

/**
 * Get FCP (First Contentful Paint)
 */
function getFCP(onReport: ReportHandler) {
    if (typeof window === 'undefined' || !('PerformanceObserver' in window)) return;

    const observer = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
            if (entry.name === 'first-contentful-paint') {
                onReport({
                    name: 'FCP',
                    value: entry.startTime,
                    rating: entry.startTime <= 1800 ? 'good' : entry.startTime <= 3000 ? 'needs-improvement' : 'poor',
                    delta: entry.startTime,
                    id: Math.random().toString(36).slice(2),
                    entries: [entry]
                });
            }
        }
    });

    observer.observe({ entryTypes: ['paint'] });
}

/**
 * Get LCP (Largest Contentful Paint)
 */
function getLCP(onReport: ReportHandler) {
    if (typeof window === 'undefined' || !('PerformanceObserver' in window)) return;

    let lcpEntry: PerformanceEntry | null = null;

    const observer = new PerformanceObserver((list) => {
        const entries = list.getEntries();
        lcpEntry = entries[entries.length - 1];
    });

    observer.observe({ entryTypes: ['largest-contentful-paint'] });

    // Report on visibility change
    const reportLCP = () => {
        if (lcpEntry) {
            const value = lcpEntry.startTime;
            onReport({
                name: 'LCP',
                value,
                rating: value <= 2500 ? 'good' : value <= 4000 ? 'needs-improvement' : 'poor',
                delta: value,
                id: Math.random().toString(36).slice(2),
                entries: [lcpEntry]
            });
        }
    };

    document.addEventListener('visibilitychange', reportLCP);
}

/**
 * Get TTFB (Time to First Byte)
 */
function getTTFB(onReport: ReportHandler) {
    if (typeof window === 'undefined') return;

    const navigation = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming;
    if (navigation) {
        const value = navigation.responseStart;
        onReport({
            name: 'TTFB',
            value,
            rating: value <= 800 ? 'good' : value <= 1800 ? 'needs-improvement' : 'poor',
            delta: value,
            id: Math.random().toString(36).slice(2),
            entries: [navigation]
        });
    }
}

/**
 * Send metric to analytics endpoint
 */
function sendToAnalytics(metric: Metric) {
    const body = JSON.stringify({
        name: metric.name,
        value: metric.value,
        rating: metric.rating,
        delta: metric.delta,
        id: metric.id,
        url: window.location.href,
        timestamp: new Date().toISOString()
    });

    postTelemetryEvent('performance', body);

    // Also log to console in development
    if (process.env.NODE_ENV === 'development') {
        debug.log(`[Performance] ${metric.name}: ${metric.value.toFixed(2)} (${metric.rating})`);
    }
}

/**
 * Track custom metric
 */
export function trackCustomMetric(name: string, value: number, metadata?: Record<string, unknown>) {
    const body = JSON.stringify({
        name,
        value,
        metadata,
        url: window.location.href,
        timestamp: new Date().toISOString()
    });

    postTelemetryEvent('custom', body);
}

/**
 * Track WebSocket connection time
 */
export function trackWebSocketConnect(duration: number) {
    trackCustomMetric('websocket_connect', duration);
}

/**
 * Track audio latency
 */
export function trackAudioLatency(latency: number) {
    trackCustomMetric('audio_latency', latency);
}

/**
 * Track page load time
 */
export function trackPageLoad() {
    if (typeof window === 'undefined') return;

    window.addEventListener('load', () => {
        setTimeout(() => {
            const timing = performance.timing;
            const loadTime = timing.loadEventEnd - timing.navigationStart;
            trackCustomMetric('page_load', loadTime);
        }, 0);
    });
}

/**
 * React hook for performance monitoring
 */
export function usePerformanceMonitor() {
    useEffect(() => {
        if (typeof window === 'undefined') return;

        // Initialize Core Web Vitals tracking
        getCLS(sendToAnalytics);
        getFID(sendToAnalytics);
        getFCP(sendToAnalytics);
        getLCP(sendToAnalytics);
        getTTFB(sendToAnalytics);

        // Track page load
        trackPageLoad();
    }, []);
}

/**
 * Initialize performance monitoring
 */
export function initPerformanceMonitor() {
    if (typeof window === 'undefined') return;

    getCLS(sendToAnalytics);
    getFID(sendToAnalytics);
    getFCP(sendToAnalytics);
    getLCP(sendToAnalytics);
    getTTFB(sendToAnalytics);
    trackPageLoad();
}

export { getCLS, getFID, getFCP, getLCP, getTTFB };
export type { Metric };
