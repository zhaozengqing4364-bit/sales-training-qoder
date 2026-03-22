// AudioWorklet processor for capturing audio data
class AudioProcessor extends AudioWorkletProcessor {
    constructor() {
        super();
        this.bufferSize = 4096;
        this.buffer = new Float32Array(this.bufferSize);
        this.bufferIndex = 0;
    }

    process(inputs) {
        const input = inputs[0];
        if (!input || !input[0]) {
            return true;
        }

        const inputChannel = input[0];
        
        // Accumulate samples into buffer
        for (let i = 0; i < inputChannel.length; i++) {
            this.buffer[this.bufferIndex++] = inputChannel[i];
            
            if (this.bufferIndex >= this.bufferSize) {
                // Send buffer to main thread
                this.port.postMessage({
                    type: 'audio',
                    data: this.buffer.slice()
                });
                this.bufferIndex = 0;
            }
        }

        return true;
    }
}

registerProcessor('audio-processor', AudioProcessor);
