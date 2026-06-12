export const COPILOTKIT_TYPED_RENDERING_BRIDGE_STATUS =
    "typed-rendering-only" as const;

export function CopilotKitInteractionAdapter(): never {
    throw new Error(
        "[CopilotKitInteractionAdapter] Use the Python-backed typed ui_event bridge; arbitrary JSX/HTML rendering is not allowed.",
    );
}
