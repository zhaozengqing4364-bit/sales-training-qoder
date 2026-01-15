/**
 * AudioWorklet Processor Tests
 * 
 * Feature: voice-practice-optimization
 * 
 * Tests for the AudioWorklet processor communication and buffer handling.
 * Since AudioWorklet runs in a separate thread and isn't available in jsdom,
 * we test the processor logic by simulating its behavior.
 * 
 * Property 2: AudioWorklet Communication
 * Validates: Requirements 1.5
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import * as fc from 'fast-check'

/**
 * Simulated AudioWorklet processor logic for testing.
 * This mirrors the logic in public/audio-worklet-processor.js
 */
class MockAudioProcessor {
  private bufferSize = 1024
  private buffer: Float32Array
  private bufferIndex = 0
  private port: { postMessage: (data: unknown) => void }

  constructor(port: { postMessage: (data: unknown) => void }) {
    this.buffer = new Float32Array(this.bufferSize)
    this.port = port
  }

  /**
   * Process audio input, accumulating samples and sending when buffer is full.
   * Mirrors the process() method in audio-worklet-processor.js
   */
  process(inputs: Float32Array[][]): boolean {
    const input = inputs[0]
    
    if (!input || !input[0]) {
      return true
    }

    const inputChannel = input[0]
    
    for (let i = 0; i < inputChannel.length; i++) {
      this.buffer[this.bufferIndex++] = inputChannel[i]
      
      if (this.bufferIndex >= this.bufferSize) {
        // Send audio data via postMessage with type 'audio'
        this.port.postMessage({
          type: 'audio',
          buffer: this.buffer.slice(),
          timestamp: Date.now()
        })
        
        this.bufferIndex = 0
      }
    }

    return true
  }

  getBufferSize(): number {
    return this.bufferSize
  }

  getCurrentBufferIndex(): number {
    return this.bufferIndex
  }
}

// ============================================================================
// Unit Tests - AudioWorklet Processor Logic
// ============================================================================

describe('AudioWorklet Processor Logic', () => {
  let mockPostMessage: ReturnType<typeof vi.fn>
  let processor: MockAudioProcessor

  beforeEach(() => {
    mockPostMessage = vi.fn()
    processor = new MockAudioProcessor({ postMessage: mockPostMessage })
  })

  it('should have buffer size of 1024 samples', () => {
    expect(processor.getBufferSize()).toBe(1024)
  })

  it('should accumulate samples without sending until buffer is full', () => {
    // Send 128 samples (typical Web Audio block size)
    const input = new Float32Array(128).fill(0.5)
    processor.process([[input]])

    expect(mockPostMessage).not.toHaveBeenCalled()
    expect(processor.getCurrentBufferIndex()).toBe(128)
  })

  it('should send message when buffer reaches 1024 samples', () => {
    // Send 8 blocks of 128 samples = 1024 samples
    const input = new Float32Array(128).fill(0.5)
    
    for (let i = 0; i < 8; i++) {
      processor.process([[input]])
    }

    expect(mockPostMessage).toHaveBeenCalledTimes(1)
    expect(processor.getCurrentBufferIndex()).toBe(0)
  })

  it('should send message with correct format', () => {
    // Fill buffer to trigger send
    const input = new Float32Array(1024).fill(0.5)
    processor.process([[input]])

    expect(mockPostMessage).toHaveBeenCalledWith(
      expect.objectContaining({
        type: 'audio',
        buffer: expect.any(Float32Array),
        timestamp: expect.any(Number)
      })
    )
  })

  it('should handle empty input gracefully', () => {
    expect(processor.process([[]])).toBe(true)
    expect(processor.process([null as unknown as Float32Array[]])).toBe(true)
    expect(processor.process([])).toBe(true)
    expect(mockPostMessage).not.toHaveBeenCalled()
  })

  it('should preserve audio data in sent buffer', () => {
    const testValue = 0.75
    const input = new Float32Array(1024).fill(testValue)
    processor.process([[input]])

    const sentData = mockPostMessage.mock.calls[0][0] as { buffer: Float32Array }
    expect(sentData.buffer[0]).toBe(testValue)
    expect(sentData.buffer[1023]).toBe(testValue)
  })

  it('should handle multiple buffer fills correctly', () => {
    const input = new Float32Array(1024).fill(0.5)
    
    // Fill buffer 3 times
    processor.process([[input]])
    processor.process([[input]])
    processor.process([[input]])

    expect(mockPostMessage).toHaveBeenCalledTimes(3)
  })
})

// ============================================================================
// Property-Based Tests
// ============================================================================

/**
 * Feature: voice-practice-optimization
 * Property 2: AudioWorklet Communication
 * 
 * For any audio buffer processed by the AudioWorklet, the processor SHALL
 * send the data to the main thread via postMessage with type 'audio' and
 * a Float32Array buffer.
 * 
 * Validates: Requirements 1.5
 */
describe('Property 2: AudioWorklet Communication', () => {
  it('should always send messages with correct format when buffer is full', () => {
    fc.assert(
      fc.property(
        // Generate random audio samples (values between -1 and 1)
        fc.array(fc.float({ min: -1, max: 1, noNaN: true }), { minLength: 1024, maxLength: 4096 }),
        (audioSamples) => {
          const mockPostMessage = vi.fn()
          const processor = new MockAudioProcessor({ postMessage: mockPostMessage })
          
          // Process the audio samples
          const input = new Float32Array(audioSamples)
          processor.process([[input]])
          
          // Calculate expected number of messages
          const expectedMessages = Math.floor(audioSamples.length / 1024)
          
          // Verify correct number of messages sent
          expect(mockPostMessage).toHaveBeenCalledTimes(expectedMessages)
          
          // Verify each message has correct format
          for (let i = 0; i < expectedMessages; i++) {
            const call = mockPostMessage.mock.calls[i][0] as {
              type: string
              buffer: Float32Array
              timestamp: number
            }
            
            // Must have type 'audio'
            expect(call.type).toBe('audio')
            
            // Must have Float32Array buffer
            expect(call.buffer).toBeInstanceOf(Float32Array)
            
            // Buffer must be exactly 1024 samples
            expect(call.buffer.length).toBe(1024)
            
            // Must have timestamp
            expect(typeof call.timestamp).toBe('number')
          }
        }
      ),
      { numRuns: 100 }
    )
  })

  it('should preserve audio sample values in transmitted buffer', () => {
    fc.assert(
      fc.property(
        // Generate exactly 1024 samples to fill one buffer
        fc.array(fc.float({ min: -1, max: 1, noNaN: true }), { minLength: 1024, maxLength: 1024 }),
        (audioSamples) => {
          const mockPostMessage = vi.fn()
          const processor = new MockAudioProcessor({ postMessage: mockPostMessage })
          
          const input = new Float32Array(audioSamples)
          processor.process([[input]])
          
          expect(mockPostMessage).toHaveBeenCalledTimes(1)
          
          const sentBuffer = (mockPostMessage.mock.calls[0][0] as { buffer: Float32Array }).buffer
          
          // Verify all samples are preserved
          for (let i = 0; i < 1024; i++) {
            expect(sentBuffer[i]).toBeCloseTo(audioSamples[i], 5)
          }
        }
      ),
      { numRuns: 100 }
    )
  })

  it('should accumulate samples correctly across multiple process calls', () => {
    fc.assert(
      fc.property(
        // Generate multiple small chunks that together make at least one full buffer
        fc.array(
          fc.array(fc.float({ min: -1, max: 1, noNaN: true }), { minLength: 64, maxLength: 256 }),
          { minLength: 8, maxLength: 20 }
        ),
        (audioChunks) => {
          const mockPostMessage = vi.fn()
          const processor = new MockAudioProcessor({ postMessage: mockPostMessage })
          
          let totalSamples = 0
          
          // Process each chunk
          for (const chunk of audioChunks) {
            const input = new Float32Array(chunk)
            processor.process([[input]])
            totalSamples += chunk.length
          }
          
          // Calculate expected messages
          const expectedMessages = Math.floor(totalSamples / 1024)
          
          // Verify correct number of messages
          expect(mockPostMessage).toHaveBeenCalledTimes(expectedMessages)
          
          // Verify remaining samples in buffer
          const expectedRemaining = totalSamples % 1024
          expect(processor.getCurrentBufferIndex()).toBe(expectedRemaining)
        }
      ),
      { numRuns: 100 }
    )
  })

  it('should handle edge case of exactly buffer-sized input', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 1, max: 10 }),
        (multiplier) => {
          const mockPostMessage = vi.fn()
          const processor = new MockAudioProcessor({ postMessage: mockPostMessage })
          
          // Create input that is exact multiple of buffer size
          const input = new Float32Array(1024 * multiplier).fill(0.5)
          processor.process([[input]])
          
          // Should send exactly 'multiplier' messages
          expect(mockPostMessage).toHaveBeenCalledTimes(multiplier)
          
          // Buffer should be empty after processing
          expect(processor.getCurrentBufferIndex()).toBe(0)
        }
      ),
      { numRuns: 100 }
    )
  })
})
