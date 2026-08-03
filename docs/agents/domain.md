# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

## Before exploring, read these

- **[AGENTS.md](../../AGENTS.md)** — repository engineering and collaboration rules.
- **`CONTEXT.md`** at the repo root if it exists.
- **`docs/adr/`** — read ADRs that touch the area you're about to work in.

If any of these files don't exist, **proceed silently**. Don't flag their absence or suggest creating them upfront. The `/domain-modeling` skill creates them lazily when terms or decisions are resolved.

## File structure

This repo uses a single-context layout:

```
/
├── CONTEXT.md
├── docs/adr/
│   └── ...
└── src/
```

## Use the glossary's vocabulary

When output names a domain concept—in an issue title, refactor proposal, hypothesis, or test name—use the term defined in `CONTEXT.md`. Don't drift to synonyms the glossary explicitly avoids.

If the needed concept isn't in the glossary, reconsider whether the language is being invented or record the genuine gap for `/domain-modeling`.

## Flag ADR conflicts

If output contradicts an existing ADR, surface the conflict explicitly rather than silently overriding it.
