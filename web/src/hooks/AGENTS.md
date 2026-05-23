# Hooks — `web/src/hooks/`

Client-side behavior shared across routes. Changes here ripple across practice and admin.

## Map

| Hook / path | Responsibility |
|-------------|----------------|
| `use-practice-websocket.ts` | Sales & presentation realtime session |
| `use-examiner-websocket.ts` | Curriculum exam sessions |
| `websocket/` | Transport, handlers, audio playback helpers |
| `use-audio-recorder.ts` + `use-continuous-audio-uploader.ts` | Capture & upload |
| `use-streaming-audio-player.ts` | TTS/stream playback |
| `use-auth-protection.ts` | Client navigation guard |
| `use-current-user.ts` | React Query current user |
| `use-training-preferences.ts`, `use-voice-speed-preference.ts` | Learner prefs |
| `use-sidebar.ts` | Layout collapse (Zustand) |

## Hard Rules

- No raw `console.*` — `debug` from `@/lib/debug`
- Keep protocol parsing in `websocket/message-handlers.ts`
- Co-locate `*.test.ts` with hook files

## Where to Look

- Barrel: `websocket/index.ts`
- Practice integration tests: `use-practice-websocket.test.ts`
