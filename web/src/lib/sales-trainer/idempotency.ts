/**
 * 生成提交幂等键。
 *
 * 用于做题/试卷提交等写操作：前端在进入提交流程时生成一次 token，
 * 重复提交（网络重试、双击）携带同一 token，后端按 token 去重返回已存在结果，
 * 避免重复判分。
 *
 * 优先使用浏览器原生 crypto.randomUUID()；非安全上下文（HTTP）回退到
 * crypto.getRandomValues 拼装，仍保证高熵唯一性。
 */
export function generateClientToken(): string {
    if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
        return crypto.randomUUID();
    }
    // 回退：4 字节随机数拼装，足够做客户端幂等键。
    const buffer = new Uint8Array(16);
    if (typeof crypto !== "undefined" && typeof crypto.getRandomValues === "function") {
        crypto.getRandomValues(buffer);
    } else {
        // 极端环境（无 crypto）退化为时间+随机，仍优于无 token。
        for (let i = 0; i < buffer.length; i++) {
            buffer[i] = Math.floor(Math.random() * 256);
        }
    }
    const hex = Array.from(buffer, (byte) => byte.toString(16).padStart(2, "0")).join(
        "",
    );
    return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(
        16,
        20,
    )}-${hex.slice(20)}`;
}
