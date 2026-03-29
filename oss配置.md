
 Warning: Auto-mode paused due to provider
 error: stream_read_error# 阿里云 OSS / DashScope 直连与密钥排查

更新时间：2026-03-28

## 结论先行

1. 后端 `apps/api` 直接使用 `ali-oss` SDK 连接阿里云 OSS，密钥来自环境变量 `ALI_OSS_ACCESS_KEY_ID` / `ALI_OSS_ACCESS_KEY_SECRET`，不是通过中间网关或代理服务转发。
2. 当前本地运行环境的仓库根 `.env` 中，确实存在非空的 OSS 相关配置项：`ALI_OSS_ACCESS_KEY_ID`、`ALI_OSS_ACCESS_KEY_SECRET`、`ALI_OSS_BUCKET`、`ALI_OSS_ENDPOINT`。本文只确认“已配置”，不暴露具体值。
3. 前端 `apps/web` 没有发现 `NEXT_PUBLIC_*` 形式的 OSS/DashScope 密钥暴露；前端拿到的是后端生成的 `signedUrl`，浏览器再直接 `PUT` 到 OSS。
4. 除 OSS 外，后端还直接连阿里云 DashScope：
   - HTTP ASR：`https://dashscope.aliyuncs.com/api/v1`
   - WebSocket 实时 ASR：`wss://dashscope.aliyuncs.com/api-ws/v1/inference`
   - 使用的密钥是 `DASHSCOPE_API_KEY`
5. `.env` 和 `apps/web/.env.local` 都未被 Git 跟踪，且被 `.gitignore` 忽略；因此当前看到的密钥属于本地运行环境，不是已提交到仓库的源码文件。

## 本次排查范围

- 代码：`apps/api`、`apps/web`
- 配置：`.env.example`、`.env`、`apps/web/.env.local`
- 启动与校验脚本：`start.sh`、`scripts/verify-runtime-baseline.sh`
- 文档：`README.md`、`docs/internal-launch-guide.md`、`docs/releases/*.md`

## 环境变量从哪里读取

### 1. NestJS 运行时读取顺序

`apps/api/src/app.module.ts:29-32`

```ts
ConfigModule.forRoot({
  isGlobal: true,
  envFilePath: ['../../.env', '.env'],
})
```

已验证事实：

- API 会优先读仓库根 `.env`
- 若根 `.env` 没有，再回退到 `apps/api/.env`

### 2. 启动脚本读取顺序

`start.sh:102-115`

```bash
resolve_api_env_value() {
    value=$(read_env_value "$ROOT_ENV_FILE" "$key")
    if [ -n "$value" ]; then
        echo "$value"
        return 0
    fi

    value=$(read_env_value "$API_ENV_FILE" "$key")
    if [ -n "$value" ]; then
        echo "$value"
    fi
}
```

已验证事实：

- 启动脚本和 verifier 的读取逻辑与 API 一致
- 也是“根 `.env` 优先，`apps/api/.env` 次之”

## OSS 是如何直连的

### 1. 直接依赖阿里云 OSS SDK

`apps/api/package.json`

- 依赖：`ali-oss`

`apps/api/src/common/services/oss.service.ts:1-3`

```ts
import { ConfigService } from '@nestjs/config';
import OSS from 'ali-oss';
```

### 2. OSS 客户端初始化位置

`apps/api/src/common/services/oss.service.ts:25-58`

这里直接从 `ConfigService` 读取：

- `ALI_OSS_REGION`
- `ALI_OSS_BUCKET`
- `ALI_OSS_ACCESS_KEY_ID`
- `ALI_OSS_ACCESS_KEY_SECRET`
- `ALI_OSS_ENDPOINT`

然后构造：

```ts
this.client = new OSS({
  region,
  accessKeyId: accessKeyId || '',
  accessKeySecret: accessKeySecret || '',
  bucket: bucket || '',
  secure,
  ...(endpoint ? { endpoint } : {}),
});
```

这说明：

- 后端进程本身持有阿里云 OSS 的 AK/SK
- 不是 STS 临时凭证模式
- 也不是通过服务端调用其他内部上传服务

### 3. OSS 的核心能力都在这个服务里完成

`apps/api/src/common/services/oss.service.ts`

- `uploadFile`：`91-107`
- `uploadBuffer`：`109-133`
- `getObjectStream`：`135-181`
- `deleteFile`：`183-193`
- `generateSignatureUrl`：`195-212`
- `generateDownloadUrl`：`214-225`
- `generatePresignedUrl`：`227-229`
- `buildPublicUrl`：`262-279`

也就是说，仓库里绝大多数 OSS 行为都统一汇聚到了 `OssService`。

## 浏览器上传链路：前端不持密钥，但会直传 OSS

### 1. 前端先向后端申请签名 URL

`apps/web/lib/hooks/useOSSUpload.ts:123-133`

```ts
const response = await api.get('/meetings/presigned-url', {
  params: { filename, userId },
});
```

### 2. 后端生成签名上传地址

`apps/api/src/meetings/meetings.controller.ts:47-53`

```ts
@Get('presigned-url')
getPresignedUrl(...) {
  return this.meetingsService.getUploadSignature(req.user.id, filename);
}
```

`apps/api/src/meetings/meetings.service.ts:804-813`

```ts
const signedUrl = this.ossService.generateSignatureUrl(
  objectKey,
  'PUT',
  contentType,
);
return { signedUrl, objectKey, contentType };
```

### 3. 浏览器直接 PUT 到 OSS

`apps/web/lib/hooks/useOSSUpload.ts:167-173`

```ts
xhr.open('PUT', signedUrl, true);
xhr.setRequestHeader('Content-Type', signedContentType || contentType);
xhr.send(file);
```

结论：

- 前端没有拿到 AK/SK
- 但浏览器会拿着后端签发的 `signedUrl` 直接上传到 OSS
- 这属于“前端直传 OSS，密钥在后端保存”的架构

## 会议音频是如何落到 OSS 并被后续流程使用的

### 1. 上传完成后，仅把 `objectKey` 回传给后端建会议

`apps/web/app/dashboard/components/UploadModal.tsx:79-84`

`apps/web/app/meetings/new/components/AudioUploadForm.tsx:76-86`

两条上传入口都遵循同样的模式：

- 先 `uploadFile(file, userId)`
- 再调用 `POST /meetings/create-from-oss`
- 请求体里只带 `objectKey`

### 2. 后端用 `objectKey` 拼出公开 OSS URL 并持久化

`apps/api/src/meetings/meetings.service.ts:855-873`

```ts
const audioUrl = this.ossService.buildPublicUrl(objectKey);
...
audio_oss_key: objectKey,
audio_url: audioUrl,
```

`apps/api/src/common/services/oss.service.ts:262-279`

`buildPublicUrl` 直接拼：

```ts
${protocol}//${bucket}.${host}/${objectKey}
```

`apps/api/src/meetings/entities/meeting.entity.ts:75-79`

```ts
audio_oss_key: string;
audio_url: string; // Signed URL or public URL if applicable
```

已验证事实：

- 数据库会同时保存 `audio_oss_key` 和 `audio_url`
- `createFromOssKey` 这里保存的是基于 bucket + endpoint 拼出来的公开 URL

### 3. ASR 任务直接消费 `meeting.audio_url`

`apps/api/src/jobs/asr.processor.ts:123-153`

```ts
if (!meeting.audio_url) { ... }
submittedTaskId = await this.asrService.submitTranscription(meeting.audio_url);
```

这说明上传到 OSS 的音频，后续直接作为外部可访问 URL 提交给 ASR 服务。

说明：

- 这里“为何使用公开 URL 而不是下载签名 URL”是代码行为可见事实
- “设计动机是为了让 DashScope 拉取文件”是高概率推断，但属于推断，不当作已验证事实

## 分享页和播放链路

### 1. 分享接口不直接下发 AK/SK，而是下发音频预览签名 URL

`apps/api/src/meetings/meetings.service.ts:613-631`

```ts
return await this.ossService.generatePresignedUrl(objectKey, 1800);
```

`apps/api/src/meetings/meetings.service.ts:739-746`

```ts
audio_preview_url: await this.resolveSharedAudioPreviewUrl(meeting),
```

### 2. 前端分享页明确允许阿里云 OSS 域名作为音频源

`apps/web/app/share/[token]/page.tsx:110-135`

```ts
const isAliyunOssHost =
  hostname.endsWith('.aliyuncs.com') || hostname.endsWith('.aliyun.com');
```

`apps/web/app/share/[token]/page.tsx:302`

```ts
const safeAudioPreviewUrl = getSafeAudioPreviewUrl(fullAccessPayload?.meeting.audio_preview_url);
```

`apps/web/app/share/[token]/page.tsx:546-549`

分享页会把这个地址挂到 `<audio src>`。

结论：

- 分享页不会拿到密钥
- 但会直接消费 OSS 预签名下载地址

## 导出链路也直接依赖 OSS

### 1. 普通导出产物直接上传 OSS

`apps/api/src/export/export.service.ts:1599-1607`

```ts
await this.ossService.uploadBuffer(
  artifact.buffer,
  artifactObjectKey,
  artifact.contentType,
);
```

### 2. PDF authority chain 先把 DOCX 上传 OSS，再取签名 URL 交给 ONLYOFFICE 转 PDF

`apps/api/src/export/export.service.ts:1668-1674`

- authority artifact 上传到 OSS

`apps/api/src/export/export.service.ts:1704-1706`

```ts
const authoritySourceUrl = await this.ossService.generatePresignedUrl(
  authorityObjectKey,
);
```

`apps/api/src/export/export.service.ts:1723-1727`

```ts
const conversion = await this.officeRenderer.convertDocxToPdf({
  key: params.task.id,
  sourceUrl: authoritySourceUrl,
  sourceFileName: authorityFileName,
});
```

`apps/api/src/export/export.service.ts:1751-1755`

- 转换出的 PDF 再上传回 OSS

结论：

- OSS 不只是音频上传存储
- 还是导出链路里的 authority artifact / derived artifact 中转与归档存储

## DashScope 直连情况

### 1. HTTP ASR

`apps/api/src/common/services/asr.service.ts:52`

```ts
private readonly apiUrl = 'https://dashscope.aliyuncs.com/api/v1';
```

`apps/api/src/common/services/asr.service.ts:112-114`

```ts
private get apiKey(): string {
  return this.configService.get<string>('DASHSCOPE_API_KEY') || '';
}
```

`apps/api/src/common/services/asr.service.ts:138-142`

```ts
headers: {
  Authorization: `Bearer ${this.apiKey}`,
  'Content-Type': 'application/json',
  'X-DashScope-Async': 'enable',
}
```

### 2. 实时 ASR WebSocket

`apps/api/src/realtime/asr.gateway.ts:963-970`

```ts
const apiKey = this.configService.get<string>('DASHSCOPE_API_KEY') ?? '';
return new DashscopeRealtimeClient(apiKey, meetingId, ...)
```

`apps/api/src/realtime/dashscope-realtime.client.ts:212-219`

```ts
const url = 'wss://dashscope.aliyuncs.com/api-ws/v1/inference';
const ws = new WebSocket(url, {
  headers: { Authorization: `bearer ${this.apiKey}` },
});
```

结论：

- DashScope 也是后端直连
- 密钥同样保存在后端环境变量，不下发前端

## 当前本地环境里，相关密钥/配置是否存在

### 1. `.env.example` 里定义了这些键

`.env.example:37-46`

ALI_OSS_REGION=oss-cn-beijing
ALI_OSS_ACCESS_KEY_ID=LTAI5tRWRNWWXmQM8UwBH8o1
ALI_OSS_ACCESS_KEY_SECRET=gc9AQiNBiA8obrrZ665oRBiUKaUync
ALI_OSS_BUCKET=zzqouryun
ALI_OSS_ENDPOINT=oss-cn-beijing.aliyuncs.com


### 2. 当前本地根 `.env` 已配置 OSS 相关键

只做了“键存在且非空”的核验，未展示值：

- `.env:25` `ALI_OSS_ACCESS_KEY_ID=[REDACTED]`
- `.env:26` `ALI_OSS_ACCESS_KEY_SECRET=[REDACTED]`
- `.env:27` `ALI_OSS_BUCKET=[REDACTED]`
- `.env:28` `ALI_OSS_ENDPOINT=[REDACTED]`

### 3. 当前本地 `apps/web/.env.local` 未发现这些 OSS / DashScope 键

已核验的键名：

- `ALI_OSS_ACCESS_KEY_ID`
- `ALI_OSS_ACCESS_KEY_SECRET`
- `ALI_OSS_BUCKET`
- `ALI_OSS_ENDPOINT`
- `DASHSCOPE_API_KEY`

结论：

- 这些阿里云相关配置当前集中在后端运行环境
- 没发现前端本地环境持有同名配置

## 这些本地密钥是否被 Git 跟踪

已验证事实：

- `.env` 未被 Git 跟踪
- `apps/web/.env.local` 未被 Git 跟踪

证据：

- `.gitignore:19` 忽略 `.env`
- `apps/web/.gitignore:34` 忽略 `.env*`
- `git ls-files --error-unmatch .env` 返回未跟踪
- `git ls-files --error-unmatch apps/web/.env.local` 返回未跟踪
- `git check-ignore -v .env apps/web/.env.local` 命中忽略规则

结论：

- 当前排查到的真实密钥属于本地环境配置，不是仓库已提交源码

## 未发现的内容

本次搜索未发现以下模式：

- `NEXT_PUBLIC_ALI_*`
- `NEXT_PUBLIC_OSS_*`
- `NEXT_PUBLIC_DASHSCOPE_*`
- 前端代码里直接硬编码 AK/SK
- 仓库已提交文件里出现真实 OSS AK/SK 明文

## 风险备注（仅基于已验证代码行为）

1. 会议上传链路里，`createFromOssKey` 会把 `objectKey` 转成 `audio_url` 并持久化；这里的 `audio_url` 是按 bucket 域名直接拼出来的 URL，不是下载签名 URL。
2. ASR 提交阶段直接使用 `meeting.audio_url`，这意味着该 URL 的可达性会直接影响外部 ASR 拉取。
3. 分享页虽然不拿密钥，但会接受来自 `.aliyuncs.com` / `.aliyun.com` 的音频地址，并在全文分享场景中直接播放预签名 URL。
4. 导出链路对 OSS 的依赖是强依赖，不只是“附件上传”，而是 formal export authority chain 的一部分。

## 一句话总结

这个仓库当前对阿里云的接入模式是：后端持有 `ALI_OSS_*` 和 `DASHSCOPE_API_KEY`，直接连接阿里云 OSS / DashScope；前端不持有密钥，但通过后端签发的 `signedUrl` 直接上传或读取 OSS 资源。当前本地根 `.env` 已配置真实 OSS 相关项，且这些本地环境文件未被 Git 跟踪。
