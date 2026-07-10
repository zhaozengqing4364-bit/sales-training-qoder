# Gate 0C Vitest 运行时与退出诊断

## 结论

当前没有“测试完成后进程挂住”或遗留 open handle 的证据。此前 5 分钟观察窗口短于当前串行
全量测试的真实执行时间，把“仍在运行”误判成了“无法退出”。2026-07-10 基线在外部 420 秒
诊断上限内自行结束；退出码 1 来自 17 个断言失败，而不是 timeout、signal 或强制 kill。

Gate 0C 不应为了加速而盲目删除 `fileParallelism: false`。该配置于提交 `3e2f91a8` 随大批
历史修复一并引入，提交说明没有记录串行化的具体根因；缺少全量并行稳定性证据时，保持现状
是更保守的选择。全量 6 分钟级运行明显低于 release truth workflow 的 45 分钟 job timeout。
Gate 1B 再把完整自动发现接入唯一 `critical-quality-gate.sh`，而不是在 Gate 0C 新建第二套 runner。

## 全量基线

从 `web/` 执行：

```bash
/usr/bin/time -v timeout -k 10s 420s \
  npx vitest run \
  --reporter=verbose \
  --reporter=hanging-process \
  --reporter=json \
  --outputFile.json=/tmp/gate0c-vitest-baseline.json \
  --logHeapUsage
```

结果：

- 209 个测试文件：2 failed / 207 passed；
- 1332 个测试：17 failed / 1309 passed / 6 skipped；
- Vitest duration：366.45 秒；
- shell wall clock：6:07.86；
- maximum resident set size：404036 KB；
- 在 420 秒上限前自然返回，未收到 timeout exit code 124/137；
- JSON 结果完整写入 `/tmp/gate0c-vitest-baseline.json`。

失败只集中在：

- `src/app/(dashboard)/page.test.tsx`：1 个时区 fixture 漂移；
- `src/app/(dashboard)/sales-trainer/business-skills/page.test.tsx`：16 个 Journey/API
  fixture 与旧语义漂移。

## Open-handle 与生命周期检查

- 全量命令启用了 Vitest `hanging-process` reporter，尾部没有报告遗留句柄或无法终止 worker。
- 三个聚焦文件共 49 个测试约 22 秒自行结束；失败存在时也不会挂住。
- 首页测试目前在 `beforeEach` 恢复 real timers，但单测末尾没有对称 cleanup。Gate 0C 将增加
  `afterEach(() => vi.useRealTimers())`，防止失败/提前返回把 fake timer 泄漏给后续用例。
- 未发现本 Gate 新增 server、WebSocket、listener、observer 或后台轮询资源；无需修改生产生命周期。

## 串行与并行探针

针对 9 个 admin 测试文件做了非生产性探针：

- 当前串行配置：9 files / 33 tests，8.75 秒；
- CLI 临时 4 worker 并行：9 files / 33 tests，3.02 秒；
- 两次都自然退出且断言一致。

这个小样本只证明并行化存在潜在加速空间，不能证明 209 文件全量在共享 module mock、全局
对象替换、fake timer 和 jsdom 环境下无序依赖。因此本 Gate 不修改 runner 并行策略；后续若要
优化，应另做重复全量、随机顺序和失败重放实验，并把结果作为独立架构/测试切片提交。

## CI timeout 与权威 runner

- `web/package.json` 的权威前端命令是 `vitest run`；
- `.github/workflows/release-truth-gate.yml` 的完整 release-truth job timeout 为 45 分钟；
- `scripts/AGENTS.md` 明确要求扩展现有 `critical-quality-gate.sh`，禁止新增第二套质量门禁；
- 当前全量墙钟约占 45 分钟的 14%，有约 7.3 倍单命令余量；
- Gate 0C 用 420 秒只作为诊断保护，不把它写成新的永久 runner timeout；Gate 1B 接线时由
  workflow job timeout 统一约束完整门禁。

## Gate 0C 决策

1. 只修断言失败的根因与 timer cleanup；
2. 保持 `fileParallelism: false`，不以速度优化扩大本 Gate 风险；
3. 修复后运行默认 `npx vitest run`，外层仅用大于基线的安全 watchdog 记录自然 exit 0；
4. 若修复后超过基线尾部且 reporter 报句柄，再二分资源所有者；否则不虚构泄漏修复；
5. 完整自动发现/changed coverage/CI 接线留给 Gate 1B。
