#!/usr/bin/env python3
"""Fail when committed env/docs/CI files contain real-looking secrets.

The scanner is intentionally dependency-free so it can run in local development
and CI before release. It only scans committed release-facing examples/docs by
default; source-code fixture secrets belong in targeted tests.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


DEFAULT_PATHS = (
    ".env.example",
    "backend/.env.example",
    "docs",
    ".github/workflows",
)

SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("openai-style-key", re.compile(r"\bsk-[A-Za-z0-9][A-Za-z0-9_-]{16,}\b")),
    ("linear-api-key", re.compile(r"\blin_api_[A-Za-z0-9]{16,}\b")),
    ("aws-access-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("alibaba-access-key", re.compile(r"\bLTAI[0-9A-Za-z]{16,}\b")),
    ("jwt-secret-assignment", re.compile(r"(?i)\b(jwt_secret|secret_key)\s*=\s*[^\s<#][^\s]{20,}")),
)

PLACEHOLDER_MARKERS = (
    "<",
    "your-",
    "replace-",
    "change-me",
    "example",
    "placeholder",
    "...",
)


@dataclass(frozen=True, slots=True)
class Finding:
    path: Path
    line_number: int
    pattern_name: str
    excerpt: str


def is_placeholder(line: str) -> bool:
    lowered = line.lower()
    return any(marker in lowered for marker in PLACEHOLDER_MARKERS)


def scan_text(path: Path, text: str) -> list[Finding]:
    findings: list[Finding] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if is_placeholder(line):
            continue
        for name, pattern in SECRET_PATTERNS:
            if pattern.search(line):
                findings.append(
                    Finding(
                        path=path,
                        line_number=line_number,
                        pattern_name=name,
                        excerpt=line.strip()[:160],
                    )
                )
    return findings


def iter_files(root: Path, paths: tuple[str, ...]) -> list[Path]:
    files: list[Path] = []
    for item in paths:
        path = root / item
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            files.extend(p for p in path.rglob("*") if p.is_file())
    return sorted({p.resolve() for p in files})


def git_root() -> Path:
    output = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True)
    return Path(output.strip())


def scan_paths(root: Path, paths: tuple[str, ...]) -> list[Finding]:
    findings: list[Finding] = []
    for path in iter_files(root, paths):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        findings.extend(scan_text(path.relative_to(root), text))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", default=list(DEFAULT_PATHS))
    args = parser.parse_args(argv)

    root = git_root()
    findings = scan_paths(root, tuple(args.paths))
    if findings:
        print("Secret hygiene scan failed:", file=sys.stderr)
        for finding in findings:
            print(
                f"{finding.path}:{finding.line_number}: {finding.pattern_name}: {finding.excerpt}",
                file=sys.stderr,
            )
        return 1

    print(f"Secret hygiene scan passed ({len(iter_files(root, tuple(args.paths)))} files scanned)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
