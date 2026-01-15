"use client";

import { useCallback, useRef, useState, useEffect } from "react";

interface UseAudioRecorderOptions {
    onAudioData?: (base64Audio: string) => void;
    onAudioEnd?: () => void;
    onSpeakingChange?: (speaking: boolean) => void;
    targetSampleRate?: number;
    /** Buffer size for audio processing. Default: 1024 for ~21ms latency */
    bufferSize?: number;
    /** Force use of ScriptProcessorNode instead of AudioWorklet (for testing) */
    forceScriptProcessor?: boolean;
}

interface AudioRecorderState {
    isRecording: boolean;
    hasPermission: boolean | null;
    error: string | null;
    stream: MediaStream | null;
    /** Whether AudioWorklet is supported and being used */
    isWorkletSupported: boolean;
}

export function useAudioRecorder(options: UseAudioRecorderOptions = {}) {
    const { 
        onAudioData, 
        onAudioEnd, 
        onSpeakingChange, 
        targetSampleRate = 16000,
        bufferSize = 1024,  // Default 1024 samples for ~21ms latency at 48kHz
        forceScriptProcessor = false
    } = options;
    
    const [isRecording, setIsRecording] = useState(false);
    const [hasPermission, setHasPermission] = useState<boolean | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [stream, setStream] = useState<MediaStream | null>(null);
    const [isWorkletSupported, setIsWorkletSupported] = useState(false);
    
    const audioContextRef = useRef<AudioContext | null>(null);
    const processorRef = useRef<ScriptProcessorNode | null>(null);
    const workletNodeRef = useRef<AudioWorkletNode | null>(null);
    const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
    const isRecordingRef = useRef(false);
    const streamRef = useRef<MediaStream | null>(null);
    const onAudioDataRef = useRef(onAudioData);
    const onAudioEndRef = useRef(onAudioEnd);
    const onSpeakingChangeRef = useRef(onSpeakingChange);
    const inputSampleRateRef = useRef(48000);
    
    // 保持回调引用最新
    useEffect(() => {
        onAudioDataRef.current = onAudioData;
        onAudioEndRef.current = onAudioEnd;
        onSpeakingChangeRef.current = onSpeakingChange;
    }, [onAudioData, onAudioEnd, onSpeakingChange]);
    
    // 同步 stream ref
    useEffect(() => {
        streamRef.current = stream;
    }, [stream]);

    // 请求麦克风权限
    const requestPermission = useCallback(async () => {
        try {
            const testStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    channelCount: 1,
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true,
                },
            });
            
            // 立即停止流，只是检查权限
            testStream.getTracks().forEach(track => track.stop());
            
            setHasPermission(true);
            setError(null);
            return true;
        } catch (err) {
            console.error("Failed to get microphone permission:", err);
            setHasPermission(false);
            setError("无法访问麦克风，请检查权限设置");
            return false;
        }
    }, []);

    // 重采样函数
    const resample = useCallback((inputData: Float32Array, inputSampleRate: number, outputSampleRate: number): Float32Array => {
        if (inputSampleRate === outputSampleRate) {
            return inputData;
        }
        
        const ratio = inputSampleRate / outputSampleRate;
        const outputLength = Math.round(inputData.length / ratio);
        const output = new Float32Array(outputLength);
        
        for (let i = 0; i < outputLength; i++) {
            const srcIndex = i * ratio;
            const srcIndexFloor = Math.floor(srcIndex);
            const srcIndexCeil = Math.min(srcIndexFloor + 1, inputData.length - 1);
            const t = srcIndex - srcIndexFloor;
            output[i] = inputData[srcIndexFloor] * (1 - t) + inputData[srcIndexCeil] * t;
        }
        
        return output;
    }, []);

    // Float32 转 16-bit PCM
    const floatTo16BitPCM = useCallback((float32Array: Float32Array): Int16Array => {
        const int16Array = new Int16Array(float32Array.length);
        for (let i = 0; i < float32Array.length; i++) {
            const s = Math.max(-1, Math.min(1, float32Array[i]));
            int16Array[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        }
        return int16Array;
    }, []);

    // Int16Array 转 Base64
    const int16ArrayToBase64 = useCallback((int16Array: Int16Array): string => {
        const bytes = new Uint8Array(int16Array.buffer);
        let binary = "";
        for (let i = 0; i < bytes.byteLength; i++) {
            binary += String.fromCharCode(bytes[i]);
        }
        return btoa(binary);
    }, []);

    // 处理音频数据的通用函数
    const processAudioData = useCallback((audioData: Float32Array, chunkCount: number) => {
        // 重采样
        const resampledData = resample(audioData, inputSampleRateRef.current, targetSampleRate);
        
        // 转换为 PCM
        const pcmData = floatTo16BitPCM(resampledData);
        
        // 转换为 base64
        const base64 = int16ArrayToBase64(pcmData);
        
        // 发送
        onAudioDataRef.current?.(base64);
        
        // 每 20 个块记录一次
        if (chunkCount % 20 === 0) {
            let maxAmp = 0;
            for (let i = 0; i < audioData.length; i++) {
                const abs = Math.abs(audioData[i]);
                if (abs > maxAmp) maxAmp = abs;
            }
            console.log(`[AudioRecorder] Chunk #${chunkCount}: max=${maxAmp.toFixed(4)}`);
        }
    }, [targetSampleRate, resample, floatTo16BitPCM, int16ArrayToBase64]);

    // 检测 AudioWorklet 支持
    const checkWorkletSupport = useCallback((): boolean => {
        if (forceScriptProcessor) {
            return false;
        }
        
        // Check if AudioWorklet is available
        if (typeof AudioWorkletNode === 'undefined') {
            return false;
        }
        
        // Check if AudioContext supports audioWorklet
        try {
            const testContext = new AudioContext();
            const hasWorklet = 'audioWorklet' in testContext;
            testContext.close();
            return hasWorklet;
        } catch {
            return false;
        }
    }, [forceScriptProcessor]);

    // 使用 AudioWorklet 设置音频处理
    const setupAudioWorklet = useCallback(async (
        audioContext: AudioContext,
        source: MediaStreamAudioSourceNode
    ): Promise<boolean> => {
        try {
            // Load the AudioWorklet module
            await audioContext.audioWorklet.addModule('/audio-worklet-processor.js');
            
            // Create AudioWorkletNode
            const workletNode = new AudioWorkletNode(audioContext, 'audio-worklet-processor');
            workletNodeRef.current = workletNode;
            
            let chunkCount = 0;
            
            // Handle messages from the worklet
            workletNode.port.onmessage = (event) => {
                if (!isRecordingRef.current) return;
                
                const { type, buffer } = event.data;
                
                if (type === 'audio' && buffer instanceof Float32Array) {
                    chunkCount++;
                    processAudioData(buffer, chunkCount);
                }
            };
            
            // Connect the audio graph
            source.connect(workletNode);
            // Note: We don't connect to destination to avoid feedback
            // workletNode.connect(audioContext.destination);
            
            console.log("[AudioRecorder] AudioWorklet setup complete");
            return true;
        } catch (err) {
            console.warn("[AudioRecorder] AudioWorklet setup failed, falling back to ScriptProcessorNode:", err);
            return false;
        }
    }, [processAudioData]);

    // 使用 ScriptProcessorNode 设置音频处理 (降级方案)
    const setupScriptProcessor = useCallback((
        audioContext: AudioContext,
        source: MediaStreamAudioSourceNode,
        processorBufferSize: number
    ): void => {
        console.warn("[AudioRecorder] Using ScriptProcessorNode (deprecated) - AudioWorklet not available");
        
        const processor = audioContext.createScriptProcessor(processorBufferSize, 1, 1);
        processorRef.current = processor;

        let chunkCount = 0;

        processor.onaudioprocess = (e) => {
            if (!isRecordingRef.current) return;
            
            const inputData = e.inputBuffer.getChannelData(0);
            
            // 复制数据
            const audioData = new Float32Array(inputData.length);
            for (let i = 0; i < inputData.length; i++) {
                audioData[i] = inputData[i];
            }
            
            chunkCount++;
            processAudioData(audioData, chunkCount);
        };

        // 连接节点
        source.connect(processor);
        processor.connect(audioContext.destination);
        
        console.log("[AudioRecorder] ScriptProcessorNode setup complete");
    }, [processAudioData]);

    // 开始录音
    const startRecording = useCallback(async () => {
        if (isRecordingRef.current) return;

        try {
            console.log("[AudioRecorder] Starting...");
            
            // Check AudioWorklet support
            const workletSupported = checkWorkletSupport();
            setIsWorkletSupported(workletSupported);
            
            // 获取新的麦克风流
            const newStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    channelCount: 1,
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true,
                },
            });
            
            const audioTrack = newStream.getAudioTracks()[0];
            if (audioTrack) {
                console.log("[AudioRecorder] Track:", {
                    label: audioTrack.label,
                    enabled: audioTrack.enabled,
                    readyState: audioTrack.readyState,
                    muted: audioTrack.muted,
                    settings: audioTrack.getSettings(),
                });
            }
            
            setStream(newStream);
            streamRef.current = newStream;
            setHasPermission(true);
            onSpeakingChangeRef.current?.(true);

            // 创建 AudioContext
            const audioContext = new AudioContext();
            audioContextRef.current = audioContext;
            inputSampleRateRef.current = audioContext.sampleRate;
            
            console.log(`[AudioRecorder] AudioContext: state=${audioContext.state}, sampleRate=${audioContext.sampleRate}`);

            if (audioContext.state === 'suspended') {
                await audioContext.resume();
                console.log("[AudioRecorder] AudioContext resumed");
            }

            // 创建音频源
            const source = audioContext.createMediaStreamSource(newStream);
            sourceRef.current = source;

            // Try to use AudioWorklet, fall back to ScriptProcessorNode
            let workletSetupSuccess = false;
            
            if (workletSupported) {
                workletSetupSuccess = await setupAudioWorklet(audioContext, source);
            }
            
            if (!workletSetupSuccess) {
                // Fall back to ScriptProcessorNode
                // Use larger buffer size for ScriptProcessorNode (must be power of 2: 256, 512, 1024, 2048, 4096, 8192, 16384)
                const scriptProcessorBufferSize = Math.max(1024, bufferSize);
                // Ensure it's a valid power of 2
                const validBufferSize = Math.pow(2, Math.ceil(Math.log2(scriptProcessorBufferSize)));
                setupScriptProcessor(audioContext, source, Math.min(validBufferSize, 16384));
                setIsWorkletSupported(false);
            }

            isRecordingRef.current = true;
            setIsRecording(true);
            setError(null);
            
            console.log(`[AudioRecorder] Recording started (using ${workletSetupSuccess ? 'AudioWorklet' : 'ScriptProcessorNode'})`);

        } catch (err) {
            console.error("[AudioRecorder] Failed to start:", err);
            setError("无法开始录音: " + (err as Error).message);
            onSpeakingChangeRef.current?.(false);
        }
    }, [bufferSize, checkWorkletSupport, setupAudioWorklet, setupScriptProcessor]);

    // 停止录音
    const stopRecording = useCallback(async (): Promise<void> => {
        if (!isRecordingRef.current) {
            return;
        }

        console.log("[AudioRecorder] Stopping...");

        isRecordingRef.current = false;
        setIsRecording(false);

        // 清理 AudioWorklet 节点
        if (workletNodeRef.current) {
            workletNodeRef.current.disconnect();
            workletNodeRef.current.port.close();
            workletNodeRef.current = null;
        }
        
        // 清理 ScriptProcessor 节点
        if (processorRef.current) {
            processorRef.current.disconnect();
            processorRef.current = null;
        }
        
        if (sourceRef.current) {
            sourceRef.current.disconnect();
            sourceRef.current = null;
        }
        if (audioContextRef.current) {
            await audioContextRef.current.close();
            audioContextRef.current = null;
        }
        
        // 停止麦克风流 (使用 ref 而不是 state)
        if (streamRef.current) {
            streamRef.current.getTracks().forEach(track => {
                track.stop();
            });
            streamRef.current = null;
            setStream(null);
        }

        // 发送音频结束信号
        onAudioEndRef.current?.();
        onSpeakingChangeRef.current?.(false);
        
        console.log("[AudioRecorder] Recording stopped");
    }, []); // 无依赖，函数引用稳定

    // 清理资源
    const cleanup = useCallback(() => {
        isRecordingRef.current = false;
        setIsRecording(false);
        
        if (workletNodeRef.current) {
            workletNodeRef.current.disconnect();
            workletNodeRef.current.port.close();
            workletNodeRef.current = null;
        }
        if (processorRef.current) {
            processorRef.current.disconnect();
            processorRef.current = null;
        }
        if (sourceRef.current) {
            sourceRef.current.disconnect();
            sourceRef.current = null;
        }
        if (audioContextRef.current) {
            audioContextRef.current.close();
            audioContextRef.current = null;
        }
        if (streamRef.current) {
            streamRef.current.getTracks().forEach(track => track.stop());
            streamRef.current = null;
            setStream(null);
        }
        setHasPermission(null);
    }, []);

    return {
        isRecording,
        hasPermission,
        error,
        stream,  // 暴露 stream 供可视化组件使用
        isWorkletSupported,  // 暴露 AudioWorklet 支持状态
        startRecording,
        stopRecording,
        requestPermission,
        cleanup,
    };
}
