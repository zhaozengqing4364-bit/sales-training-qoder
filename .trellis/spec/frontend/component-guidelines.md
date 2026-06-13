# Component Guidelines

> How components are built in this project.

---

## Overview

UI builds on **Tailwind CSS** + **Radix UI** primitives wrapped in a **glass** design language. Interactive components are client components (`"use client"`). During practice, **never use native browser dialogs** for errors — use status indicators, toasts, and inline error states.

Reference: `components/ui/`, `.kiro/steering/frontend-principles.md`, Constitution principle I (UX never interrupted).

---

## Component Structure

Typical atom (`components/ui/button.tsx`):

1. `"use client"` when using refs, Radix, or event handlers.
2. Import `cn` from `@/lib/utils` for class merging.
3. `forwardRef` for form controls and Radix slots.
4. Variant props via **explicit variant maps** (see `button.tsx`). The repo does not use `class-variance-authority` today.
5. Export component + prop type.

Domain components compose atoms from `components/ui/` and domain-specific subcomponents.

---

## Props Conventions

- Use **`interface`** for props: `ButtonProps`, `GlassCardProps`, `ConfirmDialogProps`.
- Extend native element props where appropriate: `React.ButtonHTMLAttributes<HTMLButtonElement>`.
- Optional variants with defaults: `variant = "default"`, `size = "md"`.
- Prefer explicit props over spreading unknown bags into DOM.

Example: `components/ui/confirm-dialog.tsx`, `components/ui/glass-card.tsx`.

---

## Styling Patterns

### Tailwind + cn()

```tsx
import { cn } from "@/lib/utils";

<div className={cn("rounded-[2rem] bg-white/70 backdrop-blur-xl", className)} />
```

### Canvas vs surfaces

- **Page canvas**: `bg-slate-50 text-slate-900` (root `app/layout.tsx`).
- **Cards / modals**: glass surfaces — `components/ui/glass-card.tsx`, `glass-modal.tsx`.
- **Buttons**: `rounded-full` in `components/ui/button.tsx`.
- Avoid full-page `bg-white` backgrounds; white is for cards/inputs.

### Viewport-Bound Chat Surfaces

Practice/chat surfaces with persistent headers, status bars, command bars, or composers must be bounded to the viewport. Use a fixed-height flex shell plus `min-h-0` on the scrollable message region so historical messages scroll inside the conversation area instead of pushing the whole page taller.

```tsx
<section className="flex h-[calc(100dvh-7rem)] min-h-0 flex-col overflow-hidden">
  <header className="shrink-0">...</header>
  <div role="log" className="min-h-0 flex-1 overflow-y-auto">...</div>
  <footer className="shrink-0">...</footer>
</section>
```

Do not rely on `min-h-*` alone for chat shells. `min-height` lets content expand the shell, which defeats the internal scroll container and causes the page to grow indefinitely.

### Radix wrappers

| Primitive | Wrapper |
|-----------|---------|
| Dialog | `components/ui/glass-modal.tsx` |
| Tooltip | `components/ui/glass-tooltip.tsx` |
| Slot (polymorphic) | `components/ui/button.tsx` |

Dependencies: `@radix-ui/react-dialog`, `@radix-ui/react-slot`, `@radix-ui/react-tooltip` (see `web/package.json`).

---

## Composition

- **Confirm flows**: `ConfirmDialog` on top of `GlassModal` — not `window.confirm`.
- **Feedback**: `ToastProvider` + `useToast()` — see `components/ui/toast.tsx`.
- **Practice status**: `StatusIndicator` — `components/ui/status-indicator.tsx`.
- **Route errors**: `LearnerRouteErrorState` — inline recovery, no alert.

Barrel exports for multi-file domains: `components/practice/presentation/index.ts`.

---

## Accessibility

- Prefer Radix primitives for focus trap and ESC behavior in modals.
- Interactive controls need visible focus states (Tailwind `focus-visible:`).
- Status changes during practice should be announced via visible UI state, not only console.
- Do not rely on `alert()` for accessibility — it blocks and breaks practice flow.

---

## Anti-Patterns

| Forbidden | Use instead |
|-----------|-------------|
| `alert()`, `confirm()`, `prompt()` | `ConfirmDialog`, `useToast`, `StatusIndicator` |
| Error popups during practice | Inline error + retry affordance |
| Raw Radix in every page | Import from `components/ui/` |
| `bg-white` full-page background | `bg-slate-50` canvas |

Production `src/` has **no** `alert()` usage (tests may use alert in XSS fixtures only).

---

## Common Mistakes

- Adding `"use client"` to entire pages when only a child needs it — split components.
- Duplicating glass styles instead of using `GlassCard` / `GlassModal`.
- Showing API error strings directly — use `getApiErrorMessage()` from `lib/api/client.ts`.

---

## Examples

| Component | Path |
|-----------|------|
| Button + variants | `components/ui/button.tsx` |
| Modal | `components/ui/glass-modal.tsx` |
| Confirm | `components/ui/confirm-dialog.tsx` |
| Practice panel | `components/practice/` |
| Admin tables | `components/admin/` |
