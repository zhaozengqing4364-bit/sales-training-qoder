# S02 Replan

**Milestone:** M010
**Slice:** S02
**Blocker Task:** T01
**Created:** 2026-03-30T03:13:14.636Z

## Blocker Description

Replay response schema (ReplayDataResponse in backend/src/common/conversation/schemas.py) does not declare evidence_degradation, so FastAPI/Pydantic silently trims it from replay payloads. This breaks cross-route parity because report and knowledge-check return the field correctly.

## What Changed

T01's blocker was the missing evidence_degradation field on ReplayDataResponse. That field has now been added and all parity tests pass. The remaining T02 work is narrowed: TS type definitions, degraded_reasons compatibility mirror, and admin analytics backward-compatibility verification. The replay schema fix is done; no other plan changes needed.
