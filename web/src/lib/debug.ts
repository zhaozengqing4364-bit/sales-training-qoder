/**
 * v1-25 Fix: Conditional debug logging for production cleanliness.
 * Only logs when NEXT_PUBLIC_DEBUG=true or in development mode.
 */
const IS_DEBUG = process.env.NEXT_PUBLIC_DEBUG === "true" ||
    process.env.NODE_ENV === "development";

export const debug = {
    log: IS_DEBUG ? console.log.bind(console) : () => {},
    warn: IS_DEBUG ? console.warn.bind(console) : () => {},
    error: console.error.bind(console), // Always log errors
};
