# NFR Performance Report

**Generated:** 2026-04-30T09:44:22.028744
**Commit:** `unknown`
**Branch:** `unknown`
**Environment:** `development`

---

## Summary

| Metric | Value |
|--------|-------|
| Total Metrics Tested | 2 |
| Passed | 1 |
| Failed | 1 |
| Pass Rate | 50.0% |
| Overall Status | **❌ FAIL** |

---

## Performance Targets (Constitution Principle II)

### Core Latency Requirements

| Metric | P95 Target | P95 Actual | P99 Target | P99 Actual | Status |
|--------|-------------|-------------|-------------|-------------|--------|
| User speech to AI response latency | 300.0ms | 320.00ms | N/Ams | 320.00ms | ❌ FAIL |
| WebSocket connection establishment time | 100.0ms | 90.00ms | N/Ams | 90.00ms | ✅ PASS |

---

## Detailed Results

### End To End Latency

- **Status:** ❌ FAIL
- **Samples:** 5
- **P95:** 320.00ms
- **P99:** 320.00ms
- **Min:** 250.00ms
- **Max:** 320.00ms
- **Avg:** 290.00ms

### Websocket Connection

- **Status:** ✅ PASS
- **Samples:** 5
- **P95:** 90.00ms
- **P99:** 90.00ms
- **Min:** 50.00ms
- **Max:** 90.00ms
- **Avg:** 70.00ms

---

## Constitution Compliance

**Principle II: Real-Time Priority**

❌ Some NFR performance targets not met

- **User speech to AI response latency**: P95=320.00ms (target: 300.0ms)