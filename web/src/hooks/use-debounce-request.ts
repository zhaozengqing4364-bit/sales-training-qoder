/**
 * Request deduplication and debouncing hooks
 *
 * Prevents duplicate requests from rapid user interactions
 * Implements loading states and request cancellation
 *
 * Requirements: P1-FIXES.md Issue #14
 */
import { useCallback, useRef, useState } from 'react';

interface UseDebounceRequestOptions {
    /** Delay in milliseconds before allowing next request */
    delay?: number;
    /** Whether to prevent duplicate requests while one is in progress */
    preventDuplicate?: boolean;
}

interface UseDebounceRequestReturn<TArgs extends unknown[], TResult> {
    /** Execute the debounced function */
    execute: (...args: TArgs) => Promise<TResult | undefined>;
    /** Whether a request is currently in progress */
    isLoading: boolean;
    /** Error from the last execution */
    error: Error | null;
    /** Reset the error state */
    resetError: () => void;
}

/**
 * Hook for debouncing requests and preventing duplicates
 * 
 * Features:
 * - Prevents rapid-fire requests
 * - Tracks loading state
 * - Handles request cancellation
 * - Error handling
 * 
 * Usage:
 *   const { execute: createSession, isLoading } = useDebounceRequest(
 *     api.createSession,
 *     { delay: 1000, preventDuplicate: true }
 *   );
 * 
 *   <button 
 *     onClick={() => createSession(agentId, personaId)}
 *     disabled={isLoading}
 *   >
 *     {isLoading ? '创建中...' : '开始练习'}
 *   </button>
 */
export function useDebounceRequest<TArgs extends unknown[], TResult>(
    fn: (...args: TArgs) => Promise<TResult>,
    options: UseDebounceRequestOptions = {}
): UseDebounceRequestReturn<TArgs, TResult> {
    const { delay = 1000, preventDuplicate = true } = options;
    
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<Error | null>(null);
    
    const timerRef = useRef<NodeJS.Timeout | null>(null);
    const requestIdRef = useRef(0);
    const isExecutingRef = useRef(false);
    
    const resetError = useCallback(() => {
        setError(null);
    }, []);
    
    const execute = useCallback(async (...args: TArgs): Promise<TResult | undefined> => {
        // Prevent duplicate requests
        if (preventDuplicate && isExecutingRef.current) {
            console.warn('[useDebounceRequest] Request already in progress, skipping duplicate');
            return undefined;
        }
        
        // Clear any pending timer
        if (timerRef.current) {
            clearTimeout(timerRef.current);
        }
        
        // Generate unique request ID
        const currentRequestId = ++requestIdRef.current;
        
        // Execute immediately or after delay
        return new Promise((resolve, reject) => {
            timerRef.current = setTimeout(async () => {
                isExecutingRef.current = true;
                setIsLoading(true);
                setError(null);
                
                try {
                    const result = await fn(...args);
                    
                    // Only update state if this is still the latest request
                    if (currentRequestId === requestIdRef.current) {
                        setIsLoading(false);
                        isExecutingRef.current = false;
                        resolve(result);
                    }
                } catch (err) {
                    // Only update state if this is still the latest request
                    if (currentRequestId === requestIdRef.current) {
                        const error = err instanceof Error ? err : new Error(String(err));
                        setError(error);
                        setIsLoading(false);
                        isExecutingRef.current = false;
                        reject(error);
                    }
                }
            }, delay);
        });
    }, [fn, delay, preventDuplicate]);
    
    return {
        execute,
        isLoading,
        error,
        resetError
    };
}

/**
 * Hook for preventing rapid clicks on buttons
 * 
 * Usage:
 *   const { isDisabled, handleClick } = useClickThrottle(
 *     () => submitForm(),
 *     2000
 *   );
 * 
 *   <button onClick={handleClick} disabled={isDisabled}>
 *     提交
 *   </button>
 */
export function useClickThrottle(
    callback: () => void | Promise<void>,
    throttleMs: number = 1000
) {
    const [isDisabled, setIsDisabled] = useState(false);
    const timerRef = useRef<NodeJS.Timeout | null>(null);
    
    const handleClick = useCallback(async () => {
        if (isDisabled) return;
        
        setIsDisabled(true);
        
        try {
            await callback();
        } finally {
            timerRef.current = setTimeout(() => {
                setIsDisabled(false);
            }, throttleMs);
        }
    }, [callback, isDisabled, throttleMs]);
    
    // Cleanup on unmount
    const cleanup = useCallback(() => {
        if (timerRef.current) {
            clearTimeout(timerRef.current);
        }
    }, []);
    
    return { isDisabled, handleClick, cleanup };
}

/**
 * Hook for request cancellation using AbortController
 * 
 * Usage:
 *   const { signal, abort, isAborted } = useRequestAbort();
 *   
 *   useEffect(() => {
 *     fetch('/api/data', { signal })
 *       .then(setData);
 *     
 *     return () => abort();
 *   }, []);
 */
export function useRequestAbort() {
    const abortControllerRef = useRef<AbortController | null>(null);
    const [isAborted, setIsAborted] = useState(false);
    const [signal, setSignal] = useState<AbortSignal | undefined>(undefined);
    
    const abort = useCallback(() => {
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
            setIsAborted(true);
            setSignal(undefined);
        }
    }, []);
    
    const createSignal = useCallback(() => {
        // Abort any existing request
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
        }
        
        // Create new controller
        abortControllerRef.current = new AbortController();
        setIsAborted(false);
        setSignal(abortControllerRef.current.signal);
        
        return abortControllerRef.current.signal;
    }, []);
    
    return {
        signal,
        createSignal,
        abort,
        isAborted
    };
}
