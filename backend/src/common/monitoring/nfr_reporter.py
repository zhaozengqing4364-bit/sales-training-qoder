"""
NFR Performance Report Generator

Automated test report generation for NFR (Non-Functional Requirements)
performance metrics validation.

Constitution Principle II: Real-Time Priority - <300ms end-to-end latency
Constitution Principle VII: Observability - Structured logging with trace_id

Requirements:
- NFR-P1: End-to-end latency < 300ms (P95)
- NFR-P2: ASR streaming latency < 200ms (P95)
- NFR-P3: Interrupt detection latency < 100ms (P95)
- NFR-P4: Key API response < 100ms (P95), < 200ms (P99)
- NFR-C1: Support >= 50 concurrent sessions
"""
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from common.monitoring.logger import get_logger

logger = get_logger(__name__)


@dataclass
class NFRThreshold:
    """Single NFR performance threshold definition."""
    metric_name: str
    p95_target_ms: float
    p99_target_ms: float | None = None
    description: str = ""


@dataclass
class NFRTestResult:
    """Result of a single NFR metric test."""
    metric_name: str
    p95_actual_ms: float
    p99_actual_ms: float | None = None
    passed: bool = False
    samples: int = 0
    min_ms: float = 0.0
    max_ms: float = 0.0
    avg_ms: float = 0.0


class NFRReporter:
    """
    Generates comprehensive NFR performance reports.

    Supports multiple output formats:
    - JSON: Machine-readable for CI/CD integration
    - Markdown: Human-readable for documentation
    - HTML: Visual report for dashboards
    """

    # NFR thresholds from Constitution Principle II
    THRESHOLDS: list[NFRThreshold] = [
        NFRThreshold(
            metric_name="end_to_end_latency",
            p95_target_ms=300.0,
            description="User speech to AI response latency",
        ),
        NFRThreshold(
            metric_name="websocket_connection",
            p95_target_ms=100.0,
            description="WebSocket connection establishment time",
        ),
        NFRThreshold(
            metric_name="asr_streaming_latency",
            p95_target_ms=200.0,
            description="ASR transcription streaming latency",
        ),
        NFRThreshold(
            metric_name="asr_first_result",
            p95_target_ms=200.0,
            description="ASR first transcription result",
        ),
        NFRThreshold(
            metric_name="tts_first_byte_latency",
            p95_target_ms=300.0,
            description="TTS first audio chunk latency",
        ),
        NFRThreshold(
            metric_name="tts_total_synthesis",
            p95_target_ms=500.0,
            description="TTS total synthesis time",
        ),
        NFRThreshold(
            metric_name="interrupt_detection",
            p95_target_ms=100.0,
            description="Interrupt detection response time",
        ),
        NFRThreshold(
            metric_name="session_creation",
            p95_target_ms=100.0,
            p99_target_ms=200.0,
            description="Session creation API response",
        ),
    ]

    def __init__(self, output_dir: str | Path = "test-results"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.results: list[NFRTestResult] = []
        self.test_metadata: dict[str, Any] = {}

    def add_result(
        self,
        metric_name: str,
        samples: list[float],
    ) -> None:
        """
        Add a test result for a metric.

        Args:
            metric_name: Name of the metric (must match threshold name)
            samples: List of measured latencies in milliseconds
        """
        if not samples:
            logger.warning(f"No samples provided for metric: {metric_name}")
            return

        # Calculate statistics
        sorted_samples = sorted(samples)
        count = len(sorted_samples)

        p95_idx = int(0.95 * count)
        p99_idx = int(0.99 * count)

        p95 = sorted_samples[min(p95_idx, count - 1)]
        p99 = sorted_samples[min(p99_idx, count - 1)]

        # Find threshold for this metric
        threshold = next(
            (t for t in self.THRESHOLDS if t.metric_name == metric_name),
            None,
        )

        if threshold is None:
            logger.warning(f"No threshold defined for metric: {metric_name}")
            return

        # Check if passed
        passed = p95 < threshold.p95_target_ms
        if threshold.p99_target_ms is not None:
            passed = passed and (p99 < threshold.p99_target_ms)

        # Store result
        result = NFRTestResult(
            metric_name=metric_name,
            p95_actual_ms=p95,
            p99_actual_ms=p99,
            passed=passed,
            samples=count,
            min_ms=min(sorted_samples),
            max_ms=max(sorted_samples),
            avg_ms=sum(sorted_samples) / count,
        )

        self.results.append(result)

        logger.info(
            f"NFR metric {metric_name}: P95={p95:.2f}ms (target: {threshold.p95_target_ms}ms), "
            f"P99={p99:.2f}ms, status={'✅ PASS' if passed else '❌ FAIL'}",
            metric_name=metric_name,
            p95_ms=round(p95, 2),
            target_ms=threshold.p95_target_ms,
            p99_ms=round(p99, 2) if p99 else None,
            passed=passed,
        )

    def set_metadata(
        self,
        commit_sha: str | None = None,
        branch: str | None = None,
        environment: str = "ci",
        test_duration_seconds: float | None = None,
    ) -> None:
        """Set test execution metadata."""
        self.test_metadata = {
            "timestamp": datetime.utcnow().isoformat(),
            "commit_sha": commit_sha or "unknown",
            "branch": branch or "unknown",
            "environment": environment,
            "test_duration_seconds": test_duration_seconds,
        }

    def get_summary(self) -> dict[str, Any]:
        """Get summary of all test results."""
        total_metrics = len(self.results)
        passed_metrics = sum(1 for r in self.results if r.passed)
        failed_metrics = total_metrics - passed_metrics

        return {
            "total_metrics": total_metrics,
            "passed_metrics": passed_metrics,
            "failed_metrics": failed_metrics,
            "pass_rate": (
                passed_metrics / total_metrics if total_metrics > 0 else 0.0
            ),
            "overall_status": "PASS" if failed_metrics == 0 else "FAIL",
        }

    def generate_json(self, filename: str = "nfr-report.json") -> Path:
        """Generate JSON report for CI/CD integration."""
        report = {
            "metadata": self.test_metadata,
            "summary": self.get_summary(),
            "thresholds": [
                {
                    "metric_name": t.metric_name,
                    "p95_target_ms": t.p95_target_ms,
                    "p99_target_ms": t.p99_target_ms,
                    "description": t.description,
                }
                for t in self.THRESHOLDS
            ],
            "results": [
                {
                    "metric_name": r.metric_name,
                    "p95_actual_ms": round(r.p95_actual_ms, 2),
                    "p99_actual_ms": round(r.p99_actual_ms, 2) if r.p99_actual_ms else None,
                    "passed": r.passed,
                    "samples": r.samples,
                    "min_ms": round(r.min_ms, 2),
                    "max_ms": round(r.max_ms, 2),
                    "avg_ms": round(r.avg_ms, 2),
                }
                for r in self.results
            ],
        }

        output_path = self.output_dir / filename
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        logger.info(f"JSON report generated: {output_path}")
        return output_path

    def generate_markdown(self, filename: str = "nfr-report.md") -> Path:
        """Generate Markdown report for human review."""
        lines = [
            "# NFR Performance Report",
            "",
            f"**Generated:** {self.test_metadata.get('timestamp', 'N/A')}",
            f"**Commit:** `{self.test_metadata.get('commit_sha', 'N/A')}`",
            f"**Branch:** `{self.test_metadata.get('branch', 'N/A')}`",
            f"**Environment:** `{self.test_metadata.get('environment', 'ci')}`",
            "",
            "---",
            "",
            "## Summary",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Total Metrics Tested | {self.get_summary()['total_metrics']} |",
            f"| Passed | {self.get_summary()['passed_metrics']} |",
            f"| Failed | {self.get_summary()['failed_metrics']} |",
            f"| Pass Rate | {self.get_summary()['pass_rate']*100:.1f}% |",
            f"| Overall Status | **{'✅ PASS' if self.get_summary()['overall_status'] == 'PASS' else '❌ FAIL'}** |",
            "",
            "---",
            "",
            "## Performance Targets (Constitution Principle II)",
            "",
            "### Core Latency Requirements",
            "",
            "| Metric | P95 Target | P95 Actual | P99 Target | P99 Actual | Status |",
            "|--------|-------------|-------------|-------------|-------------|--------|",
        ]

        # Add metric results
        for result in self.results:
            threshold = next(
                (t for t in self.THRESHOLDS if t.metric_name == result.metric_name),
                None,
            )

            if threshold:
                p99_target = threshold.p99_target_ms or "N/A"
                p99_actual = f"{result.p99_actual_ms:.2f}" if result.p99_actual_ms else "N/A"
                status = "✅ PASS" if result.passed else "❌ FAIL"

                lines.append(
                    f"| {threshold.description} | {threshold.p95_target_ms}ms | "
                    f"{result.p95_actual_ms:.2f}ms | {p99_target}ms | {p99_actual}ms | {status} |"
                )

        lines.extend([
            "",
            "---",
            "",
            "## Detailed Results",
            "",
        ])

        # Add detailed per-metric breakdown
        for result in self.results:
            lines.extend([
                f"### {result.metric_name.replace('_', ' ').title()}",
                "",
                f"- **Status:** {'✅ PASS' if result.passed else '❌ FAIL'}",
                f"- **Samples:** {result.samples}",
                f"- **P95:** {result.p95_actual_ms:.2f}ms",
                f"- **P99:** {result.p99_actual_ms:.2f}ms" if result.p99_actual_ms else "",
                f"- **Min:** {result.min_ms:.2f}ms",
                f"- **Max:** {result.max_ms:.2f}ms",
                f"- **Avg:** {result.avg_ms:.2f}ms",
                "",
            ])

        lines.append("---")
        lines.append("")
        lines.append("## Constitution Compliance")
        lines.append("")
        lines.append("**Principle II: Real-Time Priority**")
        lines.append("")
        if self.get_summary()["overall_status"] == "PASS":
            lines.append("✅ All NFR performance targets met")
        else:
            lines.append("❌ Some NFR performance targets not met")
            lines.append("")
            for result in self.results:
                if not result.passed:
                    threshold = next(
                        (t for t in self.THRESHOLDS if t.metric_name == result.metric_name),
                        None,
                    )
                    if threshold:
                        lines.append(f"- **{threshold.description}**: P95={result.p95_actual_ms:.2f}ms (target: {threshold.p95_target_ms}ms)")

        output_path = self.output_dir / filename
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        logger.info(f"Markdown report generated: {output_path}")
        return output_path

    def generate_html(self, filename: str = "nfr-report.html") -> Path:
        """Generate HTML report with visual charts."""
        summary = self.get_summary()

        html_template = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NFR Performance Report</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background: #f5f5f7;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            padding: 30px;
        }}
        h1 {{
            color: #1a1a1a;
            border-bottom: 2px solid #1890ff;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #333;
            margin-top: 30px;
        }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        .metric-card {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 6px;
            border-left: 4px solid #1890ff;
        }}
        .metric-card.pass {{
            border-left-color: #52c41a;
        }}
        .metric-card.fail {{
            border-left-color: #ff4d4f;
        }}
        .metric-value {{
            font-size: 24px;
            font-weight: bold;
            margin: 10px 0;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background: #f0f0f0;
            font-weight: 600;
        }}
        .status-pass {{
            color: #52c41a;
            font-weight: bold;
        }}
        .status-fail {{
            color: #ff4d4f;
            font-weight: bold;
        }}
        .badge {{
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 600;
        }}
        .badge-pass {{
            background: #f6ffed;
            color: #52c41a;
        }}
        .badge-fail {{
            background: #fff1f0;
            color: #ff4d4f;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>NFR Performance Report</h1>

        <p><strong>Generated:</strong> {self.test_metadata.get('timestamp', 'N/A')}</p>
        <p><strong>Commit:</strong> <code>{self.test_metadata.get('commit_sha', 'N/A')}</code></p>
        <p><strong>Branch:</strong> <code>{self.test_metadata.get('branch', 'N/A')}</code></p>
        <p><strong>Environment:</strong> <code>{self.test_metadata.get('environment', 'ci')}</code></p>

        <h2>Summary</h2>
        <div class="summary">
            <div class="metric-card">
                <div>Total Metrics Tested</div>
                <div class="metric-value">{summary['total_metrics']}</div>
            </div>
            <div class="metric-card pass">
                <div>Passed</div>
                <div class="metric-value">{summary['passed_metrics']}</div>
            </div>
            <div class="metric-card fail">
                <div>Failed</div>
                <div class="metric-value">{summary['failed_metrics']}</div>
            </div>
            <div class="metric-card {'pass' if summary['overall_status'] == 'PASS' else 'fail'}">
                <div>Overall Status</div>
                <div class="metric-value">
                    <span class="status-{'pass' if summary['overall_status'] == 'PASS' else 'fail'}">
                        {summary['overall_status']}
                    </span>
                </div>
            </div>
        </div>

        <h2>Performance Targets (Constitution Principle II)</h2>
        <table>
            <thead>
                <tr>
                    <th>Metric</th>
                    <th>P95 Target</th>
                    <th>P95 Actual</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
        """

        # Add metric rows
        for result in self.results:
            threshold = next(
                (t for t in self.THRESHOLDS if t.metric_name == result.metric_name),
                None,
            )
            if threshold:
                status_badge = '<span class="badge badge-pass">PASS</span>' if result.passed else '<span class="badge badge-fail">FAIL</span>'
                html_template += f"""
                <tr>
                    <td>{threshold.description}</td>
                    <td>{threshold.p95_target_ms}ms</td>
                    <td>{result.p95_actual_ms:.2f}ms</td>
                    <td>{status_badge}</td>
                </tr>
                """

        html_template += """
            </tbody>
        </table>

        <h2>Detailed Results</h2>
        <table>
            <thead>
                <tr>
                    <th>Metric</th>
                    <th>Status</th>
                    <th>Samples</th>
                    <th>P95</th>
                    <th>P99</th>
                    <th>Min</th>
                    <th>Max</th>
                    <th>Avg</th>
                </tr>
            </thead>
            <tbody>
        """

        # Add detailed rows
        for result in self.results:
            status_class = 'status-pass' if result.passed else 'status-fail'
            status_text = 'PASS' if result.passed else 'FAIL'
            p99_text = f"{result.p99_actual_ms:.2f}ms" if result.p99_actual_ms else "N/A"

            html_template += f"""
            <tr>
                <td>{result.metric_name.replace('_', ' ').title()}</td>
                <td class="{status_class}">{status_text}</td>
                <td>{result.samples}</td>
                <td>{result.p95_actual_ms:.2f}ms</td>
                <td>{p99_text}</td>
                <td>{result.min_ms:.2f}ms</td>
                <td>{result.max_ms:.2f}ms</td>
                <td>{result.avg_ms:.2f}ms</td>
            </tr>
            """

        html_template += """
            </tbody>
        </table>
    </div>
</body>
</html>
        """

        output_path = self.output_dir / filename
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_template)

        logger.info(f"HTML report generated: {output_path}")
        return output_path

    def generate_all_reports(self) -> dict[str, Path]:
        """Generate all report formats."""
        return {
            "json": self.generate_json(),
            "markdown": self.generate_markdown(),
            "html": self.generate_html(),
        }


# Convenience function for test scripts
def create_nfr_report(
    results: dict[str, list[float]],
    output_dir: str = "test-results",
) -> dict[str, Path]:
    """
    Create NFR report from test results.

    Args:
        results: Dictionary mapping metric names to sample lists
        output_dir: Directory to save reports

    Returns:
        Dictionary of report file paths
    """
    reporter = NFRReporter(output_dir=output_dir)

    # Set metadata
    import os
    reporter.set_metadata(
        commit_sha=os.getenv("GITHUB_SHA"),
        branch=os.getenv("GITHUB_REF_NAME"),
        environment=os.getenv("ENVIRONMENT", "ci"),
    )

    # Add all results
    for metric_name, samples in results.items():
        reporter.add_result(metric_name, samples)

    # Generate all reports
    return reporter.generate_all_reports()
