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

    // Use sendBeacon for reliability
    if (navigator.sendBeacon) {
        navigator.sendBeacon('/api/v1/analytics/performance', body);
    } else {
        fetch('/api/v1/analytics/performance', {
            method: 'POST',
            body,
            keepalive: true,
            headers: { 'Content-Type': 'application/json' }
        }).catch(() => {
            // Silent fail
        });
    }

    // Also log to console in development
    if (process.env.NODE_ENV === 'development') {
        console.log(`[Performance] ${metric.name}: ${metric.value.toFixed(2)} (${metric.rating})`);
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

    if (navigator.sendBeacon) {
        navigator.sendBeacon('/api/v1/analytics/custom', body);
    } else {
        fetch('/api/v1/analytics/custom', {
            method: 'POST',
            body,
            keepalive: true,
            headers: { 'Content-Type': 'application/json' }
        }).catch(() => {});
    }
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
