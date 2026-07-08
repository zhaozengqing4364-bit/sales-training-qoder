# Sales Trainer Audio Evaluation Scenarios

> Backend contract for newcomer training audio assessment scenes. Use this when adding or changing PPT explanation, product demo, elevator pitch, or any future audio-upload + AI-scoring task.

## Core Boundary

`SalesTrainerAudioSubmission` and the ASR / AI scoring pipeline are the capability layer. Business tasks such as PPT explanation, company product demo, and elevator pitch are scenario layer objects. Do not add PPT-specific or product-demo-specific branches inside the generic submission, transcription, scoring, material snapshot, or result projection flow.

## Scenario Registry

Audio assessment scenario identity is centralized in `sales_trainer.services.audio_evaluation_scenarios`.

Each scenario must define:

- `scenario_key`
- `module_key`
- `purpose_key`
- display name
- `module_type`
- material policy
- prompt/completion/runtime semantics
- legacy error compatibility when needed

The first governed scenarios are:

- `ppt_explanation`: legacy purpose `ppt_pitch`, material policy `required_confirmed`, legacy error `[PPT_MATERIAL_BINDING_REQUIRED]`.
- `company_product_demo`: purpose `company_product_demo`, material policy `required_confirmed`, generic error `[AUDIO_EVALUATION_MATERIAL_BINDING_REQUIRED]`.
- `elevator_pitch`: purpose `elevator_pitch`, material policy optional, grouped audio runtime.

## Path Config Compatibility

`newcomer_path.modules[]` may carry additive `scenario_key`. Old payloads without this field must still resolve by `module_key` or `purpose`.

Validation rules:

- Unknown `scenario_key` is rejected.
- A scenario may only bind to its registered `module_key`.
- New fields are additive; do not require migration of historical path revisions.
- Product demo must be enabled by an explicit path module, not silently inserted into default required modules.

## Material Gate

Material requirement is scenario policy, never `purpose == "ppt_pitch"` alone.

Apply the same policy in:

- unit material config validation;
- path publish validation;
- learner audio submission gate;
- submission material snapshot freeze.

`required_confirmed` means at least one required + confirmation-required published material binding is present and the learner confirms the current required version before submission. Optional scenarios must be allowed to submit without material unless an explicit material binding is configured.

## Error Compatibility

Keep legacy PPT errors for old clients:

- PPT explanation / `ppt_pitch`: `[PPT_MATERIAL_BINDING_REQUIRED]`.
- Other required-material audio scenarios: `[AUDIO_EVALUATION_MATERIAL_BINDING_REQUIRED]`.

Do not expose raw `scenario_key`, `purpose_key`, prompt hash, or internal module keys in ordinary admin surfaces. Advanced diagnostics and operation logs may show them when permissioned.

## Tests Required

When adding or changing a scenario:

- registry resolution by `scenario_key`, `module_key`, and `purpose_key`;
- path config save/publish with `scenario_key`;
- required vs optional material policy at material-service and submission-service boundaries;
- frontend DTO/ViewModel mapping if the scenario appears in admin UI;
- compatibility for legacy PPT purpose and historical snapshots.
