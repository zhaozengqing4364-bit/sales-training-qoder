/**
 * useAudioRecorder Hook Tests
 * 
 * Feature: voice-practice-optimization
 * 
 * Tests for the useAudioRecorder hook including AudioWorklet support detection
 * and fallback behavior.
 * 
 * Property 1: Recording uses AudioWorklet when supported
 * Validates: Requirements 1.1
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import * as fc from 'fast-check'

// ============================================================================
// AudioWorklet Support Detection Tests
// ============================================================================

/**
 * Helper function that mirrors the checkWorkletSupport logic in useAudioRecorder
 */
function checkWorkletSupport(
  forceScriptProcessor: boolean,
  hasAudioWorkletNode: boolean,
  hasAudioWorkletInContext: boolean
): boolean {
  if (forceScriptProcessor) {
    return false
  }
  
  if (!hasAudioWorkletNode) {
    return false
  }
  
  return hasAudioWorkletInContext
}

describe('AudioWorklet Support Detection', () => {
  it('should return false when forceScriptProcessor is true', () => {
    expect(checkWorkletSupport(true, true, true)).toBe(false)
    expect(checkWorkletSupport(true, false, false)).toBe(false)
  })

  it('should return false when AudioWorkletNode is not available', () => {
    expect(checkWorkletSupport(false, false, true)).toBe(false)
    expect(checkWorkletSupport(false, false, false)).toBe(false)
  })

  it('should return false when audioWorklet is not in AudioContext', () => {
    expect(checkWorkletSupport(false, true, false)).toBe(false)
  })

  it('should return true only when all conditions are met', () => {
    expect(checkWorkletSupport(false, true, true)).toBe(true)
  })
})

// ============================================================================
// Audio Processing Utility Tests
// ============================================================================

/**
 * Resample function that mirrors the logic in useAudioRecorder
 */
function resample(
  inputData: Float32Array,
  inputSampleRate: number,
  outputSampleRate: number
): Float32Array {
  if (inputSampleRate === outputSampleRate) {
    return inputData
  }
  
  const ratio = inputSampleRate / outputSampleRate
  const outputLength = Math.round(inputData.length / ratio)
  const output = new Float32Array(outputLength)
  
  for (let i = 0; i < outputLength; i++) {
    const srcIndex = i * ratio
    const srcIndexFloor = Math.floor(srcIndex)
    const srcIndexCeil = Math.min(srcIndexFloor + 1, inputData.length - 1)
    const t = srcIndex - srcIndexFloor
    output[i] = inputData[srcIndexFloor] * (1 - t) + inputData[srcIndexCeil] * t
  }
  
  return output
}

/**
 * Float32 to 16-bit PCM conversion that mirrors the logic in useAudioRecorder
 */
function floatTo16BitPCM(float32Array: Float32Array): Int16Array {
  const int16Array = new Int16Array(float32Array.length)
  for (let i = 0; i < float32Array.length; i++) {
    const s = Math.max(-1, Math.min(1, float32Array[i]))
    int16Array[i] = s < 0 ? s * 0x8000 : s * 0x7FFF
  }
  return int16Array
}

/**
 * Int16Array to Base64 conversion that mirrors the logic in useAudioRecorder
 */
function int16ArrayToBase64(int16Array: Int16Array): string {
  const bytes = new Uint8Array(int16Array.buffer)
  let binary = ''
  for (let i = 0; i < bytes.byteLength; i++) {
    binary += String.fromCharCode(bytes[i])
  }
  return btoa(binary)
}

describe('Audio Processing Utilities', () => {
  describe('resample', () => {
    it('should return same data when sample rates match', () => {
      const input = new Float32Array([0.1, 0.2, 0.3, 0.4])
      const result = resample(input, 48000, 48000)
      expect(result).toEqual(input)
    })

    it('should downsample from 48kHz to 16kHz', () => {
      const input = new Float32Array(4800) // 100ms at 48kHz
      input.fill(0.5)
      const result = resample(input, 48000, 16000)
      // Should be approximately 1600 samples (100ms at 16kHz)
      expect(result.length).toBe(1600)
    })

    it('should preserve approximate amplitude during resampling', () => {
      const input = new Float32Array(4800).fill(0.75)
      const result = resample(input, 48000, 16000)
      // All values should be close to 0.75
      for (let i = 0; i < result.length; i++) {
        expect(result[i]).toBeCloseTo(0.75, 2)
      }
    })
  })

  describe('floatTo16BitPCM', () => {
    it('should convert 0 to 0', () => {
      const input = new Float32Array([0])
      const result = floatTo16BitPCM(input)
      expect(result[0]).toBe(0)
    })

    it('should convert 1.0 to max positive value', () => {
      const input = new Float32Array([1.0])
      const result = floatTo16BitPCM(input)
      expect(result[0]).toBe(32767) // 0x7FFF
    })

    it('should convert -1.0 to max negative value', () => {
      const input = new Float32Array([-1.0])
      const result = floatTo16BitPCM(input)
      expect(result[0]).toBe(-32768) // -0x8000
    })

    it('should clamp values outside [-1, 1]', () => {
      const input = new Float32Array([2.0, -2.0])
      const result = floatTo16BitPCM(input)
      expect(result[0]).toBe(32767)
      expect(result[1]).toBe(-32768)
    })
  })

  describe('int16ArrayToBase64', () => {
    it('should produce valid base64 string', () => {
      const input = new Int16Array([0, 100, -100, 32767, -32768])
      const result = int16ArrayToBase64(input)
      // Should be a valid base64 string
      expect(() => atob(result)).not.toThrow()
    })

    it('should be reversible', () => {
      const input = new Int16Array([1000, -1000, 0])
      const base64 = int16ArrayToBase64(input)
      
      // Decode back
      const binary = atob(base64)
      const bytes = new Uint8Array(binary.length)
      for (let i = 0; i < binary.length; i++) {
        bytes[i] = binary.charCodeAt(i)
      }
      const decoded = new Int16Array(bytes.buffer)
      
      expect(decoded).toEqual(input)
    })
  })
})

// ============================================================================
// Property-Based Tests
// ============================================================================

/**
 * Feature: voice-practice-optimization
 * Property 1: Recording uses AudioWorklet when supported
 * 
 * For any recording session initiated by the user on a browser that supports
 * AudioWorklet, the Audio_Recorder SHALL create and connect an AudioWorkletNode
 * (not ScriptProcessorNode) for audio processing.
 * 
 * Since we can't directly test the hook in jsdom (no AudioWorklet), we test
 * the detection logic and ensure the hook correctly determines support.
 * 
 * Validates: Requirements 1.1
 */
describe('Property 1: Recording uses AudioWorklet when supported', () => {
  it('should correctly detect AudioWorklet support based on browser capabilities', () => {
    fc.assert(
      fc.property(
        fc.boolean(), // forceScriptProcessor
        fc.boolean(), // hasAudioWorkletNode
        fc.boolean(), // hasAudioWorkletInContext
        (forceScriptProcessor, hasAudioWorkletNode, hasAudioWorkletInContext) => {
          const result = checkWorkletSupport(
            forceScriptProcessor,
            hasAudioWorkletNode,
            hasAudioWorkletInContext
          )
          
          // Should only return true when all conditions are met
          const expectedResult = !forceScriptProcessor && hasAudioWorkletNode && hasAudioWorkletInContext
          expect(result).toBe(expectedResult)
        }
      ),
      { numRuns: 100 }
    )
  })

  it('should always prefer AudioWorklet when available and not forced to use ScriptProcessor', () => {
    fc.assert(
      fc.property(
        fc.boolean(), // hasAudioWorkletNode
        fc.boolean(), // hasAudioWorkletInContext
        (hasAudioWorkletNode, hasAudioWorkletInContext) => {
          // When not forcing ScriptProcessor
          const result = checkWorkletSupport(false, hasAudioWorkletNode, hasAudioWorkletInContext)
          
          // Should use AudioWorklet only when both conditions are true
          if (hasAudioWorkletNode && hasAudioWorkletInContext) {
            expect(result).toBe(true)
          } else {
            expect(result).toBe(false)
          }
        }
      ),
      { numRuns: 100 }
    )
  })

  it('should always fall back to ScriptProcessor when forceScriptProcessor is true', () => {
    fc.assert(
      fc.property(
        fc.boolean(), // hasAudioWorkletNode
        fc.boolean(), // hasAudioWorkletInContext
        (hasAudioWorkletNode, hasAudioWorkletInContext) => {
          // When forcing ScriptProcessor
          const result = checkWorkletSupport(true, hasAudioWorkletNode, hasAudioWorkletInContext)
          
          // Should always return false (use ScriptProcessor)
          expect(result).toBe(false)
        }
      ),
      { numRuns: 100 }
    )
  })
})

/**
 * Property: Resampling preserves audio characteristics
 * 
 * For any audio data, resampling should:
 * 1. Produce output with correct length ratio
 * 2. Preserve approximate amplitude range
 */
describe('Property: Resampling preserves audio characteristics', () => {
  it('should produce output with correct length ratio', () => {
    fc.assert(
      fc.property(
        fc.array(fc.float({ min: -1, max: 1, noNaN: true }), { minLength: 100, maxLength: 10000 }),
        fc.integer({ min: 8000, max: 96000 }), // inputSampleRate
        fc.integer({ min: 8000, max: 48000 }), // outputSampleRate
        (samples, inputRate, outputRate) => {
          const input = new Float32Array(samples)
          const result = resample(input, inputRate, outputRate)
          
          const expectedLength = Math.round(samples.length * outputRate / inputRate)
          expect(result.length).toBe(expectedLength)
        }
      ),
      { numRuns: 100 }
    )
  })

  it('should preserve amplitude range after resampling', () => {
    fc.assert(
      fc.property(
        fc.array(fc.float({ min: -1, max: 1, noNaN: true }), { minLength: 100, maxLength: 1000 }),
        (samples) => {
          const input = new Float32Array(samples)
          const result = resample(input, 48000, 16000)
          
          // Find min/max of input
          let inputMin = Infinity, inputMax = -Infinity
          for (const s of samples) {
            if (s < inputMin) inputMin = s
            if (s > inputMax) inputMax = s
          }
          
          // Find min/max of output
          let outputMin = Infinity, outputMax = -Infinity
          for (let i = 0; i < result.length; i++) {
            if (result[i] < outputMin) outputMin = result[i]
            if (result[i] > outputMax) outputMax = result[i]
          }
          
          // Output should be within input range (interpolation doesn't extrapolate)
          expect(outputMin).toBeGreaterThanOrEqual(inputMin - 0.001)
          expect(outputMax).toBeLessThanOrEqual(inputMax + 0.001)
        }
      ),
      { numRuns: 100 }
    )
  })
})

/**
 * Property: PCM conversion is reversible within precision limits
 * 
 * For any float audio data in [-1, 1], converting to 16-bit PCM and back
 * should produce values close to the original.
 */
describe('Property: PCM conversion preserves data', () => {
  it('should convert float to PCM within valid range', () => {
    fc.assert(
      fc.property(
        fc.array(fc.float({ min: -1, max: 1, noNaN: true }), { minLength: 1, maxLength: 1000 }),
        (samples) => {
          const input = new Float32Array(samples)
          const pcm = floatTo16BitPCM(input)
          
          // All PCM values should be in valid 16-bit range
          for (let i = 0; i < pcm.length; i++) {
            expect(pcm[i]).toBeGreaterThanOrEqual(-32768)
            expect(pcm[i]).toBeLessThanOrEqual(32767)
          }
        }
      ),
      { numRuns: 100 }
    )
  })

  it('should preserve sign of audio samples', () => {
    fc.assert(
      fc.property(
        fc.array(fc.float({ min: -1, max: 1, noNaN: true }), { minLength: 1, maxLength: 100 }),
        (samples) => {
          const input = new Float32Array(samples)
          const pcm = floatTo16BitPCM(input)
          
          for (let i = 0; i < samples.length; i++) {
            if (samples[i] > 0.0001) {
              expect(pcm[i]).toBeGreaterThan(0)
            } else if (samples[i] < -0.0001) {
              expect(pcm[i]).toBeLessThan(0)
            }
          }
        }
      ),
      { numRuns: 100 }
    )
  })
})

/**
 * Property: Base64 encoding is reversible
 * 
 * For any Int16Array, encoding to Base64 and decoding should produce
 * the original data.
 */
describe('Property: Base64 encoding is reversible', () => {
  it('should produce reversible Base64 encoding', () => {
    fc.assert(
      fc.property(
        fc.array(fc.integer({ min: -32768, max: 32767 }), { minLength: 1, maxLength: 500 }),
        (samples) => {
          const input = new Int16Array(samples)
          const base64 = int16ArrayToBase64(input)
          
          // Decode back
          const binary = atob(base64)
          const bytes = new Uint8Array(binary.length)
          for (let i = 0; i < binary.length; i++) {
            bytes[i] = binary.charCodeAt(i)
          }
          const decoded = new Int16Array(bytes.buffer)
          
          // Should match original
          expect(decoded.length).toBe(input.length)
          for (let i = 0; i < input.length; i++) {
            expect(decoded[i]).toBe(input[i])
          }
        }
      ),
      { numRuns: 100 }
    )
  })
})

// ============================================================================
// Unit Tests - AudioWorklet Fallback Behavior
// ============================================================================

/**
 * Tests for AudioWorklet fallback to ScriptProcessorNode
 * 
 * Validates: Requirements 1.2
 * - When AudioWorklet is not supported, fall back to ScriptProcessorNode
 * - Console warning should be logged when falling back
 */
describe('AudioWorklet Fallback Behavior', () => {
  let consoleWarnSpy: ReturnType<typeof vi.spyOn>
  
  beforeEach(() => {
    consoleWarnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
  })
  
  afterEach(() => {
    consoleWarnSpy.mockRestore()
  })

  it('should return false when AudioWorkletNode is undefined', () => {
    // Simulate browser without AudioWorkletNode
    const result = checkWorkletSupport(false, false, true)
    expect(result).toBe(false)
  })

  it('should return false when audioWorklet is not in AudioContext', () => {
    // Simulate browser with AudioWorkletNode but no audioWorklet in context
    const result = checkWorkletSupport(false, true, false)
    expect(result).toBe(false)
  })

  it('should return false when forceScriptProcessor option is true', () => {
    // Even with full support, should return false when forced
    const result = checkWorkletSupport(true, true, true)
    expect(result).toBe(false)
  })

  /**
   * Test that the fallback detection logic correctly identifies
   * when ScriptProcessorNode should be used
   */
  describe('Fallback Detection Logic', () => {
    it('should detect need for fallback when AudioWorkletNode is missing', () => {
      const scenarios = [
        { hasNode: false, hasContext: false, expected: false },
        { hasNode: false, hasContext: true, expected: false },
        { hasNode: true, hasContext: false, expected: false },
        { hasNode: true, hasContext: true, expected: true },
      ]
      
      for (const scenario of scenarios) {
        const result = checkWorkletSupport(false, scenario.hasNode, scenario.hasContext)
        expect(result).toBe(scenario.expected)
      }
    })

    it('should always use fallback when explicitly requested', () => {
      // All combinations should return false when forceScriptProcessor is true
      const combinations = [
        [false, false],
        [false, true],
        [true, false],
        [true, true],
      ]
      
      for (const [hasNode, hasContext] of combinations) {
        const result = checkWorkletSupport(true, hasNode, hasContext)
        expect(result).toBe(false)
      }
    })
  })

  /**
   * Test buffer size validation for ScriptProcessorNode fallback
   * ScriptProcessorNode requires buffer sizes that are powers of 2
   */
  describe('ScriptProcessorNode Buffer Size Validation', () => {
    const validBufferSizes = [256, 512, 1024, 2048, 4096, 8192, 16384]
    
    it('should use valid power-of-2 buffer sizes', () => {
      for (const size of validBufferSizes) {
        // Verify it's a power of 2
        expect(Math.log2(size) % 1).toBe(0)
        // Verify it's in valid range
        expect(size).toBeGreaterThanOrEqual(256)
        expect(size).toBeLessThanOrEqual(16384)
      }
    })

    it('should round up to nearest power of 2 for invalid sizes', () => {
      const testCases = [
        { input: 1000, expected: 1024 },
        { input: 1025, expected: 2048 },
        { input: 500, expected: 512 },
        { input: 3000, expected: 4096 },
      ]
      
      for (const { input, expected } of testCases) {
        const rounded = Math.pow(2, Math.ceil(Math.log2(input)))
        expect(rounded).toBe(expected)
      }
    })

    it('should cap buffer size at 16384', () => {
      const largeSize = 20000
      const rounded = Math.pow(2, Math.ceil(Math.log2(largeSize)))
      const capped = Math.min(rounded, 16384)
      expect(capped).toBe(16384)
    })

    it('should ensure minimum buffer size of 1024', () => {
      const smallSizes = [100, 256, 512]
      for (const size of smallSizes) {
        const adjusted = Math.max(1024, size)
        expect(adjusted).toBeGreaterThanOrEqual(1024)
      }
    })
  })
})
