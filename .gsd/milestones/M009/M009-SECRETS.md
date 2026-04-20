# M009 — Secrets Manifest

## ALI_OSS_ACCESS_KEY_ID

- **Service:** Alibaba Cloud OSS
- **Dashboard:** https://ram.console.aliyun.com/users/access-keys
- **Format hint:** `LTAI...` (typically starts with `LTAI`)
- **Status:** pending
- **Destination:** dotenv (backend/.env)
- **Steps:**
  1. Navigate to https://ram.console.aliyun.com/users/access-keys
  2. If no RAM sub-user exists for OSS, create one with `AliyunOSSFullAccess` policy attached
  3. Create an AccessKey for that RAM user
  4. Copy the AccessKey ID
  5. Add `ALI_OSS_ACCESS_KEY_ID=<value>` to `backend/.env`

## ALI_OSS_ACCESS_KEY_SECRET

- **Service:** Alibaba Cloud OSS
- **Dashboard:** https://ram.console.aliyun.com/users/access-keys
- **Format hint:** 30-char alphanumeric
- **Status:** pending
- **Destination:** dotenv (backend/.env)
- **Steps:**
  1. Same screen as ALI_OSS_ACCESS_KEY_ID — the secret is shown once at creation time
  2. If lost, delete the old AccessKey pair and create a new one
  3. Add `ALI_OSS_ACCESS_KEY_SECRET=<value>` to `backend/.env`

## ALI_OSS_BUCKET

- **Service:** Alibaba Cloud OSS
- **Dashboard:** https://oss.console.aliyun.com/bucket
- **Format hint:** lowercase bucket name (e.g. `zzqouryun`)
- **Status:** pending
- **Destination:** dotenv (backend/.env)
- **Steps:**
  1. Navigate to https://oss.console.aliyun.com/bucket
  2. Select the existing bucket (or create a new one for training audio)
  3. Copy the bucket name
  4. Add `ALI_OSS_BUCKET=<value>` to `backend/.env`

## ALI_OSS_ENDPOINT

- **Service:** Alibaba Cloud OSS
- **Dashboard:** https://oss.console.aliyun.com/bucket → Bucket Overview → Access Port → Endpoint
- **Format hint:** `oss-cn-<region>.aliyuncs.com` (e.g. `oss-cn-beijing.aliyuncs.com`)
- **Status:** pending
- **Destination:** dotenv (backend/.env)
- **Steps:**
  1. Navigate to the bucket overview page in OSS console
  2. Find the "Endpoint" field (under bucket > Overview > Access Port > Endpoint)
  3. Copy the public endpoint (VPC endpoint if backend runs inside Alibaba Cloud)
  4. Add `ALI_OSS_ENDPOINT=<value>` to `backend/.env`

## ALI_OSS_REGION

- **Service:** Alibaba Cloud OSS
- **Dashboard:** https://oss.console.aliyun.com/bucket → Bucket Overview
- **Format hint:** `oss-cn-<region>` (e.g. `oss-cn-beijing`)
- **Status:** pending
- **Destination:** dotenv (backend/.env)
- **Steps:**
  1. Same as ALI_OSS_ENDPOINT — region is the prefix before `.aliyuncs.com`
  2. Add `ALI_OSS_REGION=<value>` to `backend/.env`
