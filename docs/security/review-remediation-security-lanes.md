# Review Remediation Security Lanes 1–4

This document records worker-1's local, reversible remediation scope. It does not authorize real credential rotation, remote history rewriting, production setting changes, or deletion of the preteam backup at `.omx/preteam-untracked-20260501T033414Z`.

| Lane | Finding | Local status | Evidence target | External release gate |
| --- | --- | --- | --- | --- |
| 1 | Credential exposure in examples/docs/history | Placeholders only in env examples; local/CI secret-hygiene scan added | `scripts/check_secret_hygiene.py`; `backend/tests/unit/test_secret_hygiene_scan.py` | Rotate exposed OpenRouter/StepFun/model-encryption/OSS credentials and approve repository history cleanup before release |
| 2 | Admin model-config SSRF/API-key exfiltration | Provider endpoint policy blocks unsafe hosts, credentials in URLs, private DNS results, redirects, and raw upstream bodies | `backend/tests/unit/common/test_ai_endpoint_policy.py`; `backend/tests/unit/admin/test_model_config_security.py` | Production provider host policy management/backlog remains admin/ops-owned |
| 3 | PPT upload path traversal | Upload path is server-generated, extension-limited, resolved under upload root | `backend/tests/unit/admin/test_presentation_upload_safety.py` | None for code; storage root remains environment/operator configuration |
| 4 | RAG cross-encoder plaintext key | API writes encrypt key, responses expose only `has_api_key`, runtime decrypts and lazily re-encrypts legacy plaintext | `backend/tests/unit/admin/test_rag_profile_security.py` | Operator review for any legacy plaintext migration in production data |

## Approval-gated tasks kept outside automation

- Do not rotate real keys in this team run.
- Do not rewrite remote git history or force-push cleanup.
- Do not change production DNS/network/provider settings.
- Do not remove or edit `.omx/preteam-untracked-20260501T033414Z`; it is a preteam untracked backup.
