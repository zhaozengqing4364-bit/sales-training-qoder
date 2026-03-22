/**
 * Theme Hook - Dark mode support
 * 
 * Features:
 * - System preference detection
 * - Local storage persistence
 * - Smooth transitions
 * - CSS variable integration
 * 
 * Requirements: P2-FIXES.md Issue #32
 */

import { useEffect, useState, useCallback } from 'react';

type Theme = 'light' | 'dark' | 'system';

interface UseThemeReturn {
    /** Current theme */
    theme: Theme;
    /** Resolved theme (light/dark, never system) */
    resolvedTheme: 'light' | 'dark';
    /** Toggle between light and dark */
    toggleTheme: () => void;
    /** Set specific theme */
    setTheme: (theme: Theme) => void;
    /** Whether dark mode is active */
    isDark: boolean;
}

const THEME_STORAGE_KEY = 'theme';

/**
 * Get initial theme from localStorage or system preference
 */
function getInitialTheme(): Theme {
    if (typeof window === 'undefined') return 'system';

    // Check localStorage
    const stored = localStorage.getItem(THEME_STORAGE_KEY) as Theme;
    if (stored && ['light', 'dark', 'system'].includes(stored)) {
        return stored;
    }

    return 'system';
}

/**
 * Get resolved theme (actual light/dark value)
 */
function getResolvedTheme(theme: Theme): 'light' | 'dark' {
    if (theme === 'system') {
        if (typeof window === 'undefined') return 'light';
        return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }
    return theme;
}

/**
 * Apply theme to document
 */
function applyTheme(theme: 'light' | 'dark') {
    if (typeof document === 'undefined') return;

    const root = document.documentElement;
    
    if (theme === 'dark') {
        root.classList.add('dark');
    } else {
        root.classList.remove('dark');
    }

    // Update meta theme-color for mobile browsers
    const metaThemeColor = document.querySelector('meta[name="theme-color"]');
    if (metaThemeColor) {
        metaThemeColor.setAttribute('content', theme === 'dark' ? '#1a1a1a' : '#ffffff');
    }
}

/**
 * Hook for theme management
 * 
 * Usage:
 *   const { theme, resolvedTheme, toggleTheme, isDark } = useTheme();
 *   
 *   <button onClick={toggleTheme}>
 *     {isDark ? '🌙' : '☀️'}
 *   </button>
 */
export function useTheme(): UseThemeReturn {
    const [theme, setThemeState] = useState<Theme>(() => getInitialTheme());
    const resolvedTheme: 'light' | 'dark' = getResolvedTheme(theme);

    // Apply theme when it changes
    useEffect(() => {
        if (typeof window === 'undefined') return;
        applyTheme(resolvedTheme);
        localStorage.setItem(THEME_STORAGE_KEY, theme);
    }, [theme, resolvedTheme]);

    // Listen for system theme changes
    useEffect(() => {
        if (typeof window === 'undefined') return;

        const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
        
        const handleChange = () => {
            if (theme === 'system') {
                const resolved = mediaQuery.matches ? 'dark' : 'light';
                applyTheme(resolved);
            }
        };

        mediaQuery.addEventListener('change', handleChange);
        return () => mediaQuery.removeEventListener('change', handleChange);
    }, [theme]);

    const toggleTheme = useCallback(() => {
        setThemeState(prev => {
            if (prev === 'light') return 'dark';
            if (prev === 'dark') return 'system';
            return 'light';
        });
    }, []);

    const setTheme = useCallback((newTheme: Theme) => {
        setThemeState(newTheme);
    }, []);

    return {
        theme,
        resolvedTheme,
        toggleTheme,
        setTheme,
        isDark: resolvedTheme === 'dark'
    };
}
