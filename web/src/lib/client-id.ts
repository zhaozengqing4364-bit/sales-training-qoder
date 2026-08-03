/**
 * Generate a high-entropy client identifier in both secure HTTPS contexts and
 * public HTTP demo environments where `crypto.randomUUID` is unavailable.
 */
export function generateClientId(): string {
    if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
        return crypto.randomUUID();
    }

    const buffer = new Uint8Array(16);
    if (typeof crypto !== "undefined" && typeof crypto.getRandomValues === "function") {
        crypto.getRandomValues(buffer);
    } else {
        for (let index = 0; index < buffer.length; index += 1) {
            buffer[index] = Math.floor(Math.random() * 256);
        }
    }
    // Keep the fallback interoperable with UUID validators used by API and audit layers.
    buffer[6] = (buffer[6] & 0x0f) | 0x40;
    buffer[8] = (buffer[8] & 0x3f) | 0x80;
    const hex = Array.from(buffer, (byte) => byte.toString(16).padStart(2, "0")).join("");
    return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}
