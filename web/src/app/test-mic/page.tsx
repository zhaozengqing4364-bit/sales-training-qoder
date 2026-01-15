"use client";

import * as React from "react";
import { Mic, Square } from "lucide-react";
import { Button } from "@/components/ui/button";
import { AudioVisualizer, AudioLevel } from "@/components/ui/audio-visualizer";

export default function TestMicPage() {
    const [isRecording, setIsRecording] = React.useState(false);
    const [logs, setLogs] = React.useState<string[]>([]);
    const [stream, setStream] = React.useState<MediaStream | null>(null);

    const addLog = (msg: string) => {
        const timestamp = new Date().toLocaleTimeString();
        setLogs(prev => [...prev.slice(-50), `[${timestamp}] ${msg}`]);
        console.log(msg);
    };

    const startRecording = async () => {
        try {
            addLog("Requesting microphone access...");
            
            const newStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    channelCount: 1,
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true,
                },
            });
            
            setStream(newStream);
            
            const audioTrack = newStream.getAudioTracks()[0];
            if (audioTrack) {
                const settings = audioTrack.getSettings();
                addLog(`Track: ${audioTrack.label}`);
                addLog(`Settings: sampleRate=${settings.sampleRate}, channelCount=${settings.channelCount}`);
                addLog(`State: enabled=${audioTrack.enabled}, readyState=${audioTrack.readyState}, muted=${audioTrack.muted}`);
            }

            // 创建 AudioContext 测试音频数据
            const audioContext = new AudioContext();
            addLog(`AudioContext: state=${audioContext.state}, sampleRate=${audioContext.sampleRate}`);

            if (audioContext.state === 'suspended') {
                await audioContext.resume();
                addLog("AudioContext resumed");
            }

            const source = audioContext.createMediaStreamSource(newStream);
            const analyser = audioContext.createAnalyser();
            analyser.fftSize = 256;
            source.connect(analyser);

            // 测试 ScriptProcessorNode
            const processor = audioContext.createScriptProcessor(4096, 1, 1);
            let chunkCount = 0;
            let hasNonZeroAudio = false;
            
            processor.onaudioprocess = (e) => {
                const inputData = e.inputBuffer.getChannelData(0);
                
                let maxAmp = 0;
                for (let i = 0; i < inputData.length; i++) {
                    const abs = Math.abs(inputData[i]);
                    if (abs > maxAmp) maxAmp = abs;
                }
                
                if (maxAmp > 0.001 && !hasNonZeroAudio) {
                    hasNonZeroAudio = true;
                    addLog(`✅ 检测到音频信号! max=${maxAmp.toFixed(4)}`);
                }
                
                chunkCount++;
                if (chunkCount % 10 === 0) {
                    addLog(`ScriptProcessor #${chunkCount}: max=${maxAmp.toFixed(6)}`);
                }
            };
            
            source.connect(processor);
            processor.connect(audioContext.destination);

            setIsRecording(true);
            addLog("Recording started - 请对着麦克风说话");

        } catch (err) {
            addLog(`Error: ${(err as Error).message}`);
        }
    };

    const stopRecording = () => {
        if (stream) {
            stream.getTracks().forEach(track => track.stop());
            setStream(null);
        }
        setIsRecording(false);
        addLog("Recording stopped");
    };

    const listDevices = async () => {
        try {
            const devices = await navigator.mediaDevices.enumerateDevices();
            const audioInputs = devices.filter(d => d.kind === 'audioinput');
            addLog(`Found ${audioInputs.length} audio input devices:`);
            audioInputs.forEach((d, i) => {
                addLog(`  ${i + 1}. ${d.label || 'Unknown'} (${d.deviceId.slice(0, 8)}...)`);
            });
        } catch (err) {
            addLog(`Error: ${(err as Error).message}`);
        }
    };

    return (
        <div className="min-h-screen bg-slate-50 p-8">
            <div className="max-w-2xl mx-auto">
                <h1 className="text-2xl font-bold text-slate-900 mb-6">麦克风测试页面</h1>
                
                {/* 真实音频可视化 */}
                <div className="mb-6 p-6 bg-white rounded-2xl shadow-[0_8px_30px_rgb(0,0,0,0.04)]">
                    <div className="text-sm text-slate-600 mb-4">实时音频频谱</div>
                    <div className="flex justify-center mb-4">
                        <AudioVisualizer 
                            stream={stream} 
                            isActive={isRecording} 
                            barCount={24}
                            className="h-16"
                        />
                    </div>
                    <div className="text-sm text-slate-600 mb-2">音量级别</div>
                    <AudioLevel stream={stream} isActive={isRecording} />
                    <p className="text-xs text-slate-400 mt-2">
                        {isRecording ? "正在录音 - 如果看到波形跳动，说明麦克风正常" : "点击开始录音查看音频波形"}
                    </p>
                </div>

                {/* 控制按钮 */}
                <div className="flex gap-4 mb-6">
                    <Button
                        onClick={isRecording ? stopRecording : startRecording}
                        className={isRecording ? "bg-red-500 hover:bg-red-600" : "bg-indigo-600 hover:bg-indigo-700"}
                    >
                        {isRecording ? (
                            <>
                                <Square className="w-4 h-4 mr-2" />
                                停止录音
                            </>
                        ) : (
                            <>
                                <Mic className="w-4 h-4 mr-2" />
                                开始录音
                            </>
                        )}
                    </Button>
                    
                    <Button variant="outline" onClick={listDevices}>
                        列出设备
                    </Button>
                    
                    <Button variant="outline" onClick={() => setLogs([])}>
                        清空日志
                    </Button>
                </div>

                {/* 日志输出 */}
                <div className="bg-slate-900 text-green-400 p-4 rounded-xl font-mono text-xs h-80 overflow-y-auto">
                    {logs.length === 0 ? (
                        <div className="text-slate-500">点击"开始录音"测试麦克风...</div>
                    ) : (
                        logs.map((log, i) => (
                            <div key={i} className="mb-1">{log}</div>
                        ))
                    )}
                </div>

                {/* 说明 */}
                <div className="mt-6 p-4 bg-amber-50 border border-amber-100 rounded-xl text-sm text-amber-800">
                    <p className="font-bold mb-2">调试说明：</p>
                    <ul className="list-disc list-inside space-y-1">
                        <li>如果频谱条不动，说明麦克风没有捕获到声音</li>
                        <li>检查浏览器地址栏是否有麦克风图标，点击确认权限</li>
                        <li>检查系统设置中的麦克风输入设备是否正确</li>
                        <li>尝试在系统偏好设置中测试麦克风</li>
                    </ul>
                </div>
            </div>
        </div>
    );
}
