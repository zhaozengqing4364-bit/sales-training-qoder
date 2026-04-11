"use client";
import { debug } from "@/lib/debug";

import * as React from "react";
import { cn } from "@/lib/utils";

interface AudioVisualizerProps {
    stream: MediaStream | null;
    isActive?: boolean;
    barCount?: number;
    className?: string;
    color?: string;
}

/**
 * 真实音频频谱可视化组件
 * 使用 Web Audio API 的 AnalyserNode 获取实时音频数据
 */
export function AudioVisualizer({
    stream,
    isActive = false,
    barCount = 16,
    className,
    color = "bg-indigo-500",
}: AudioVisualizerProps) {
    const audioContextRef = React.useRef<AudioContext | null>(null);
    const analyserRef = React.useRef<AnalyserNode | null>(null);
    const sourceRef = React.useRef<MediaStreamAudioSourceNode | null>(null);
    const animationRef = React.useRef<number | null>(null);
    const [bars, setBars] = React.useState<number[]>(Array(barCount).fill(4));

    // 当 stream 变化时，设置音频分析
    React.useEffect(() => {
        if (!stream || !isActive) {
            // 清理
            if (animationRef.current) {
                cancelAnimationFrame(animationRef.current);
                animationRef.current = null;
            }
            if (sourceRef.current) {
                sourceRef.current.disconnect();
                sourceRef.current = null;
            }
            if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
                audioContextRef.current.close();
                audioContextRef.current = null;
            }
            analyserRef.current = null;
            setBars(Array(barCount).fill(4));
            return;
        }

        const setupAudio = async () => {
            try {
                // 创建 AudioContext
                const audioContext = new AudioContext();
                audioContextRef.current = audioContext;

                // 确保 AudioContext 运行
                if (audioContext.state === 'suspended') {
                    await audioContext.resume();
                }

                // 创建分析器
                const analyser = audioContext.createAnalyser();
                analyser.fftSize = 256;
                analyser.smoothingTimeConstant = 0.7;
                analyserRef.current = analyser;

                // 创建音频源
                const source = audioContext.createMediaStreamSource(stream);
                sourceRef.current = source;
                source.connect(analyser);

                // 开始动画
                const dataArray = new Uint8Array(analyser.frequencyBinCount);
                
                const draw = () => {
                    if (!analyserRef.current) return;
                    
                    analyserRef.current.getByteFrequencyData(dataArray);
                    
                    // 将频率数据映射到条形高度
                    const newBars: number[] = [];
                    const step = Math.floor(dataArray.length / barCount);
                    
                    for (let i = 0; i < barCount; i++) {
                        // 取每个区间的平均值
                        let sum = 0;
                        for (let j = 0; j < step; j++) {
                            sum += dataArray[i * step + j];
                        }
                        const avg = sum / step;
                        // 映射到 4-32 的高度范围
                        const height = Math.max(4, (avg / 255) * 32);
                        newBars.push(height);
                    }
                    
                    setBars(newBars);
                    animationRef.current = requestAnimationFrame(draw);
                };
                
                draw();
            } catch (err) {
                debug.error("Failed to setup audio visualizer:", err);
            }
        };

        setupAudio();

        return () => {
            if (animationRef.current) {
                cancelAnimationFrame(animationRef.current);
            }
            if (sourceRef.current) {
                sourceRef.current.disconnect();
            }
            if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
                audioContextRef.current.close();
            }
        };
    }, [stream, isActive, barCount]);

    return (
        <div className={cn("flex items-center justify-center gap-0.5 h-8", className)}>
            {bars.map((height, index) => (
                <div
                    key={index}
                    className={cn("w-1 rounded-full transition-all duration-75", color)}
                    style={{ height: `${height}px` }}
                />
            ))}
        </div>
    );
}

/**
 * 简单的音量指示器
 * 显示当前音量级别
 */
interface AudioLevelProps {
    stream: MediaStream | null;
    isActive?: boolean;
    className?: string;
}

export function AudioLevel({ stream, isActive = false, className }: AudioLevelProps) {
    const [level, setLevel] = React.useState(0);
    const audioContextRef = React.useRef<AudioContext | null>(null);
    const analyserRef = React.useRef<AnalyserNode | null>(null);
    const animationRef = React.useRef<number | null>(null);

    React.useEffect(() => {
        if (!stream || !isActive) {
            if (animationRef.current) {
                cancelAnimationFrame(animationRef.current);
            }
            if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
                audioContextRef.current.close();
            }
            setLevel(0);
            return;
        }

        const setup = async () => {
            const audioContext = new AudioContext();
            audioContextRef.current = audioContext;
            
            if (audioContext.state === 'suspended') {
                await audioContext.resume();
            }

            const analyser = audioContext.createAnalyser();
            analyser.fftSize = 256;
            analyserRef.current = analyser;

            const source = audioContext.createMediaStreamSource(stream);
            source.connect(analyser);

            const dataArray = new Uint8Array(analyser.frequencyBinCount);
            
            const update = () => {
                if (!analyserRef.current) return;
                
                analyserRef.current.getByteFrequencyData(dataArray);
                const avg = dataArray.reduce((a, b) => a + b, 0) / dataArray.length;
                setLevel(avg / 255);
                
                animationRef.current = requestAnimationFrame(update);
            };
            
            update();
        };

        setup();

        return () => {
            if (animationRef.current) {
                cancelAnimationFrame(animationRef.current);
            }
            if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
                audioContextRef.current.close();
            }
        };
    }, [stream, isActive]);

    return (
        <div className={cn("w-full h-2 bg-slate-100 rounded-full overflow-hidden", className)}>
            <div
                className="h-full bg-indigo-500 transition-all duration-75"
                style={{ width: `${level * 100}%` }}
            />
        </div>
    );
}
