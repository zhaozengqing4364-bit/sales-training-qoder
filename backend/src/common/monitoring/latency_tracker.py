"""
Latency Tracker for Voice Practice Module

Provides end-to-end latency tracking and performance monitoring for
voice practice sessions. Implements trace-based logging for all
critical stages of the audio processing pipeline.

Constitution Principle II: Real-Time Priority - <300ms end-to-end latency
Constitution Principle VII: Observability - Structured logging with trace_id

Requirements: Voice Practice Optimization - Performance Monitoring
"""
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from common.monitoring.logger import get_logger

logger = get_logger(__name__)


@dataclass
class LatencyStage:
    """Represents a single stage in the latency pipeline."""
    stage: str
    timestamp: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LatencyTrace:
    """Complete latency trace for a single interaction."""
    trace_id: str
    stages: list[LatencyStage] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)
    
    def add_stage(self, stage: str, metadata: dict[str, Any] | None = None) -> None:
        """Add a stage to the trace."""
        self.stages.append(LatencyStage(
            stage=stage,
            timestamp=time.time(),
            metadata=metadata or {},
        ))
    
    def get_total_latency_ms(self) -> float:
        """Get total latency from first to last stage in milliseconds."""
        if len(self.stages) < 2:
            return 0.0
        return (self.stages[-1].timestamp - self.stages[0].timestamp) * 1000
    
    def get_stage_latency_ms(self, from_stage: str, to_stage: str) -> float | None:
        """Get latency between two specific stages in milliseconds."""
        from_ts = None
        to_ts = None
        
        for stage in self.stages:
            if stage.stage == from_stage and from_ts is None:
                from_ts = stage.timestamp
            if stage.stage == to_stage:
                to_ts = stage.timestamp
        
        if from_ts is not None and to_ts is not None:
            return (to_ts - from_ts) * 1000
        return None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert trace to dictionary for logging."""
        return {
            "trace_id": self.trace_id,
            "total_latency_ms": round(self.get_total_latency_ms(), 2),
            "stages": [
                {
                    "stage": s.stage,
                    "offset_ms": round((s.timestamp - self.start_time) * 1000, 2),
                    **s.metadata,
                }
                for s in self.stages
            ],
        }


class LatencyTracker:
    """
    Singleton latency tracker for voice practice performance monitoring.
    
    Tracks latency across the following stages:
    - audio_capture_start: Frontend starts recording
    - audio_received: Backend receives audio chunk
    - asr_start: ASR processing begins
    - asr_complete: ASR returns transcript
    - llm_start: LLM generation begins
    - llm_first_token: First token generated
    - llm_complete: LLM generation complete
    - tts_start: TTS generation begins
    - tts_first_chunk: First TTS chunk generated
    - tts_complete: TTS generation complete
    - audio_playback_start: Frontend starts playback
    
    Constitution Principle II: Real-Time Priority
    Constitution Principle VII: Observability
    """
    
    # Stage names for reference
    STAGE_AUDIO_CAPTURE_START = "audio_capture_start"
    STAGE_AUDIO_RECEIVED = "audio_received"
    STAGE_ASR_START = "asr_start"
    STAGE_ASR_COMPLETE = "asr_complete"
    STAGE_LLM_START = "llm_start"
    STAGE_LLM_FIRST_TOKEN = "llm_first_token"
    STAGE_LLM_COMPLETE = "llm_complete"
    STAGE_TTS_START = "tts_start"
    STAGE_TTS_FIRST_CHUNK = "tts_first_chunk"
    STAGE_TTS_COMPLETE = "tts_complete"
    STAGE_AUDIO_PLAYBACK_START = "audio_playback_start"
    
    # Performance targets (Constitution Principle II)
    TARGET_E2E_LATENCY_MS = 300  # End-to-end target
    TARGET_ASR_LATENCY_MS = 200  # ASR processing target
    TARGET_INTERRUPT_LATENCY_MS = 100  # Interrupt response target
    
    def __init__(self):
        self._traces: dict[str, LatencyTrace] = {}
        self._completed_traces: list[LatencyTrace] = []
        self._max_completed_traces = 1000  # Keep last 1000 traces for stats
        self._stats: dict[str, list[float]] = defaultdict(list)
    
    def start_trace(self, trace_id: str) -> LatencyTrace:
        """Start a new latency trace."""
        trace = LatencyTrace(trace_id=trace_id)
        self._traces[trace_id] = trace
        return trace
    
    def record(
        self, 
        trace_id: str, 
        stage: str, 
        metadata: dict[str, Any] | None = None
    ) -> None:
        """
        Record a latency stage.
        
        Args:
            trace_id: Unique trace identifier
            stage: Stage name (see STAGE_* constants)
            metadata: Optional additional data to log
        """
        trace = self._traces.get(trace_id)
        
        if trace is None:
            # Auto-create trace if not exists
            trace = self.start_trace(trace_id)
        
        trace.add_stage(stage, metadata)
        
        # Log the stage
        offset_ms = (time.time() - trace.start_time) * 1000
        logger.info(
            f"[{trace_id}] {stage} at +{offset_ms:.1f}ms",
            latency_trace_id=trace_id,
            stage=stage,
            offset_ms=round(offset_ms, 2),
            **(metadata or {}),
        )
    
    def complete_trace(self, trace_id: str) -> LatencyTrace | None:
        """
        Complete a trace and compute statistics.
        
        Returns the completed trace or None if not found.
        """
        trace = self._traces.pop(trace_id, None)
        
        if trace is None:
            return None
        
        # Compute and log summary
        total_latency = trace.get_total_latency_ms()
        
        # Store for statistics
        self._completed_traces.append(trace)
        if len(self._completed_traces) > self._max_completed_traces:
            self._completed_traces.pop(0)
        
        # Track stage-specific latencies
        asr_latency = trace.get_stage_latency_ms(
            self.STAGE_ASR_START, self.STAGE_ASR_COMPLETE
        )
        if asr_latency is not None:
            self._stats["asr"].append(asr_latency)
        
        llm_first_token_latency = trace.get_stage_latency_ms(
            self.STAGE_LLM_START, self.STAGE_LLM_FIRST_TOKEN
        )
        if llm_first_token_latency is not None:
            self._stats["llm_first_token"].append(llm_first_token_latency)
        
        tts_first_chunk_latency = trace.get_stage_latency_ms(
            self.STAGE_TTS_START, self.STAGE_TTS_FIRST_CHUNK
        )
        if tts_first_chunk_latency is not None:
            self._stats["tts_first_chunk"].append(tts_first_chunk_latency)
        
        self._stats["e2e"].append(total_latency)
        
        # Log warning if over target
        if total_latency > self.TARGET_E2E_LATENCY_MS:
            logger.warning(
                f"[{trace_id}] E2E latency {total_latency:.1f}ms exceeds target {self.TARGET_E2E_LATENCY_MS}ms",
                latency_trace_id=trace_id,
                total_latency_ms=round(total_latency, 2),
                target_ms=self.TARGET_E2E_LATENCY_MS,
            )
        else:
            logger.info(
                f"[{trace_id}] Trace complete: {total_latency:.1f}ms",
                latency_trace_id=trace_id,
                total_latency_ms=round(total_latency, 2),
            )
        
        return trace
    
    def compute_percentiles(self, metric: str = "e2e") -> dict[str, float]:
        """
        Compute percentile statistics for a metric.
        
        Args:
            metric: One of 'e2e', 'asr', 'llm_first_token', 'tts_first_chunk'
            
        Returns:
            Dict with p50, p95, p99, min, max, count
        """
        samples = self._stats.get(metric, [])
        
        if not samples:
            return {
                "p50": 0.0,
                "p95": 0.0,
                "p99": 0.0,
                "min": 0.0,
                "max": 0.0,
                "count": 0,
            }
        
        sorted_samples = sorted(samples)
        count = len(sorted_samples)
        
        def percentile(p: float) -> float:
            idx = int(p / 100 * count)
            return sorted_samples[min(idx, count - 1)]
        
        return {
            "p50": round(percentile(50), 2),
            "p95": round(percentile(95), 2),
            "p99": round(percentile(99), 2),
            "min": round(min(sorted_samples), 2),
            "max": round(max(sorted_samples), 2),
            "count": count,
        }
    
    def log_statistics(self) -> None:
        """Log current statistics for all metrics."""
        for metric in ["e2e", "asr", "llm_first_token", "tts_first_chunk"]:
            stats = self.compute_percentiles(metric)
            if stats["count"] > 0:
                logger.info(
                    f"[STATS] {metric}: p50={stats['p50']:.1f}ms, "
                    f"p95={stats['p95']:.1f}ms, p99={stats['p99']:.1f}ms "
                    f"(n={stats['count']})",
                    metric=metric,
                    **stats,
                )
    
    def get_active_trace_count(self) -> int:
        """Get number of active (incomplete) traces."""
        return len(self._traces)
    
    def clear_stats(self) -> None:
        """Clear all statistics."""
        self._stats.clear()
        self._completed_traces.clear()


# Singleton instance
_latency_tracker: LatencyTracker | None = None


def get_latency_tracker() -> LatencyTracker:
    """Get the singleton latency tracker instance."""
    global _latency_tracker
    if _latency_tracker is None:
        _latency_tracker = LatencyTracker()
    return _latency_tracker
