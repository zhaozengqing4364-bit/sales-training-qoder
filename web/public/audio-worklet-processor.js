/**
 * AudioWorklet Processor for Voice Practice Module
 * 
 * This processor runs in a separate audio thread, avoiding main thread blocking.
 * It accumulates audio samples into 1024-sample buffers (~21ms at 48kHz) and
 * sends them to the main thread via postMessage.
 * 
 * Requirements: 1.1, 1.4, 1.5
 */

class AudioProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    
    // Buffer size of 1024 samples for ~21ms latency at 48kHz
    // 1024 / 48000 ≈ 21.3ms
    this.bufferSize = 1024;
    this.buffer = new Float32Array(this.bufferSize);
    this.bufferIndex = 0;
  }

  /**
   * Process audio data from the input.
   * Called by the audio rendering thread for each audio block (typically 128 samples).
   * 
   * @param {Float32Array[][]} inputs - Input audio data
   * @param {Float32Array[][]} outputs - Output audio data (unused)
   * @param {Record<string, Float32Array>} parameters - Audio parameters (unused)
   * @returns {boolean} - Return true to keep the processor alive
   */
  process(inputs) {
    const input = inputs[0];
    
    // No input available, keep processor alive
    if (!input || !input[0]) {
      return true;
    }

    const inputChannel = input[0];
    
    // Accumulate samples into buffer
    for (let i = 0; i < inputChannel.length; i++) {
      this.buffer[this.bufferIndex++] = inputChannel[i];
      
      // When buffer is full, send to main thread
      if (this.bufferIndex >= this.bufferSize) {
        // Send audio data via postMessage with type 'audio'
        // Requirements: 1.5 - send PCM data to main thread via postMessage
        this.port.postMessage({
          type: 'audio',
          buffer: this.buffer.slice(),
          timestamp: currentTime
        });
        
        // Reset buffer index for next accumulation
        this.bufferIndex = 0;
      }
    }

    // Return true to keep the processor running
    return true;
  }
}

// Register the processor with the name 'audio-worklet-processor'
registerProcessor('audio-worklet-processor', AudioProcessor);
