import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useStreamingAudioPlayer } from "./use-streaming-audio-player";

const originalAudio = globalThis.Audio;
const originalMediaSource = globalThis.MediaSource;
const originalAudioContext = globalThis.AudioContext;
const originalCreateObjectURL = URL.createObjectURL;
const originalRevokeObjectURL = URL.revokeObjectURL;

let mediaSourceSupported = true;
const createdAudioElements: MockAudioElement[] = [];
const createdMediaSources: MockMediaSource[] = [];
const createdPcmSources: MockAudioBufferSourceNode[] = [];

function toBase64(buffer: ArrayBuffer): string {
    const bytes = new Uint8Array(buffer);
    let binary = "";
    for (let index = 0; index < bytes.length; index += 1) {
        binary += String.fromCharCode(bytes[index]);
    }
    return btoa(binary);
}

class MockAudioElement {
    src: string;
    playbackRate = 1;
    currentTime = 0;
    error: { message?: string } | null = null;
    onplay: (() => void) | null = null;
    onpause: (() => void) | null = null;
    onended: (() => void) | null = null;
    onwaiting: (() => void) | null = null;
    onplaying: (() => void) | null = null;
    ontimeupdate: (() => void) | null = null;
    onerror: (() => void) | null = null;

    play = vi.fn(() => {
        this.onplay?.();
        this.onplaying?.();
        return Promise.resolve();
    });

    pause = vi.fn(() => {
        this.onpause?.();
    });

    constructor(src = "") {
        this.src = src;
        createdAudioElements.push(this);
    }
}

class MockSourceBuffer {
    updating = false;
    onupdateend: (() => void) | null = null;
    onerror: (() => void) | null = null;
    buffered = {
        length: 0,
        end: vi.fn(() => 0),
    };

    appendBuffer = vi.fn((buffer: ArrayBuffer) => {
        this.buffered.length = buffer.byteLength > 0 ? 1 : 0;
        this.buffered.end = vi.fn(() => 0.25);
        this.onupdateend?.();
    });

    abort = vi.fn();
    addEventListener = vi.fn((event: string, callback: () => void) => {
        if (event === "updateend") {
            this.onupdateend = callback;
        }
    });
}

class MockMediaSource {
    static isTypeSupported = vi.fn(() => mediaSourceSupported);

    readyState: "closed" | "open" | "ended" = "closed";
    onsourceopen: (() => void) | null = null;
    onsourceended: (() => void) | null = null;
    onsourceclose: (() => void) | null = null;
    sourceBuffer = new MockSourceBuffer();

    constructor() {
        createdMediaSources.push(this);
    }

    addSourceBuffer = vi.fn(() => this.sourceBuffer as unknown as SourceBuffer);

    endOfStream = vi.fn(() => {
        this.readyState = "ended";
        this.onsourceended?.();
    });

    open() {
        this.readyState = "open";
        this.onsourceopen?.();
    }
}

class MockAudioBufferSourceNode {
    buffer: { duration: number } | null = null;
    playbackRate = { value: 1 };
    onended: (() => void) | null = null;
    connect = vi.fn();
    disconnect = vi.fn();
    start = vi.fn();
}

class MockAudioContext {
    currentTime = 0;
    state: "running" | "suspended" | "closed" = "running";
    destination = {} as AudioDestinationNode;
    close = vi.fn(async () => {
        this.state = "closed";
    });
    resume = vi.fn(async () => {
        this.state = "running";
    });

    constructor(_options?: AudioContextOptions) { }

    createBuffer(_channels: number, length: number, sampleRate: number) {
        return {
            duration: length / sampleRate,
            copyToChannel: vi.fn(),
        } as unknown as AudioBuffer;
    }

    createBufferSource() {
        const source = new MockAudioBufferSourceNode();
        createdPcmSources.push(source);
        return source as unknown as AudioBufferSourceNode;
    }
}

describe("useStreamingAudioPlayer voice speed playbackRate wiring", () => {
    beforeEach(() => {
        mediaSourceSupported = true;
        createdAudioElements.length = 0;
        createdMediaSources.length = 0;
        createdPcmSources.length = 0;

        vi.stubGlobal("Audio", MockAudioElement as unknown as typeof Audio);
        vi.stubGlobal("MediaSource", MockMediaSource as unknown as typeof MediaSource);
        vi.stubGlobal("AudioContext", MockAudioContext as unknown as typeof AudioContext);
        URL.createObjectURL = vi.fn(() => "blob:mock-audio-url");
        URL.revokeObjectURL = vi.fn();
    });

    afterEach(() => {
        vi.restoreAllMocks();

        if (originalAudio) {
            vi.stubGlobal("Audio", originalAudio);
        } else {
            vi.unstubAllGlobals();
        }

        if (originalMediaSource) {
            vi.stubGlobal("MediaSource", originalMediaSource);
        }

        if (originalAudioContext) {
            vi.stubGlobal("AudioContext", originalAudioContext);
        }

        URL.createObjectURL = originalCreateObjectURL;
        URL.revokeObjectURL = originalRevokeObjectURL;
    });

    it("applies the shared playbackRate to the MediaSource HTMLAudioElement path", () => {
        const { result } = renderHook(() => useStreamingAudioPlayer({ playbackRate: 1.25 }));

        act(() => {
            result.current.start();
        });

        const mediaSource = createdMediaSources.at(-1);
        expect(mediaSource).toBeDefined();

        act(() => {
            mediaSource?.open();
        });

        act(() => {
            result.current.appendChunk({
                chunk_index: 0,
                audio: toBase64(Uint8Array.from([1, 2, 3]).buffer),
                duration_ms: 120,
                is_final: false,
                audio_format: "mp3",
            });
        });

        const audioElement = createdAudioElements.at(-1);
        expect(audioElement).toBeDefined();
        expect(audioElement?.playbackRate).toBe(1.25);
        expect(audioElement?.play).toHaveBeenCalled();
        expect(mediaSource?.sourceBuffer.appendBuffer).toHaveBeenCalled();
    });

    it("prefers server playbackRate embedded in chunk metadata over the local default", () => {
        const { result } = renderHook(() => useStreamingAudioPlayer({ playbackRate: 1 }));

        act(() => {
            result.current.start();
        });

        const mediaSource = createdMediaSources.at(-1);
        expect(mediaSource).toBeDefined();

        act(() => {
            mediaSource?.open();
            result.current.appendChunk({
                chunk_index: 0,
                audio: toBase64(Uint8Array.from([13, 14, 15]).buffer),
                duration_ms: 120,
                is_final: false,
                audio_format: "mp3",
                playback_rate: 1.25,
            });
        });

        const audioElement = createdAudioElements.at(-1);
        expect(audioElement?.playbackRate).toBe(1.25);
    });

    it("applies the shared playbackRate to fallback Audio playback when MediaSource is unsupported", () => {
        mediaSourceSupported = false;

        const { result } = renderHook(() => useStreamingAudioPlayer({ playbackRate: 1.5 }));

        act(() => {
            result.current.start();
            result.current.appendChunk({
                chunk_index: 0,
                audio: toBase64(Uint8Array.from([4, 5, 6]).buffer),
                duration_ms: 120,
                is_final: false,
                audio_format: "mp3",
            });
            result.current.appendChunk({
                chunk_index: 1,
                audio: toBase64(Uint8Array.from([7, 8, 9]).buffer),
                duration_ms: 120,
                is_final: true,
                audio_format: "mp3",
            });
        });

        const audioElement = createdAudioElements.at(-1);
        expect(audioElement).toBeDefined();
        expect(audioElement?.playbackRate).toBe(1.5);
        expect(audioElement?.play).toHaveBeenCalled();
    });

    it("applies the shared playbackRate to PCM Web Audio sources", () => {
        const { result } = renderHook(() => useStreamingAudioPlayer({ playbackRate: 0.75 }));

        const pcmSamples = new Int16Array([0, 4096, -4096, 2048]);

        act(() => {
            result.current.appendChunk({
                chunk_index: 0,
                audio: toBase64(pcmSamples.buffer),
                duration_ms: 100,
                is_final: false,
                audio_format: "pcm16",
                sample_rate: 24000,
            });
        });

        const pcmSource = createdPcmSources.at(-1);
        expect(pcmSource).toBeDefined();
        expect(pcmSource?.playbackRate.value).toBe(0.75);
        expect(pcmSource?.start).toHaveBeenCalledWith(0);
    });

    it("falls back to 1.0x when playbackRate input is malformed", () => {
        const { result } = renderHook(() => useStreamingAudioPlayer({ playbackRate: Number.NaN }));

        act(() => {
            result.current.start();
        });

        const mediaSource = createdMediaSources.at(-1);
        expect(mediaSource).toBeDefined();

        act(() => {
            mediaSource?.open();
            result.current.appendChunk({
                chunk_index: 0,
                audio: toBase64(Uint8Array.from([10, 11, 12]).buffer),
                duration_ms: 80,
                is_final: false,
                audio_format: "mp3",
            });
        });

        const audioElement = createdAudioElements.at(-1);
        expect(audioElement?.playbackRate).toBe(1);
    });
});
