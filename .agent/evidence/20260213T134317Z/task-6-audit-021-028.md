# task-6-audit-021-028.md

RUN_ID: 20260213T134317Z

## AUDIT-021
- verdict: PASS
- passes: true
- confidence: medium
- command: `grep -n "publishAgent" "web/src/app/admin/agents/page.tsx"; grep -n "/{agent_id}/publish" "backend/src/agent/api/agents.py"`
- code_refs: web/src/app/admin/agents/page.tsx, backend/src/agent/api/agents.py
- db_refs: agents
- expected: Agent list actions map to draft/publish/archive/unpublish/delete state transitions.
- actual: Frontend uses all state-transition APIs; backend exposes publish/archive/unpublish/delete routes.
- repro_steps:
  1. Run recorded command
  2. Inspect referenced FE/BE code paths
  3. Compare expected vs actual and persist output path

## AUDIT-022
- verdict: PASS
- passes: true
- confidence: medium
- command: `grep -n "updateAgentVoicePolicy" "web/src/app/admin/agents/[id]/page.tsx"; grep -n "/voice-runtime/agents/{agent_id}/policy" "backend/src/admin/api/voice_runtime.py"`
- code_refs: web/src/app/admin/agents/[id]/page.tsx, backend/src/agent/api/agent_personas.py, backend/src/admin/api/voice_runtime.py
- db_refs: agent_personas, agent_voice_policies, voice_runtime_profiles
- expected: Agent detail bindings (persona + voice policy) persist through dedicated endpoints.
- actual: Agent detail page calls persona binding and voice policy APIs; backend provides matching routes.
- repro_steps:
  1. Run recorded command
  2. Inspect referenced FE/BE code paths
  3. Compare expected vs actual and persist output path

## AUDIT-023
- verdict: PASS
- passes: true
- confidence: medium
- command: `grep -n "createPersona" "web/src/app/admin/personas/page.tsx"; grep -n "/admin/personas" "backend/src/agent/api/personas.py"`
- code_refs: web/src/app/admin/personas/page.tsx, web/src/app/admin/personas/[id]/page.tsx, backend/src/agent/api/personas.py
- db_refs: personas
- expected: Persona module supports create/update/delete and detail retrieval with DB persistence.
- actual: Frontend persona list/detail pages call persona APIs; backend personas router provides CRUD routes.
- repro_steps:
  1. Run recorded command
  2. Inspect referenced FE/BE code paths
  3. Compare expected vs actual and persist output path

## AUDIT-024
- verdict: PASS
- passes: true
- confidence: medium
- command: `grep -n "uploadDocument" "web/src/app/admin/knowledge/[id]/page.tsx"; grep -n "/admin/knowledge/{kb_id}/documents" "backend/src/common/knowledge/api.py"`
- code_refs: web/src/app/admin/knowledge/page.tsx, web/src/app/admin/knowledge/[id]/page.tsx, backend/src/common/knowledge/api.py
- db_refs: knowledge_bases, knowledge_documents
- expected: Knowledge base and document actions map to upload/list/delete/preview backend APIs.
- actual: Frontend triggers knowledge CRUD and document operations; backend knowledge API exposes matching routes.
- repro_steps:
  1. Run recorded command
  2. Inspect referenced FE/BE code paths
  3. Compare expected vs actual and persist output path

## AUDIT-025
- verdict: PASS
- passes: true
- confidence: medium
- command: `grep -n "api.presentations.upload" "web/src/app/admin/presentations/page.tsx"; grep -n "/presentations" "backend/src/presentation_coach/api/presentations.py"`
- code_refs: web/src/app/admin/presentations/page.tsx, web/src/app/admin/presentations/[id]/page.tsx, backend/src/presentation_coach/api/presentations.py
- db_refs: presentations, pages, required_talking_points, forbidden_words
- expected: Presentation upload/delete/point/forbidden-word actions are end-to-end mapped.
- actual: Frontend list/detail pages call presentation CRUD and point/word APIs; backend routes implement them.
- repro_steps:
  1. Run recorded command
  2. Inspect referenced FE/BE code paths
  3. Compare expected vs actual and persist output path

## AUDIT-026
- verdict: PASS
- passes: true
- confidence: medium
- command: `grep -n "createPromptTemplate" "web/src/app/admin/prompts/new/page.tsx"; grep -n "prompt-templates" "backend/src/prompt_templates/api/routes.py"`
- code_refs: web/src/app/admin/prompts/page.tsx, web/src/app/admin/prompts/new/page.tsx, web/src/app/admin/prompts/[id]/edit/page.tsx, backend/src/prompt_templates/api/routes.py
- db_refs: prompt_templates, scenario_prompts
- expected: Prompt module supports list/create/edit/delete/render with scenario binding routes.
- actual: Frontend prompt pages invoke list/create/edit/render/delete; backend prompt template routes cover CRUD + render.
- repro_steps:
  1. Run recorded command
  2. Inspect referenced FE/BE code paths
  3. Compare expected vs actual and persist output path

## AUDIT-027
- verdict: PASS
- passes: true
- confidence: medium
- command: `grep -n "createModelConfig" "web/src/app/admin/settings/page.tsx"; grep -n "/model-configs" "backend/src/admin/api/model_configs.py"`
- code_refs: web/src/app/admin/settings/page.tsx, backend/src/admin/api/model_configs.py, docs/api-contract/model-configs.md
- db_refs: model_configs
- expected: Model settings page buttons map to create/test/update/delete model config APIs.
- actual: Settings page invokes model-config APIs and backend model-config router includes create/update/delete/test/preview endpoints.
- repro_steps:
  1. Run recorded command
  2. Inspect referenced FE/BE code paths
  3. Compare expected vs actual and persist output path

## AUDIT-028
- verdict: PASS
- passes: true
- confidence: medium
- command: `grep -n "getVoiceRuntimeProfiles" "web/src/app/admin/voice-runtime/page.tsx"; grep -n "/voice-runtime/profiles" "backend/src/admin/api/voice_runtime.py"`
- code_refs: web/src/app/admin/voice-runtime/page.tsx, backend/src/admin/api/voice_runtime.py, docs/api-contract/voice-runtime.md, .agent/evidence/20260213T134317Z/task-9-contract-drift.md
- db_refs: voice_runtime_profiles, agent_voice_policies
- expected: Voice runtime profiles and per-agent policy mapping are persisted via dedicated APIs.
- actual: Voice runtime page calls profile CRUD APIs; backend defines profile CRUD and agent-policy resolve/update routes. Task-9 drift check confirms runtime profile mapping chain and highlights canonical naming alignment action.
- repro_steps:
  1. Run recorded command
  2. Inspect referenced FE/BE code paths
  3. Compare expected vs actual and persist output path

