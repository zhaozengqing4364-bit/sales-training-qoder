import { generateClientId } from "@/lib/client-id";

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
    return generateClientId();
}
