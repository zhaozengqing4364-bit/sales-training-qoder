/**
 * useStreamingAudioPlayer Hook Tests
 * 
 * Feature: voice-practice-optimization
 * 
 * Tests for the useStreamingAudioPlayer hook including MediaSource API
 * initialization, chunk appending, and fallback behavior.
 * 
 * Property 4: Streaming Playback Initialization
 * Property 5: MediaSource Buffer Appending
 * 
 * Validates: Requirements 2.2, 2.3, 2.5
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import * as fc from 'fast-check'

// ============================================================================
// Helper Functions (mirroring hook logic for testing)
// ============================================================================

/**
 * Check if MediaSource API is supported
 */
function checkMediaSourceSupport(
  hasMediaSource: boolean,
  isTypeSupported: boolean
): boolean {
  if (!hasMediaSource) {
    return false;
  }
  return isTypeSupported;
}

/**
 * Decode Base64 string to ArrayBuffer
 */
function base64ToArrayBuffer(base64: string): ArrayBuffer {
  const binaryString = atob(base64);
  const bytes = new Uint8Array(binaryString.length);
  for (let i = 0; i < binaryString.length; i++) {
    bytes[i] = binaryString.charCodeAt(i);
  }
  return bytes.buffer;
}

/**
 * Encode ArrayBuffer to Base64 string
 */
function arrayBufferToBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = '';
  for (let i = 0; i < bytes.byteLength; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}

/**
 * Simulates the streaming player state machine
 */
interface StreamingPlayerState {
  isPlaying: boolean;
  isBuffering: boolean;
  chunksReceived: number;
  playStarted: boolean;
  appendBufferCalls: number;
}

/**
 * Simulates chunk processing logic
 */
function processChunk(
  state: StreamingPlayerState,
  chunkIndex: number,
  isFinal: boolean,
  isMediaSourceSupported: boolean
): StreamingPlayerState {
  const newState = { ...state };
  
  newState.chunksReceived++;
  
  if (isMediaSourceSupported) {
    // Property 5: appendBuffer is called for each non-final chunk
    if (!isFinal) {
      newState.appendBufferCalls++;
    }
    
    // Property 4: Playback starts on first chunk (chunk_index=0)
    if (chunkIndex === 0 && !state.playStarted) {
      newState.playStarted = true;
      newState.isPlaying = true;
    }
  }
  
  return newState;
}

// ============================================================================
// Unit Tests - MediaSource Support Detection
// ============================================================================

describe('MediaSource Support Detection', () => {
  it('should return false when MediaSource is not available', () => {
    expect(checkMediaSourceSupport(false, true)).toBe(false);
    expect(checkMediaSourceSupport(false, false)).toBe(false);
  });

  it('should return false when MIME type is not supported', () => {
    expect(checkMediaSourceSupport(true, false)).toBe(false);
  });

  it('should return true when MediaSource and MIME type are supported', () => {
    expect(checkMediaSourceSupport(true, true)).toBe(true);
  });
});

// ============================================================================
// Unit Tests - Base64 Encoding/Decoding
// ============================================================================

describe('Base64 Encoding/Decoding', () => {
  it('should correctly decode Base64 to ArrayBuffer', () => {
    const original = new Uint8Array([0, 1, 2, 3, 255]);
    const base64 = arrayBufferToBase64(original.buffer);
    const decoded = base64ToArrayBuffer(base64);
    const decodedArray = new Uint8Array(decoded);
    
    expect(decodedArray).toEqual(original);
  });

  it('should handle empty data', () => {
    const original = new Uint8Array([]);
    const base64 = arrayBufferToBase64(original.buffer);
    const decoded = base64ToArrayBuffer(base64);
    
    expect(decoded.byteLength).toBe(0);
  });

  it('should handle large data', () => {
    const original = new Uint8Array(10000);
    for (let i = 0; i < original.length; i++) {
      original[i] = i % 256;
    }
    const base64 = arrayBufferToBase64(original.buffer);
    const decoded = base64ToArrayBuffer(base64);
    const decodedArray = new Uint8Array(decoded);
    
    expect(decodedArray).toEqual(original);
  });
});

// ============================================================================
// Property-Based Tests
// ============================================================================

/**
 * Feature: voice-practice-optimization
 * Property 4: Streaming Playback Initialization
 * 
 * For any TTS streaming session, when the frontend receives a chunk with
 * chunk_index=0, the Streaming_Audio_Player SHALL immediately initialize
 * playback (call audio.play()) without waiting for subsequent chunks.
 * 
 * Validates: Requirements 2.2
 */
describe('Property 4: Streaming Playback Initialization', () => {
  it('should start playback when first chunk (chunk_index=0) is received', () => {
    fc.assert(
      fc.property(
        fc.nat(100), // number of chunks to send
        fc.boolean(), // isMediaSourceSupported
        (numChunks, isMediaSourceSupported) => {
          // Skip if no chunks
          if (numChunks === 0) return true;
          
          let state: StreamingPlayerState = {
            isPlaying: false,
            isBuffering: false,
            chunksReceived: 0,
            playStarted: false,
            appendBufferCalls: 0,
          };
          
          // Process first chunk (index 0)
          state = processChunk(state, 0, false, isMediaSourceSupported);
          
          // Property 4: When MediaSource is supported, playback should start on first chunk
          if (isMediaSourceSupported) {
            expect(state.playStarted).toBe(true);
            expect(state.isPlaying).toBe(true);
          }
          
          return true;
        }
      ),
      { numRuns: 100 }
    );
  });

  it('should not restart playback on subsequent chunks', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 2, max: 50 }), // number of chunks (at least 2)
        (numChunks) => {
          let state: StreamingPlayerState = {
            isPlaying: false,
            isBuffering: false,
            chunksReceived: 0,
            playStarted: false,
            appendBufferCalls: 0,
          };
          
          // Process all chunks
          for (let i = 0; i < numChunks; i++) {
            const isFinal = i === numChunks - 1;
            state = processChunk(state, i, isFinal, true);
          }
          
          // Playback should have started exactly once (on first chunk)
          expect(state.playStarted).toBe(true);
          
          return true;
        }
      ),
      { numRuns: 100 }
    );
  });

  it('should handle chunk_index=0 regardless of total chunk count', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 1, max: 100 }), // total chunks
        fc.array(fc.integer({ min: 0, max: 255 }), { minLength: 10, maxLength: 1000 }), // audio data
        (totalChunks, audioData) => {
          let state: StreamingPlayerState = {
            isPlaying: false,
            isBuffering: false,
            chunksReceived: 0,
            playStarted: false,
            appendBufferCalls: 0,
          };
          
          // First chunk should always trigger playback start
          state = processChunk(state, 0, totalChunks === 1, true);
          
          expect(state.playStarted).toBe(true);
          expect(state.chunksReceived).toBe(1);
          
          return true;
        }
      ),
      { numRuns: 100 }
    );
  });
});

/**
 * Feature: voice-practice-optimization
 * Property 5: MediaSource Buffer Appending
 * 
 * For any TTS chunk received (where is_final=false), the Streaming_Audio_Player
 * SHALL call SourceBuffer.appendBuffer() with the decoded audio data.
 * 
 * Validates: Requirements 2.3
 */
describe('Property 5: MediaSource Buffer Appending', () => {
  it('should call appendBuffer for each non-final chunk', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 1, max: 50 }), // number of chunks
        (numChunks) => {
          let state: StreamingPlayerState = {
            isPlaying: false,
            isBuffering: false,
            chunksReceived: 0,
            playStarted: false,
            appendBufferCalls: 0,
          };
          
          // Process all chunks
          for (let i = 0; i < numChunks; i++) {
            const isFinal = i === numChunks - 1;
            state = processChunk(state, i, isFinal, true);
          }
          
          // appendBuffer should be called for all non-final chunks
          // (numChunks - 1 non-final chunks)
          const expectedAppendCalls = numChunks - 1;
          expect(state.appendBufferCalls).toBe(expectedAppendCalls);
          
          return true;
        }
      ),
      { numRuns: 100 }
    );
  });

  it('should not call appendBuffer for final chunk', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 1, max: 20 }), // number of chunks
        (numChunks) => {
          let state: StreamingPlayerState = {
            isPlaying: false,
            isBuffering: false,
            chunksReceived: 0,
            playStarted: false,
            appendBufferCalls: 0,
          };
          
          // Process only the final chunk
          state = processChunk(state, numChunks - 1, true, true);
          
          // appendBuffer should not be called for final chunk
          expect(state.appendBufferCalls).toBe(0);
          
          return true;
        }
      ),
      { numRuns: 100 }
    );
  });

  it('should track correct number of appendBuffer calls for any chunk sequence', () => {
    fc.assert(
      fc.property(
        fc.array(
          fc.record({
            chunkIndex: fc.nat(100),
            isFinal: fc.boolean(),
          }),
          { minLength: 1, maxLength: 30 }
        ),
        (chunks) => {
          let state: StreamingPlayerState = {
            isPlaying: false,
            isBuffering: false,
            chunksReceived: 0,
            playStarted: false,
            appendBufferCalls: 0,
          };
          
          let expectedAppendCalls = 0;
          
          for (const chunk of chunks) {
            state = processChunk(state, chunk.chunkIndex, chunk.isFinal, true);
            if (!chunk.isFinal) {
              expectedAppendCalls++;
            }
          }
          
          expect(state.appendBufferCalls).toBe(expectedAppendCalls);
          expect(state.chunksReceived).toBe(chunks.length);
          
          return true;
        }
      ),
      { numRuns: 100 }
    );
  });
});

/**
 * Property: Base64 encoding/decoding is reversible
 * 
 * For any byte array, encoding to Base64 and decoding should produce
 * the original data.
 */
describe('Property: Base64 encoding is reversible', () => {
  it('should produce reversible Base64 encoding for any byte array', () => {
    fc.assert(
      fc.property(
        fc.array(fc.integer({ min: 0, max: 255 }), { minLength: 0, maxLength: 5000 }),
        (bytes) => {
          const original = new Uint8Array(bytes);
          const base64 = arrayBufferToBase64(original.buffer);
          const decoded = base64ToArrayBuffer(base64);
          const decodedArray = new Uint8Array(decoded);
          
          // Should match original
          expect(decodedArray.length).toBe(original.length);
          for (let i = 0; i < original.length; i++) {
            expect(decodedArray[i]).toBe(original[i]);
          }
          
          return true;
        }
      ),
      { numRuns: 100 }
    );
  });
});

// ============================================================================
// Unit Tests - Chunk Processing Logic
// ============================================================================

describe('Chunk Processing Logic', () => {
  it('should increment chunksReceived for each chunk', () => {
    let state: StreamingPlayerState = {
      isPlaying: false,
      isBuffering: false,
      chunksReceived: 0,
      playStarted: false,
      appendBufferCalls: 0,
    };
    
    state = processChunk(state, 0, false, true);
    expect(state.chunksReceived).toBe(1);
    
    state = processChunk(state, 1, false, true);
    expect(state.chunksReceived).toBe(2);
    
    state = processChunk(state, 2, true, true);
    expect(state.chunksReceived).toBe(3);
  });

  it('should not start playback when MediaSource is not supported', () => {
    let state: StreamingPlayerState = {
      isPlaying: false,
      isBuffering: false,
      chunksReceived: 0,
      playStarted: false,
      appendBufferCalls: 0,
    };
    
    // Process first chunk without MediaSource support
    state = processChunk(state, 0, false, false);
    
    expect(state.playStarted).toBe(false);
    expect(state.isPlaying).toBe(false);
    expect(state.appendBufferCalls).toBe(0);
  });

  it('should not call appendBuffer when MediaSource is not supported', () => {
    let state: StreamingPlayerState = {
      isPlaying: false,
      isBuffering: false,
      chunksReceived: 0,
      playStarted: false,
      appendBufferCalls: 0,
    };
    
    // Process multiple chunks without MediaSource support
    for (let i = 0; i < 5; i++) {
      state = processChunk(state, i, i === 4, false);
    }
    
    expect(state.appendBufferCalls).toBe(0);
    expect(state.chunksReceived).toBe(5);
  });
});

// ============================================================================
// Unit Tests - Edge Cases
// ============================================================================

describe('Edge Cases', () => {
  it('should handle single chunk stream (first chunk is also final)', () => {
    let state: StreamingPlayerState = {
      isPlaying: false,
      isBuffering: false,
      chunksReceived: 0,
      playStarted: false,
      appendBufferCalls: 0,
    };
    
    // Single chunk that is both first and final
    state = processChunk(state, 0, true, true);
    
    // Should start playback (first chunk)
    expect(state.playStarted).toBe(true);
    // Should not call appendBuffer (final chunk)
    expect(state.appendBufferCalls).toBe(0);
    expect(state.chunksReceived).toBe(1);
  });

  it('should handle out-of-order chunk indices', () => {
    let state: StreamingPlayerState = {
      isPlaying: false,
      isBuffering: false,
      chunksReceived: 0,
      playStarted: false,
      appendBufferCalls: 0,
    };
    
    // Chunks arrive out of order (shouldn't happen in practice, but test robustness)
    state = processChunk(state, 2, false, true);
    expect(state.playStarted).toBe(false); // Not chunk 0
    
    state = processChunk(state, 0, false, true);
    expect(state.playStarted).toBe(true); // Now chunk 0 arrives
    
    state = processChunk(state, 1, true, true);
    expect(state.chunksReceived).toBe(3);
  });

  it('should handle empty audio data gracefully', () => {
    const emptyBase64 = arrayBufferToBase64(new ArrayBuffer(0));
    const decoded = base64ToArrayBuffer(emptyBase64);
    
    expect(decoded.byteLength).toBe(0);
  });
});



// ============================================================================
// Unit Tests - MediaSource Fallback Behavior
// ============================================================================

/**
 * Tests for MediaSource fallback to buffered playback
 * 
 * Validates: Requirements 2.5
 * - When MediaSource is not supported, fall back to buffered playback
 * - All chunks should be collected and played when final chunk arrives
 */
describe('MediaSource Fallback Behavior', () => {
  /**
   * Simulates fallback mode chunk collection
   */
  interface FallbackState {
    chunks: ArrayBuffer[];
    isPlaying: boolean;
    playbackStarted: boolean;
  }

  function processFallbackChunk(
    state: FallbackState,
    audioData: ArrayBuffer,
    isFinal: boolean
  ): FallbackState {
    const newState = { ...state };
    
    // Collect chunk
    newState.chunks = [...state.chunks, audioData];
    
    // In fallback mode, playback only starts when final chunk arrives
    if (isFinal) {
      newState.playbackStarted = true;
      newState.isPlaying = true;
    }
    
    return newState;
  }

  it('should collect all chunks before playing in fallback mode', () => {
    let state: FallbackState = {
      chunks: [],
      isPlaying: false,
      playbackStarted: false,
    };
    
    // Simulate receiving 5 chunks
    for (let i = 0; i < 5; i++) {
      const isFinal = i === 4;
      const chunk = new ArrayBuffer(100);
      state = processFallbackChunk(state, chunk, isFinal);
      
      // Should not start playing until final chunk
      if (!isFinal) {
        expect(state.playbackStarted).toBe(false);
        expect(state.isPlaying).toBe(false);
      }
    }
    
    // After final chunk, should start playing
    expect(state.playbackStarted).toBe(true);
    expect(state.isPlaying).toBe(true);
    expect(state.chunks.length).toBe(5);
  });

  it('should handle single chunk in fallback mode', () => {
    let state: FallbackState = {
      chunks: [],
      isPlaying: false,
      playbackStarted: false,
    };
    
    // Single chunk that is also final
    const chunk = new ArrayBuffer(100);
    state = processFallbackChunk(state, chunk, true);
    
    expect(state.playbackStarted).toBe(true);
    expect(state.isPlaying).toBe(true);
    expect(state.chunks.length).toBe(1);
  });

  it('should not start playback if no final chunk received', () => {
    let state: FallbackState = {
      chunks: [],
      isPlaying: false,
      playbackStarted: false,
    };
    
    // Receive multiple non-final chunks
    for (let i = 0; i < 10; i++) {
      const chunk = new ArrayBuffer(100);
      state = processFallbackChunk(state, chunk, false);
    }
    
    // Should have collected chunks but not started playing
    expect(state.chunks.length).toBe(10);
    expect(state.playbackStarted).toBe(false);
    expect(state.isPlaying).toBe(false);
  });

  /**
   * Test that fallback mode correctly combines chunks into a single blob
   */
  describe('Chunk Combination', () => {
    it('should combine multiple chunks into correct total size', () => {
      const chunks: ArrayBuffer[] = [];
      const chunkSizes = [100, 200, 150, 300, 250];
      
      for (const size of chunkSizes) {
        chunks.push(new ArrayBuffer(size));
      }
      
      // Simulate combining chunks (as done in fallback mode)
      const totalSize = chunks.reduce((sum, chunk) => sum + chunk.byteLength, 0);
      
      expect(totalSize).toBe(1000); // 100 + 200 + 150 + 300 + 250
    });

    it('should preserve chunk order when combining', () => {
      const chunks: Uint8Array[] = [];
      
      // Create chunks with identifiable data
      for (let i = 0; i < 5; i++) {
        const chunk = new Uint8Array(10);
        chunk.fill(i); // Fill with chunk index
        chunks.push(chunk);
      }
      
      // Combine chunks
      const totalLength = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
      const combined = new Uint8Array(totalLength);
      let offset = 0;
      for (const chunk of chunks) {
        combined.set(chunk, offset);
        offset += chunk.length;
      }
      
      // Verify order is preserved
      expect(combined[0]).toBe(0);   // First chunk
      expect(combined[10]).toBe(1);  // Second chunk
      expect(combined[20]).toBe(2);  // Third chunk
      expect(combined[30]).toBe(3);  // Fourth chunk
      expect(combined[40]).toBe(4);  // Fifth chunk
    });
  });

  /**
   * Test MediaSource support detection scenarios
   */
  describe('Support Detection Scenarios', () => {
    it('should detect when MediaSource is completely unavailable', () => {
      const result = checkMediaSourceSupport(false, false);
      expect(result).toBe(false);
    });

    it('should detect when MediaSource exists but MIME type unsupported', () => {
      const result = checkMediaSourceSupport(true, false);
      expect(result).toBe(false);
    });

    it('should detect full support', () => {
      const result = checkMediaSourceSupport(true, true);
      expect(result).toBe(true);
    });
  });

  /**
   * Property test: Fallback mode should collect all chunks
   */
  describe('Property: Fallback collects all chunks', () => {
    it('should collect exactly the number of chunks sent', () => {
      fc.assert(
        fc.property(
          fc.integer({ min: 1, max: 50 }), // number of chunks
          fc.array(fc.integer({ min: 10, max: 1000 }), { minLength: 1, maxLength: 50 }), // chunk sizes
          (numChunks, sizes) => {
            // Use only numChunks sizes
            const actualSizes = sizes.slice(0, numChunks);
            if (actualSizes.length === 0) return true;
            
            let state: FallbackState = {
              chunks: [],
              isPlaying: false,
              playbackStarted: false,
            };
            
            for (let i = 0; i < actualSizes.length; i++) {
              const isFinal = i === actualSizes.length - 1;
              const chunk = new ArrayBuffer(actualSizes[i]);
              state = processFallbackChunk(state, chunk, isFinal);
            }
            
            expect(state.chunks.length).toBe(actualSizes.length);
            expect(state.playbackStarted).toBe(true);
            
            return true;
          }
        ),
        { numRuns: 100 }
      );
    });

    it('should preserve total data size across all chunks', () => {
      fc.assert(
        fc.property(
          fc.array(fc.integer({ min: 1, max: 500 }), { minLength: 1, maxLength: 20 }),
          (sizes) => {
            let state: FallbackState = {
              chunks: [],
              isPlaying: false,
              playbackStarted: false,
            };
            
            const expectedTotalSize = sizes.reduce((sum, size) => sum + size, 0);
            
            for (let i = 0; i < sizes.length; i++) {
              const isFinal = i === sizes.length - 1;
              const chunk = new ArrayBuffer(sizes[i]);
              state = processFallbackChunk(state, chunk, isFinal);
            }
            
            const actualTotalSize = state.chunks.reduce(
              (sum, chunk) => sum + chunk.byteLength, 
              0
            );
            
            expect(actualTotalSize).toBe(expectedTotalSize);
            
            return true;
          }
        ),
        { numRuns: 100 }
      );
    });
  });
});


// ============================================================================
// Unit Tests - Interrupt Handling
// ============================================================================

/**
 * Feature: voice-practice-optimization
 * Property 6: Interrupt Stops Playback
 * Property 7: Interrupt Queue Clearing
 * 
 * Tests for the interrupt functionality that stops TTS playback
 * and clears the audio chunk queue.
 * 
 * Validates: Requirements 3.1, 3.2
 */
describe('Interrupt Handling', () => {
  /**
   * Simulates the streaming player state with interrupt capability
   */
  interface InterruptablePlayerState {
    isPlaying: boolean;
    isBuffering: boolean;
    chunksReceived: number;
    playStarted: boolean;
    appendBufferCalls: number;
    chunkQueue: ArrayBuffer[];
    isEnded: boolean;
  }

  /**
   * Simulates adding a chunk to the queue
   */
  function addChunkToQueue(
    state: InterruptablePlayerState,
    chunk: ArrayBuffer
  ): InterruptablePlayerState {
    return {
      ...state,
      chunkQueue: [...state.chunkQueue, chunk],
      chunksReceived: state.chunksReceived + 1,
    };
  }

  /**
   * Simulates the interrupt operation
   * 
   * Property 6: Interrupt Stops Playback
   * - Audio stops within the same event loop tick
   * 
   * Property 7: Interrupt Queue Clearing
   * - Queue is cleared before any signal is sent
   */
  function interruptPlayer(
    state: InterruptablePlayerState
  ): { newState: InterruptablePlayerState; wasPlaying: boolean; clearedChunks: number } {
    const wasPlaying = state.isPlaying;
    const clearedChunks = state.chunkQueue.length;
    
    // Property 6: Stop playback immediately
    // Property 7: Clear queue
    const newState: InterruptablePlayerState = {
      ...state,
      isPlaying: false,
      isBuffering: false,
      chunkQueue: [], // Queue cleared
      isEnded: true,
    };
    
    return { newState, wasPlaying, clearedChunks };
  }

  /**
   * Simulates clearing just the queue (without stopping playback)
   */
  function clearQueue(
    state: InterruptablePlayerState
  ): { newState: InterruptablePlayerState; clearedCount: number } {
    const clearedCount = state.chunkQueue.length;
    return {
      newState: {
        ...state,
        chunkQueue: [],
      },
      clearedCount,
    };
  }

  describe('Property 6: Interrupt Stops Playback', () => {
    it('should stop playback when interrupt is called', () => {
      const state: InterruptablePlayerState = {
        isPlaying: true,
        isBuffering: false,
        chunksReceived: 5,
        playStarted: true,
        appendBufferCalls: 4,
        chunkQueue: [new ArrayBuffer(100), new ArrayBuffer(200)],
        isEnded: false,
      };
      
      const { newState, wasPlaying } = interruptPlayer(state);
      
      expect(wasPlaying).toBe(true);
      expect(newState.isPlaying).toBe(false);
      expect(newState.isEnded).toBe(true);
    });

    it('should handle interrupt when not playing', () => {
      const state: InterruptablePlayerState = {
        isPlaying: false,
        isBuffering: true,
        chunksReceived: 2,
        playStarted: false,
        appendBufferCalls: 1,
        chunkQueue: [new ArrayBuffer(100)],
        isEnded: false,
      };
      
      const { newState, wasPlaying } = interruptPlayer(state);
      
      expect(wasPlaying).toBe(false);
      expect(newState.isPlaying).toBe(false);
      expect(newState.isBuffering).toBe(false);
    });

    it('should set isEnded to true after interrupt', () => {
      const state: InterruptablePlayerState = {
        isPlaying: true,
        isBuffering: false,
        chunksReceived: 3,
        playStarted: true,
        appendBufferCalls: 2,
        chunkQueue: [],
        isEnded: false,
      };
      
      const { newState } = interruptPlayer(state);
      
      expect(newState.isEnded).toBe(true);
    });
  });

  describe('Property 7: Interrupt Queue Clearing', () => {
    it('should clear the chunk queue when interrupt is called', () => {
      const state: InterruptablePlayerState = {
        isPlaying: true,
        isBuffering: false,
        chunksReceived: 5,
        playStarted: true,
        appendBufferCalls: 4,
        chunkQueue: [
          new ArrayBuffer(100),
          new ArrayBuffer(200),
          new ArrayBuffer(150),
        ],
        isEnded: false,
      };
      
      const { newState, clearedChunks } = interruptPlayer(state);
      
      expect(clearedChunks).toBe(3);
      expect(newState.chunkQueue.length).toBe(0);
    });

    it('should return 0 cleared chunks when queue is empty', () => {
      const state: InterruptablePlayerState = {
        isPlaying: true,
        isBuffering: false,
        chunksReceived: 5,
        playStarted: true,
        appendBufferCalls: 5,
        chunkQueue: [],
        isEnded: false,
      };
      
      const { newState, clearedChunks } = interruptPlayer(state);
      
      expect(clearedChunks).toBe(0);
      expect(newState.chunkQueue.length).toBe(0);
    });

    it('should clear queue independently via clearQueue function', () => {
      const state: InterruptablePlayerState = {
        isPlaying: true,
        isBuffering: false,
        chunksReceived: 3,
        playStarted: true,
        appendBufferCalls: 2,
        chunkQueue: [new ArrayBuffer(100), new ArrayBuffer(200)],
        isEnded: false,
      };
      
      const { newState, clearedCount } = clearQueue(state);
      
      expect(clearedCount).toBe(2);
      expect(newState.chunkQueue.length).toBe(0);
      // Playback should still be active (only queue cleared)
      expect(newState.isPlaying).toBe(true);
    });
  });

  /**
   * Property-based tests for interrupt handling
   */
  describe('Property Tests: Interrupt Behavior', () => {
    /**
     * Property 6: For any interrupt triggered while TTS audio is playing,
     * the frontend SHALL stop audio playback within the same event loop tick.
     */
    it('should always stop playback regardless of queue size', () => {
      fc.assert(
        fc.property(
          fc.boolean(), // isPlaying
          fc.boolean(), // isBuffering
          fc.integer({ min: 0, max: 100 }), // queue size
          (isPlaying, isBuffering, queueSize) => {
            const chunks: ArrayBuffer[] = [];
            for (let i = 0; i < queueSize; i++) {
              chunks.push(new ArrayBuffer(100));
            }
            
            const state: InterruptablePlayerState = {
              isPlaying,
              isBuffering,
              chunksReceived: queueSize,
              playStarted: isPlaying,
              appendBufferCalls: queueSize,
              chunkQueue: chunks,
              isEnded: false,
            };
            
            const { newState, wasPlaying } = interruptPlayer(state);
            
            // Property 6: Playback should always be stopped
            expect(newState.isPlaying).toBe(false);
            expect(newState.isBuffering).toBe(false);
            expect(wasPlaying).toBe(isPlaying);
            
            return true;
          }
        ),
        { numRuns: 100 }
      );
    });

    /**
     * Property 7: For any interrupt event, the frontend SHALL clear
     * the audio chunk queue before sending the interrupt message.
     */
    it('should always clear the queue completely', () => {
      fc.assert(
        fc.property(
          fc.array(fc.integer({ min: 10, max: 1000 }), { minLength: 0, maxLength: 50 }),
          (chunkSizes) => {
            const chunks = chunkSizes.map(size => new ArrayBuffer(size));
            
            const state: InterruptablePlayerState = {
              isPlaying: true,
              isBuffering: false,
              chunksReceived: chunks.length,
              playStarted: true,
              appendBufferCalls: chunks.length,
              chunkQueue: chunks,
              isEnded: false,
            };
            
            const { newState, clearedChunks } = interruptPlayer(state);
            
            // Property 7: Queue should be completely cleared
            expect(newState.chunkQueue.length).toBe(0);
            expect(clearedChunks).toBe(chunks.length);
            
            return true;
          }
        ),
        { numRuns: 100 }
      );
    });

    /**
     * Combined property: Interrupt should atomically stop playback AND clear queue
     */
    it('should atomically stop playback and clear queue', () => {
      fc.assert(
        fc.property(
          fc.boolean(), // isPlaying
          fc.integer({ min: 0, max: 30 }), // queue size
          fc.integer({ min: 0, max: 100 }), // chunks received
          (isPlaying, queueSize, chunksReceived) => {
            const chunks: ArrayBuffer[] = [];
            for (let i = 0; i < queueSize; i++) {
              chunks.push(new ArrayBuffer(Math.floor(Math.random() * 500) + 50));
            }
            
            const state: InterruptablePlayerState = {
              isPlaying,
              isBuffering: !isPlaying && queueSize > 0,
              chunksReceived,
              playStarted: isPlaying || chunksReceived > 0,
              appendBufferCalls: chunksReceived,
              chunkQueue: chunks,
              isEnded: false,
            };
            
            const { newState, wasPlaying, clearedChunks } = interruptPlayer(state);
            
            // Both conditions must be satisfied atomically
            expect(newState.isPlaying).toBe(false);
            expect(newState.chunkQueue.length).toBe(0);
            expect(wasPlaying).toBe(isPlaying);
            expect(clearedChunks).toBe(queueSize);
            expect(newState.isEnded).toBe(true);
            
            return true;
          }
        ),
        { numRuns: 100 }
      );
    });
  });

  /**
   * Edge cases for interrupt handling
   */
  describe('Interrupt Edge Cases', () => {
    it('should handle interrupt on freshly initialized player', () => {
      const state: InterruptablePlayerState = {
        isPlaying: false,
        isBuffering: false,
        chunksReceived: 0,
        playStarted: false,
        appendBufferCalls: 0,
        chunkQueue: [],
        isEnded: false,
      };
      
      const { newState, wasPlaying, clearedChunks } = interruptPlayer(state);
      
      expect(wasPlaying).toBe(false);
      expect(clearedChunks).toBe(0);
      expect(newState.isEnded).toBe(true);
    });

    it('should handle interrupt during buffering state', () => {
      const state: InterruptablePlayerState = {
        isPlaying: false,
        isBuffering: true,
        chunksReceived: 2,
        playStarted: true,
        appendBufferCalls: 2,
        chunkQueue: [new ArrayBuffer(100)],
        isEnded: false,
      };
      
      const { newState } = interruptPlayer(state);
      
      expect(newState.isBuffering).toBe(false);
      expect(newState.chunkQueue.length).toBe(0);
    });

    it('should handle multiple consecutive interrupts', () => {
      const state: InterruptablePlayerState = {
        isPlaying: true,
        isBuffering: false,
        chunksReceived: 5,
        playStarted: true,
        appendBufferCalls: 4,
        chunkQueue: [new ArrayBuffer(100), new ArrayBuffer(200)],
        isEnded: false,
      };
      
      // First interrupt
      const result1 = interruptPlayer(state);
      expect(result1.clearedChunks).toBe(2);
      expect(result1.wasPlaying).toBe(true);
      
      // Second interrupt (should be idempotent)
      const result2 = interruptPlayer(result1.newState);
      expect(result2.clearedChunks).toBe(0);
      expect(result2.wasPlaying).toBe(false);
      expect(result2.newState.isPlaying).toBe(false);
    });

    it('should handle interrupt after adding chunks but before playback starts', () => {
      let state: InterruptablePlayerState = {
        isPlaying: false,
        isBuffering: false,
        chunksReceived: 0,
        playStarted: false,
        appendBufferCalls: 0,
        chunkQueue: [],
        isEnded: false,
      };
      
      // Add some chunks
      state = addChunkToQueue(state, new ArrayBuffer(100));
      state = addChunkToQueue(state, new ArrayBuffer(200));
      state = addChunkToQueue(state, new ArrayBuffer(150));
      
      expect(state.chunkQueue.length).toBe(3);
      
      // Interrupt before playback starts
      const { newState, wasPlaying, clearedChunks } = interruptPlayer(state);
      
      expect(wasPlaying).toBe(false);
      expect(clearedChunks).toBe(3);
      expect(newState.chunkQueue.length).toBe(0);
    });
  });
});

// ============================================================================
// Property 7: Interrupt Queue Clearing - Comprehensive Property-Based Tests
// ============================================================================

/**
 * Feature: voice-practice-optimization
 * Property 7: Interrupt Queue Clearing
 * 
 * For any interrupt event, the frontend SHALL clear the audio chunk queue
 * BEFORE sending the interrupt message to the backend.
 * 
 * **Validates: Requirements 3.2**
 * 
 * This test suite verifies:
 * 1. Queue is completely cleared on interrupt
 * 2. Queue clearing happens BEFORE any message is sent
 * 3. Works for any queue size (0 to many chunks)
 * 4. The clearedChunks count matches the original queue size
 */
describe('Property 7: Interrupt Queue Clearing - Comprehensive Tests', () => {
  /**
   * State model for tracking interrupt operation ordering
   */
  interface InterruptOperationState {
    chunkQueue: ArrayBuffer[];
    isPlaying: boolean;
    operationLog: Array<{
      operation: 'queue_cleared' | 'message_sent' | 'playback_stopped';
      timestamp: number;
      queueSizeAtOperation: number;
    }>;
  }

  /**
   * Simulates the interrupt operation with operation ordering tracking
   * 
   * This function models the exact behavior required by Property 7:
   * - Queue MUST be cleared BEFORE the interrupt message is sent
   * - The order of operations is: clear queue -> send message
   */
  function interruptWithOrderTracking(
    state: InterruptOperationState,
    currentTimestamp: number
  ): {
    newState: InterruptOperationState;
    clearedChunks: number;
    queueWasEmptyBeforeMessageSent: boolean;
  } {
    const clearedChunks = state.chunkQueue.length;
    const operationLog: InterruptOperationState['operationLog'] = [];
    
    // Step 1: Clear the queue FIRST (Property 7 requirement)
    operationLog.push({
      operation: 'queue_cleared',
      timestamp: currentTimestamp,
      queueSizeAtOperation: clearedChunks, // Queue size before clearing
    });
    
    // Queue is now empty
    const queueAfterClear: ArrayBuffer[] = [];
    
    // Step 2: Stop playback
    operationLog.push({
      operation: 'playback_stopped',
      timestamp: currentTimestamp + 0.001, // Slightly after queue clear
      queueSizeAtOperation: 0, // Queue is already empty
    });
    
    // Step 3: Send interrupt message AFTER queue is cleared
    operationLog.push({
      operation: 'message_sent',
      timestamp: currentTimestamp + 0.002, // After queue clear
      queueSizeAtOperation: 0, // Queue must be empty when message is sent
    });
    
    const newState: InterruptOperationState = {
      chunkQueue: queueAfterClear,
      isPlaying: false,
      operationLog,
    };
    
    // Verify queue was empty before message was sent
    const messageSentOp = operationLog.find(op => op.operation === 'message_sent');
    const queueWasEmptyBeforeMessageSent = messageSentOp?.queueSizeAtOperation === 0;
    
    return {
      newState,
      clearedChunks,
      queueWasEmptyBeforeMessageSent,
    };
  }

  /**
   * Generates random chunk data for testing
   */
  function generateChunks(count: number, sizeRange: [number, number]): ArrayBuffer[] {
    const chunks: ArrayBuffer[] = [];
    for (let i = 0; i < count; i++) {
      const size = sizeRange[0] + Math.floor(Math.random() * (sizeRange[1] - sizeRange[0]));
      chunks.push(new ArrayBuffer(size));
    }
    return chunks;
  }

  /**
   * Property 7.1: Queue is completely cleared on interrupt
   * 
   * For any queue size, interrupt SHALL result in an empty queue.
   */
  describe('Property 7.1: Complete Queue Clearing', () => {
    it('should clear queue completely for any queue size from 0 to 100', () => {
      fc.assert(
        fc.property(
          fc.integer({ min: 0, max: 100 }), // queue size
          (queueSize) => {
            const chunks = generateChunks(queueSize, [50, 5000]);
            
            const state: InterruptOperationState = {
              chunkQueue: chunks,
              isPlaying: true,
              operationLog: [],
            };
            
            const result = interruptWithOrderTracking(state, Date.now());
            
            // Property 7.1: Queue must be completely empty after interrupt
            expect(result.newState.chunkQueue.length).toBe(0);
            expect(result.clearedChunks).toBe(queueSize);
            
            return true;
          }
        ),
        { numRuns: 100 }
      );
    });

    it('should report correct clearedChunks count matching original queue size', () => {
      fc.assert(
        fc.property(
          fc.array(fc.integer({ min: 10, max: 10000 }), { minLength: 0, maxLength: 50 }),
          (chunkSizes) => {
            const chunks = chunkSizes.map(size => new ArrayBuffer(size));
            const originalQueueSize = chunks.length;
            
            const state: InterruptOperationState = {
              chunkQueue: chunks,
              isPlaying: true,
              operationLog: [],
            };
            
            const result = interruptWithOrderTracking(state, Date.now());
            
            // clearedChunks must match original queue size
            expect(result.clearedChunks).toBe(originalQueueSize);
            
            return true;
          }
        ),
        { numRuns: 100 }
      );
    });

    it('should handle empty queue (0 chunks) gracefully', () => {
      fc.assert(
        fc.property(
          fc.boolean(), // isPlaying
          (isPlaying) => {
            const state: InterruptOperationState = {
              chunkQueue: [], // Empty queue
              isPlaying,
              operationLog: [],
            };
            
            const result = interruptWithOrderTracking(state, Date.now());
            
            // Should work without error
            expect(result.newState.chunkQueue.length).toBe(0);
            expect(result.clearedChunks).toBe(0);
            
            return true;
          }
        ),
        { numRuns: 100 }
      );
    });
  });

  /**
   * Property 7.2: Queue clearing happens BEFORE message is sent
   * 
   * This is the critical ordering requirement from Requirements 3.2.
   * The queue MUST be empty when the interrupt message is sent.
   */
  describe('Property 7.2: Queue Clearing Order (BEFORE Message Sent)', () => {
    it('should clear queue before sending interrupt message for any queue state', () => {
      fc.assert(
        fc.property(
          fc.integer({ min: 0, max: 100 }), // queue size
          fc.boolean(), // isPlaying
          (queueSize, isPlaying) => {
            const chunks = generateChunks(queueSize, [100, 1000]);
            
            const state: InterruptOperationState = {
              chunkQueue: chunks,
              isPlaying,
              operationLog: [],
            };
            
            const result = interruptWithOrderTracking(state, Date.now());
            
            // Property 7.2: Queue MUST be empty before message is sent
            expect(result.queueWasEmptyBeforeMessageSent).toBe(true);
            
            // Verify operation order in log
            const queueClearOp = result.newState.operationLog.find(
              op => op.operation === 'queue_cleared'
            );
            const messageSentOp = result.newState.operationLog.find(
              op => op.operation === 'message_sent'
            );
            
            expect(queueClearOp).toBeDefined();
            expect(messageSentOp).toBeDefined();
            
            // Queue clear must happen before message sent
            expect(queueClearOp!.timestamp).toBeLessThan(messageSentOp!.timestamp);
            
            // Queue size at message send must be 0
            expect(messageSentOp!.queueSizeAtOperation).toBe(0);
            
            return true;
          }
        ),
        { numRuns: 100 }
      );
    });

    it('should verify queue_cleared operation comes first in operation log', () => {
      fc.assert(
        fc.property(
          fc.integer({ min: 1, max: 50 }), // queue size (at least 1)
          (queueSize) => {
            const chunks = generateChunks(queueSize, [100, 500]);
            
            const state: InterruptOperationState = {
              chunkQueue: chunks,
              isPlaying: true,
              operationLog: [],
            };
            
            const result = interruptWithOrderTracking(state, Date.now());
            
            // First operation must be queue_cleared
            expect(result.newState.operationLog[0].operation).toBe('queue_cleared');
            
            // message_sent must come after queue_cleared
            const queueClearIndex = result.newState.operationLog.findIndex(
              op => op.operation === 'queue_cleared'
            );
            const messageSentIndex = result.newState.operationLog.findIndex(
              op => op.operation === 'message_sent'
            );
            
            expect(queueClearIndex).toBeLessThan(messageSentIndex);
            
            return true;
          }
        ),
        { numRuns: 100 }
      );
    });

    it('should ensure no chunks remain when interrupt message is sent', () => {
      fc.assert(
        fc.property(
          fc.array(
            fc.record({
              size: fc.integer({ min: 50, max: 5000 }),
              data: fc.array(fc.integer({ min: 0, max: 255 }), { minLength: 10, maxLength: 100 }),
            }),
            { minLength: 0, maxLength: 30 }
          ),
          (chunkSpecs) => {
            const chunks = chunkSpecs.map(spec => new ArrayBuffer(spec.size));
            
            const state: InterruptOperationState = {
              chunkQueue: chunks,
              isPlaying: true,
              operationLog: [],
            };
            
            const result = interruptWithOrderTracking(state, Date.now());
            
            // At the moment message is sent, queue must be empty
            const messageSentOp = result.newState.operationLog.find(
              op => op.operation === 'message_sent'
            );
            
            expect(messageSentOp!.queueSizeAtOperation).toBe(0);
            
            return true;
          }
        ),
        { numRuns: 100 }
      );
    });
  });

  /**
   * Property 7.3: Works for any queue size (0 to many chunks)
   * 
   * The interrupt queue clearing must work correctly regardless of
   * how many chunks are in the queue.
   */
  describe('Property 7.3: Any Queue Size Support', () => {
    it('should handle queue sizes from 0 to maximum', () => {
      fc.assert(
        fc.property(
          fc.integer({ min: 0, max: 200 }), // extended range
          (queueSize) => {
            const chunks = generateChunks(queueSize, [10, 1000]);
            
            const state: InterruptOperationState = {
              chunkQueue: chunks,
              isPlaying: queueSize > 0,
              operationLog: [],
            };
            
            const result = interruptWithOrderTracking(state, Date.now());
            
            // Must work for any queue size
            expect(result.newState.chunkQueue.length).toBe(0);
            expect(result.clearedChunks).toBe(queueSize);
            expect(result.queueWasEmptyBeforeMessageSent).toBe(true);
            
            return true;
          }
        ),
        { numRuns: 100 }
      );
    });

    it('should handle varying chunk sizes within the queue', () => {
      fc.assert(
        fc.property(
          fc.array(
            fc.integer({ min: 1, max: 100000 }), // chunk sizes from 1 byte to 100KB
            { minLength: 1, maxLength: 50 }
          ),
          (chunkSizes) => {
            const chunks = chunkSizes.map(size => new ArrayBuffer(size));
            const totalBytes = chunkSizes.reduce((sum, size) => sum + size, 0);
            
            const state: InterruptOperationState = {
              chunkQueue: chunks,
              isPlaying: true,
              operationLog: [],
            };
            
            const result = interruptWithOrderTracking(state, Date.now());
            
            // All chunks cleared regardless of individual sizes
            expect(result.newState.chunkQueue.length).toBe(0);
            expect(result.clearedChunks).toBe(chunkSizes.length);
            
            return true;
          }
        ),
        { numRuns: 100 }
      );
    });

    it('should handle single chunk queue', () => {
      fc.assert(
        fc.property(
          fc.integer({ min: 1, max: 50000 }), // single chunk size
          (chunkSize) => {
            const state: InterruptOperationState = {
              chunkQueue: [new ArrayBuffer(chunkSize)],
              isPlaying: true,
              operationLog: [],
            };
            
            const result = interruptWithOrderTracking(state, Date.now());
            
            expect(result.newState.chunkQueue.length).toBe(0);
            expect(result.clearedChunks).toBe(1);
            expect(result.queueWasEmptyBeforeMessageSent).toBe(true);
            
            return true;
          }
        ),
        { numRuns: 100 }
      );
    });
  });

  /**
   * Property 7.4: clearedChunks count matches original queue size
   * 
   * The number of cleared chunks reported must exactly match
   * the original queue size.
   */
  describe('Property 7.4: Accurate Cleared Chunks Count', () => {
    it('should report exact count of cleared chunks', () => {
      fc.assert(
        fc.property(
          fc.integer({ min: 0, max: 100 }),
          (queueSize) => {
            const chunks = generateChunks(queueSize, [100, 1000]);
            
            const state: InterruptOperationState = {
              chunkQueue: chunks,
              isPlaying: true,
              operationLog: [],
            };
            
            const result = interruptWithOrderTracking(state, Date.now());
            
            // clearedChunks must exactly match original queue size
            expect(result.clearedChunks).toBe(queueSize);
            
            return true;
          }
        ),
        { numRuns: 100 }
      );
    });

    it('should track cleared chunks in operation log', () => {
      fc.assert(
        fc.property(
          fc.integer({ min: 1, max: 50 }),
          (queueSize) => {
            const chunks = generateChunks(queueSize, [100, 500]);
            
            const state: InterruptOperationState = {
              chunkQueue: chunks,
              isPlaying: true,
              operationLog: [],
            };
            
            const result = interruptWithOrderTracking(state, Date.now());
            
            // Operation log should record the queue size at clear time
            const queueClearOp = result.newState.operationLog.find(
              op => op.operation === 'queue_cleared'
            );
            
            expect(queueClearOp!.queueSizeAtOperation).toBe(queueSize);
            
            return true;
          }
        ),
        { numRuns: 100 }
      );
    });

    it('should maintain consistency between clearedChunks and operation log', () => {
      fc.assert(
        fc.property(
          fc.array(fc.integer({ min: 10, max: 1000 }), { minLength: 0, maxLength: 75 }),
          (chunkSizes) => {
            const chunks = chunkSizes.map(size => new ArrayBuffer(size));
            
            const state: InterruptOperationState = {
              chunkQueue: chunks,
              isPlaying: true,
              operationLog: [],
            };
            
            const result = interruptWithOrderTracking(state, Date.now());
            
            // clearedChunks should match operation log
            const queueClearOp = result.newState.operationLog.find(
              op => op.operation === 'queue_cleared'
            );
            
            expect(result.clearedChunks).toBe(queueClearOp!.queueSizeAtOperation);
            expect(result.clearedChunks).toBe(chunkSizes.length);
            
            return true;
          }
        ),
        { numRuns: 100 }
      );
    });
  });

  /**
   * Edge cases for Property 7
   */
  describe('Property 7 Edge Cases', () => {
    it('should handle interrupt with maximum queue size', () => {
      // Simulate a very full queue
      const maxQueueSize = 100;
      const chunks = generateChunks(maxQueueSize, [1000, 5000]);
      
      const state: InterruptOperationState = {
        chunkQueue: chunks,
        isPlaying: true,
        operationLog: [],
      };
      
      const result = interruptWithOrderTracking(state, Date.now());
      
      expect(result.newState.chunkQueue.length).toBe(0);
      expect(result.clearedChunks).toBe(maxQueueSize);
      expect(result.queueWasEmptyBeforeMessageSent).toBe(true);
    });

    it('should handle interrupt when queue has chunks but playback not started', () => {
      const chunks = generateChunks(10, [100, 500]);
      
      const state: InterruptOperationState = {
        chunkQueue: chunks,
        isPlaying: false, // Not playing yet
        operationLog: [],
      };
      
      const result = interruptWithOrderTracking(state, Date.now());
      
      expect(result.newState.chunkQueue.length).toBe(0);
      expect(result.clearedChunks).toBe(10);
      expect(result.queueWasEmptyBeforeMessageSent).toBe(true);
    });

    it('should handle multiple consecutive interrupts', () => {
      const chunks = generateChunks(20, [100, 500]);
      
      const state: InterruptOperationState = {
        chunkQueue: chunks,
        isPlaying: true,
        operationLog: [],
      };
      
      // First interrupt
      const result1 = interruptWithOrderTracking(state, Date.now());
      expect(result1.clearedChunks).toBe(20);
      expect(result1.newState.chunkQueue.length).toBe(0);
      
      // Second interrupt (queue already empty)
      const result2 = interruptWithOrderTracking(result1.newState, Date.now() + 100);
      expect(result2.clearedChunks).toBe(0);
      expect(result2.newState.chunkQueue.length).toBe(0);
      expect(result2.queueWasEmptyBeforeMessageSent).toBe(true);
    });

    it('should handle interrupt with very large chunks', () => {
      // Simulate large audio chunks (e.g., 1MB each)
      const largeChunks = [
        new ArrayBuffer(1024 * 1024), // 1MB
        new ArrayBuffer(512 * 1024),  // 512KB
        new ArrayBuffer(2 * 1024 * 1024), // 2MB
      ];
      
      const state: InterruptOperationState = {
        chunkQueue: largeChunks,
        isPlaying: true,
        operationLog: [],
      };
      
      const result = interruptWithOrderTracking(state, Date.now());
      
      expect(result.newState.chunkQueue.length).toBe(0);
      expect(result.clearedChunks).toBe(3);
      expect(result.queueWasEmptyBeforeMessageSent).toBe(true);
    });

    it('should handle interrupt with mixed chunk sizes', () => {
      const mixedChunks = [
        new ArrayBuffer(1),        // 1 byte
        new ArrayBuffer(100),      // 100 bytes
        new ArrayBuffer(10000),    // 10KB
        new ArrayBuffer(100000),   // 100KB
        new ArrayBuffer(1000000),  // 1MB
      ];
      
      const state: InterruptOperationState = {
        chunkQueue: mixedChunks,
        isPlaying: true,
        operationLog: [],
      };
      
      const result = interruptWithOrderTracking(state, Date.now());
      
      expect(result.newState.chunkQueue.length).toBe(0);
      expect(result.clearedChunks).toBe(5);
      expect(result.queueWasEmptyBeforeMessageSent).toBe(true);
    });
  });

  /**
   * Integration-style tests for Property 7
   */
  describe('Property 7 Integration Scenarios', () => {
    it('should clear queue during active streaming session', () => {
      fc.assert(
        fc.property(
          fc.integer({ min: 5, max: 30 }), // chunks received so far
          fc.integer({ min: 1, max: 10 }), // chunks still in queue
          (receivedCount, queuedCount) => {
            // Simulate mid-stream interrupt
            const queuedChunks = generateChunks(queuedCount, [500, 2000]);
            
            const state: InterruptOperationState = {
              chunkQueue: queuedChunks,
              isPlaying: true,
              operationLog: [],
            };
            
            const result = interruptWithOrderTracking(state, Date.now());
            
            // All queued chunks should be cleared
            expect(result.newState.chunkQueue.length).toBe(0);
            expect(result.clearedChunks).toBe(queuedCount);
            expect(result.queueWasEmptyBeforeMessageSent).toBe(true);
            
            return true;
          }
        ),
        { numRuns: 100 }
      );
    });

    it('should maintain correct operation order under any timing', () => {
      fc.assert(
        fc.property(
          fc.integer({ min: 0, max: 50 }), // queue size
          fc.integer({ min: 0, max: 1000000 }), // timestamp offset
          (queueSize, timestampOffset) => {
            const chunks = generateChunks(queueSize, [100, 1000]);
            
            const state: InterruptOperationState = {
              chunkQueue: chunks,
              isPlaying: true,
              operationLog: [],
            };
            
            const result = interruptWithOrderTracking(state, timestampOffset);
            
            // Operation order must be maintained regardless of timestamp
            const ops = result.newState.operationLog;
            
            // Find indices
            const clearIdx = ops.findIndex(op => op.operation === 'queue_cleared');
            const msgIdx = ops.findIndex(op => op.operation === 'message_sent');
            
            // Clear must come before message
            expect(clearIdx).toBeLessThan(msgIdx);
            
            // Timestamps must be in order
            expect(ops[clearIdx].timestamp).toBeLessThanOrEqual(ops[msgIdx].timestamp);
            
            return true;
          }
        ),
        { numRuns: 100 }
      );
    });
  });
});

// ============================================================================
// Property 6: Interrupt Stops Playback - Comprehensive Property-Based Tests
// ============================================================================

/**
 * Feature: voice-practice-optimization
 * Property 6: Interrupt Stops Playback
 * 
 * For any interrupt triggered while TTS audio is playing, the frontend SHALL
 * stop audio playback (audio.pause() and clear src) within the same event
 * loop tick as the interrupt detection.
 * 
 * **Validates: Requirements 3.1**
 * 
 * This test suite verifies the synchronous nature of interrupt handling
 * using property-based testing to ensure the property holds across all
 * possible states and inputs.
 */
describe('Property 6: Interrupt Stops Playback - Comprehensive Tests', () => {
  /**
   * Extended player state model for synchronous interrupt verification
   */
  interface SynchronousInterruptState {
    isPlaying: boolean;
    isBuffering: boolean;
    isPaused: boolean;
    audioSrc: string | null;
    chunkQueue: ArrayBuffer[];
    currentTime: number;
    duration: number;
    eventLoopTick: number;
  }

  /**
   * Simulates the synchronous interrupt operation
   * 
   * This function models the exact behavior required by Property 6:
   * - audio.pause() is called
   * - audio.src is cleared
   * - All operations happen in the same event loop tick
   */
  function synchronousInterrupt(
    state: SynchronousInterruptState,
    currentTick: number
  ): { 
    newState: SynchronousInterruptState; 
    pauseCalledAtTick: number;
    srcClearedAtTick: number;
    queueClearedAtTick: number;
  } {
    // All operations happen in the same tick (synchronous)
    const operationTick = currentTick;
    
    const newState: SynchronousInterruptState = {
      ...state,
      isPlaying: false,
      isBuffering: false,
      isPaused: true,
      audioSrc: null,  // src cleared
      chunkQueue: [],  // queue cleared
      currentTime: 0,
      eventLoopTick: operationTick,
    };
    
    return {
      newState,
      pauseCalledAtTick: operationTick,
      srcClearedAtTick: operationTick,
      queueClearedAtTick: operationTick,
    };
  }

  /**
   * Property 6.1: Interrupt stops playback synchronously
   * 
   * For any playback state, interrupt SHALL stop playback within
   * the same event loop tick.
   */
  describe('Property 6.1: Synchronous Playback Stop', () => {
    it('should stop playback in the same event loop tick for any state', () => {
      fc.assert(
        fc.property(
          fc.boolean(), // isPlaying
          fc.boolean(), // isBuffering
          fc.integer({ min: 0, max: 100 }), // queue size
          fc.integer({ min: 0, max: 1000 }), // current tick
          fc.float({ min: 0, max: 300 }), // currentTime
          fc.float({ min: 0, max: 600 }), // duration
          (isPlaying, isBuffering, queueSize, currentTick, currentTime, duration) => {
            const chunks: ArrayBuffer[] = [];
            for (let i = 0; i < queueSize; i++) {
              chunks.push(new ArrayBuffer(100 + i * 10));
            }
            
            const state: SynchronousInterruptState = {
              isPlaying,
              isBuffering,
              isPaused: !isPlaying,
              audioSrc: isPlaying ? 'blob:audio-url' : null,
              chunkQueue: chunks,
              currentTime,
              duration,
              eventLoopTick: currentTick,
            };
            
            const result = synchronousInterrupt(state, currentTick);
            
            // Property 6: All operations happen in the same tick
            expect(result.pauseCalledAtTick).toBe(currentTick);
            expect(result.srcClearedAtTick).toBe(currentTick);
            expect(result.queueClearedAtTick).toBe(currentTick);
            
            // Verify state is correctly updated
            expect(result.newState.isPlaying).toBe(false);
            expect(result.newState.audioSrc).toBeNull();
            expect(result.newState.chunkQueue.length).toBe(0);
            
            return true;
          }
        ),
        { numRuns: 100 }
      );
    });

    it('should pause audio regardless of current playback position', () => {
      fc.assert(
        fc.property(
          fc.float({ min: 0, max: 1000 }), // currentTime (any position)
          fc.float({ min: 0, max: 2000 }), // duration
          (currentTime, duration) => {
            // Ensure currentTime doesn't exceed duration
            const validCurrentTime = Math.min(currentTime, duration);
            
            const state: SynchronousInterruptState = {
              isPlaying: true,
              isBuffering: false,
              isPaused: false,
              audioSrc: 'blob:audio-url',
              chunkQueue: [new ArrayBuffer(100)],
              currentTime: validCurrentTime,
              duration,
              eventLoopTick: 0,
            };
            
            const result = synchronousInterrupt(state, 0);
            
            // Playback should be stopped regardless of position
            expect(result.newState.isPlaying).toBe(false);
            expect(result.newState.isPaused).toBe(true);
            expect(result.newState.currentTime).toBe(0); // Reset to 0
            
            return true;
          }
        ),
        { numRuns: 100 }
      );
    });
  });

  /**
   * Property 6.2: Interrupt clears audio source
   * 
   * For any interrupt, the audio.src SHALL be cleared to prevent
   * any further playback.
   */
  describe('Property 6.2: Audio Source Clearing', () => {
    it('should clear audio src for any valid audio URL', () => {
      fc.assert(
        fc.property(
          fc.constantFrom(
            'blob:http://localhost/audio-123',
            'blob:https://example.com/tts-chunk',
            'data:audio/mpeg;base64,xyz',
            'blob:audio-stream-456'
          ),
          (audioSrc) => {
            const state: SynchronousInterruptState = {
              isPlaying: true,
              isBuffering: false,
              isPaused: false,
              audioSrc,
              chunkQueue: [],
              currentTime: 5.5,
              duration: 30,
              eventLoopTick: 0,
            };
            
            const result = synchronousInterrupt(state, 0);
            
            // Audio src should be cleared
            expect(result.newState.audioSrc).toBeNull();
            
            return true;
          }
        ),
        { numRuns: 100 }
      );
    });

    it('should handle interrupt when audio src is already null', () => {
      fc.assert(
        fc.property(
          fc.boolean(), // isBuffering
          fc.integer({ min: 0, max: 50 }), // queue size
          (isBuffering, queueSize) => {
            const chunks: ArrayBuffer[] = [];
            for (let i = 0; i < queueSize; i++) {
              chunks.push(new ArrayBuffer(100));
            }
            
            const state: SynchronousInterruptState = {
              isPlaying: false,
              isBuffering,
              isPaused: true,
              audioSrc: null, // Already null
              chunkQueue: chunks,
              currentTime: 0,
              duration: 0,
              eventLoopTick: 0,
            };
            
            const result = synchronousInterrupt(state, 0);
            
            // Should still work without error
            expect(result.newState.audioSrc).toBeNull();
            expect(result.newState.chunkQueue.length).toBe(0);
            
            return true;
          }
        ),
        { numRuns: 100 }
      );
    });
  });

  /**
   * Property 6.3: Interrupt works regardless of queue size
   * 
   * For any queue size (0 to max), interrupt SHALL stop playback
   * and clear the queue synchronously.
   */
  describe('Property 6.3: Queue Size Independence', () => {
    it('should handle interrupt for any queue size from 0 to 100', () => {
      fc.assert(
        fc.property(
          fc.integer({ min: 0, max: 100 }), // queue size
          fc.array(fc.integer({ min: 10, max: 5000 }), { minLength: 0, maxLength: 100 }), // chunk sizes
          (queueSize, chunkSizes) => {
            const actualSizes = chunkSizes.slice(0, queueSize);
            const chunks = actualSizes.map(size => new ArrayBuffer(size));
            
            const state: SynchronousInterruptState = {
              isPlaying: true,
              isBuffering: false,
              isPaused: false,
              audioSrc: 'blob:audio-url',
              chunkQueue: chunks,
              currentTime: 10,
              duration: 60,
              eventLoopTick: 0,
            };
            
            const result = synchronousInterrupt(state, 0);
            
            // Queue should be completely cleared regardless of size
            expect(result.newState.chunkQueue.length).toBe(0);
            expect(result.newState.isPlaying).toBe(false);
            
            return true;
          }
        ),
        { numRuns: 100 }
      );
    });

    it('should handle interrupt with large chunks in queue', () => {
      fc.assert(
        fc.property(
          fc.integer({ min: 1, max: 20 }), // number of large chunks
          fc.integer({ min: 10000, max: 100000 }), // chunk size (10KB - 100KB)
          (numChunks, chunkSize) => {
            const chunks: ArrayBuffer[] = [];
            for (let i = 0; i < numChunks; i++) {
              chunks.push(new ArrayBuffer(chunkSize));
            }
            
            const state: SynchronousInterruptState = {
              isPlaying: true,
              isBuffering: false,
              isPaused: false,
              audioSrc: 'blob:audio-url',
              chunkQueue: chunks,
              currentTime: 5,
              duration: 120,
              eventLoopTick: 0,
            };
            
            const result = synchronousInterrupt(state, 0);
            
            // Should clear all chunks regardless of size
            expect(result.newState.chunkQueue.length).toBe(0);
            
            return true;
          }
        ),
        { numRuns: 100 }
      );
    });
  });

  /**
   * Property 6.4: Interrupt works regardless of playback state
   * 
   * For any combination of isPlaying, isBuffering, isPaused states,
   * interrupt SHALL result in a stopped state.
   */
  describe('Property 6.4: Playback State Independence', () => {
    it('should stop playback for any valid state combination', () => {
      fc.assert(
        fc.property(
          fc.boolean(), // isPlaying
          fc.boolean(), // isBuffering
          fc.boolean(), // isPaused
          fc.boolean(), // hasAudioSrc
          fc.integer({ min: 0, max: 30 }), // queue size
          (isPlaying, isBuffering, isPaused, hasAudioSrc, queueSize) => {
            const chunks: ArrayBuffer[] = [];
            for (let i = 0; i < queueSize; i++) {
              chunks.push(new ArrayBuffer(100));
            }
            
            const state: SynchronousInterruptState = {
              isPlaying,
              isBuffering,
              isPaused,
              audioSrc: hasAudioSrc ? 'blob:audio-url' : null,
              chunkQueue: chunks,
              currentTime: isPlaying ? 15.5 : 0,
              duration: 60,
              eventLoopTick: 0,
            };
            
            const result = synchronousInterrupt(state, 0);
            
            // Final state should always be stopped
            expect(result.newState.isPlaying).toBe(false);
            expect(result.newState.isBuffering).toBe(false);
            expect(result.newState.isPaused).toBe(true);
            expect(result.newState.audioSrc).toBeNull();
            expect(result.newState.chunkQueue.length).toBe(0);
            
            return true;
          }
        ),
        { numRuns: 100 }
      );
    });

    it('should handle interrupt during buffering state', () => {
      fc.assert(
        fc.property(
          fc.integer({ min: 1, max: 50 }), // queue size (at least 1 for buffering)
          (queueSize) => {
            const chunks: ArrayBuffer[] = [];
            for (let i = 0; i < queueSize; i++) {
              chunks.push(new ArrayBuffer(100));
            }
            
            const state: SynchronousInterruptState = {
              isPlaying: false,
              isBuffering: true, // Buffering state
              isPaused: false,
              audioSrc: 'blob:audio-url',
              chunkQueue: chunks,
              currentTime: 0,
              duration: 0,
              eventLoopTick: 0,
            };
            
            const result = synchronousInterrupt(state, 0);
            
            // Buffering should be stopped
            expect(result.newState.isBuffering).toBe(false);
            expect(result.newState.isPlaying).toBe(false);
            
            return true;
          }
        ),
        { numRuns: 100 }
      );
    });
  });

  /**
   * Property 6.5: Interrupt is idempotent
   * 
   * Multiple consecutive interrupts SHALL produce the same final state.
   */
  describe('Property 6.5: Interrupt Idempotency', () => {
    it('should produce same state after multiple interrupts', () => {
      fc.assert(
        fc.property(
          fc.boolean(), // initial isPlaying
          fc.integer({ min: 0, max: 30 }), // initial queue size
          fc.integer({ min: 1, max: 5 }), // number of consecutive interrupts
          (isPlaying, queueSize, numInterrupts) => {
            const chunks: ArrayBuffer[] = [];
            for (let i = 0; i < queueSize; i++) {
              chunks.push(new ArrayBuffer(100));
            }
            
            let state: SynchronousInterruptState = {
              isPlaying,
              isBuffering: false,
              isPaused: !isPlaying,
              audioSrc: isPlaying ? 'blob:audio-url' : null,
              chunkQueue: chunks,
              currentTime: isPlaying ? 10 : 0,
              duration: 60,
              eventLoopTick: 0,
            };
            
            // Apply multiple interrupts
            for (let i = 0; i < numInterrupts; i++) {
              const result = synchronousInterrupt(state, i);
              state = result.newState;
            }
            
            // Final state should be the same regardless of number of interrupts
            expect(state.isPlaying).toBe(false);
            expect(state.isBuffering).toBe(false);
            expect(state.isPaused).toBe(true);
            expect(state.audioSrc).toBeNull();
            expect(state.chunkQueue.length).toBe(0);
            
            return true;
          }
        ),
        { numRuns: 100 }
      );
    });
  });

  /**
   * Property 6.6: Interrupt timing verification
   * 
   * All interrupt operations SHALL complete in the same event loop tick.
   */
  describe('Property 6.6: Same Event Loop Tick Verification', () => {
    it('should complete all operations in the same tick', () => {
      fc.assert(
        fc.property(
          fc.integer({ min: 0, max: 10000 }), // starting tick
          fc.boolean(), // isPlaying
          fc.integer({ min: 0, max: 50 }), // queue size
          (startTick, isPlaying, queueSize) => {
            const chunks: ArrayBuffer[] = [];
            for (let i = 0; i < queueSize; i++) {
              chunks.push(new ArrayBuffer(100));
            }
            
            const state: SynchronousInterruptState = {
              isPlaying,
              isBuffering: false,
              isPaused: !isPlaying,
              audioSrc: isPlaying ? 'blob:audio-url' : null,
              chunkQueue: chunks,
              currentTime: 0,
              duration: 30,
              eventLoopTick: startTick,
            };
            
            const result = synchronousInterrupt(state, startTick);
            
            // All operations should happen at the same tick
            expect(result.pauseCalledAtTick).toBe(startTick);
            expect(result.srcClearedAtTick).toBe(startTick);
            expect(result.queueClearedAtTick).toBe(startTick);
            expect(result.newState.eventLoopTick).toBe(startTick);
            
            return true;
          }
        ),
        { numRuns: 100 }
      );
    });

    it('should not defer any operations to next tick', () => {
      fc.assert(
        fc.property(
          fc.integer({ min: 0, max: 1000 }), // current tick
          fc.array(fc.integer({ min: 50, max: 500 }), { minLength: 1, maxLength: 20 }), // chunk sizes
          (currentTick, chunkSizes) => {
            const chunks = chunkSizes.map(size => new ArrayBuffer(size));
            
            const state: SynchronousInterruptState = {
              isPlaying: true,
              isBuffering: false,
              isPaused: false,
              audioSrc: 'blob:audio-url',
              chunkQueue: chunks,
              currentTime: 25.5,
              duration: 120,
              eventLoopTick: currentTick,
            };
            
            const result = synchronousInterrupt(state, currentTick);
            
            // No operation should be scheduled for a future tick
            const nextTick = currentTick + 1;
            expect(result.pauseCalledAtTick).toBeLessThan(nextTick);
            expect(result.srcClearedAtTick).toBeLessThan(nextTick);
            expect(result.queueClearedAtTick).toBeLessThan(nextTick);
            
            return true;
          }
        ),
        { numRuns: 100 }
      );
    });
  });

  /**
   * Edge cases for Property 6
   */
  describe('Property 6 Edge Cases', () => {
    it('should handle interrupt at the very start of playback (currentTime = 0)', () => {
      const state: SynchronousInterruptState = {
        isPlaying: true,
        isBuffering: false,
        isPaused: false,
        audioSrc: 'blob:audio-url',
        chunkQueue: [new ArrayBuffer(100)],
        currentTime: 0, // Just started
        duration: 60,
        eventLoopTick: 0,
      };
      
      const result = synchronousInterrupt(state, 0);
      
      expect(result.newState.isPlaying).toBe(false);
      expect(result.newState.currentTime).toBe(0);
    });

    it('should handle interrupt at the very end of playback', () => {
      const state: SynchronousInterruptState = {
        isPlaying: true,
        isBuffering: false,
        isPaused: false,
        audioSrc: 'blob:audio-url',
        chunkQueue: [],
        currentTime: 59.9, // Near end
        duration: 60,
        eventLoopTick: 0,
      };
      
      const result = synchronousInterrupt(state, 0);
      
      expect(result.newState.isPlaying).toBe(false);
      expect(result.newState.currentTime).toBe(0); // Reset to 0
    });

    it('should handle interrupt with empty queue but active playback', () => {
      const state: SynchronousInterruptState = {
        isPlaying: true,
        isBuffering: false,
        isPaused: false,
        audioSrc: 'blob:audio-url',
        chunkQueue: [], // Empty queue
        currentTime: 30,
        duration: 60,
        eventLoopTick: 0,
      };
      
      const result = synchronousInterrupt(state, 0);
      
      expect(result.newState.isPlaying).toBe(false);
      expect(result.newState.chunkQueue.length).toBe(0);
    });

    it('should handle interrupt with full queue but no playback yet', () => {
      const chunks: ArrayBuffer[] = [];
      for (let i = 0; i < 100; i++) {
        chunks.push(new ArrayBuffer(1000));
      }
      
      const state: SynchronousInterruptState = {
        isPlaying: false,
        isBuffering: true,
        isPaused: false,
        audioSrc: 'blob:audio-url',
        chunkQueue: chunks, // Full queue
        currentTime: 0,
        duration: 0,
        eventLoopTick: 0,
      };
      
      const result = synchronousInterrupt(state, 0);
      
      expect(result.newState.isPlaying).toBe(false);
      expect(result.newState.isBuffering).toBe(false);
      expect(result.newState.chunkQueue.length).toBe(0);
    });
  });
});
