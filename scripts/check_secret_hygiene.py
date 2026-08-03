#!/usr/bin/env python3
"""Fail when committed env/docs/CI files contain real-looking secrets.

The scanner is intentionally dependency-free so it can run in local development
and CI before release. It only scans committed release-facing examples/docs by
default; source-code fixture secrets belong in targeted tests.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path

DEFAULT_PATHS = (
    ".env.example",
    "backend/.env.example",
    "docs",
    ".github/workflows",
    "evidence",
    ".sisyphus/evidence",
)

EXCLUDED_REPORT_NAMES = frozenset({"secret-scan-report.json"})
EXCLUDED_REPORT_NAME_MARKERS = (
    "secret-scan",
    "secret_scan",
    "secret-hygiene",
    "secret_hygiene",
)
MAX_ARCHIVE_MEMBER_BYTES = 20 * 1024 * 1024

SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "stepfun-api-key-assignment",
        re.compile(
            r"(?i)\bSTEPFUN_API_KEY\s*[:=]\s*[\"']?"
            r"(?P<secret>[A-Za-z0-9][A-Za-z0-9_.=-]{20,})"
        ),
    ),
    (
        "openai-style-key",
        re.compile(r"\b(?P<secret>sk-[A-Za-z0-9][A-Za-z0-9_-]{16,})\b"),
    ),
    ("linear-api-key", re.compile(r"\b(?P<secret>lin_api_[A-Za-z0-9]{16,})\b")),
    ("aws-access-key", re.compile(r"\b(?P<secret>AKIA[0-9A-Z]{16})\b")),
    ("alibaba-access-key", re.compile(r"\b(?P<secret>LTAI[0-9A-Za-z]{16,})\b")),
    (
        "bearer-token",
        re.compile(
            r"(?i)\bAuthorization\s*[:=]\s*[\"']?Bearer\s+"
            r"(?P<secret>[A-Za-z0-9][A-Za-z0-9._~+/=-]{20,})"
        ),
    ),
    (
        "jwt-secret-assignment",
        re.compile(
            r"(?i)\b(?:jwt_secret|jwt_secret_key|secret_key)\s*[:=]\s*[\"']?"
            r"(?P<secret>[^\s<#\"']{20,})"
        ),
    ),
    (
        "jwt-token-assignment",
        re.compile(
            r"(?i)\b[A-Z0-9_]*(?:TOKEN|JWT)[A-Z0-9_]*\s*[:=]\s*[\"']?"
            r"(?P<secret>eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)"
        ),
    ),
    (
        "jwt-token",
        re.compile(
            r"\b(?P<secret>eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)\b"
        ),
    ),
    (
        "url-query-token",
        re.compile(
            r"(?i)\b(?:https?|wss?)://[^\s'\"<>]*[?&]"
            r"(?:access_token|refresh_token|id_token|token|api_key|apikey|"
            r"authorization|jwt|client_secret|secret)="
            r"(?P<secret>[^&\s'\"<>]{12,})"
        ),
    ),
)

PLACEHOLDER_WRAPPERS = ("<", ">", "{", "}", "${")
PLACEHOLDER_PREFIXES = (
    "your-",
    "your_",
    "replace-",
    "replace_",
    "change-me",
    "change_me",
    "example-",
    "example_",
    "dummy-",
    "dummy_",
    "fake-",
    "fake_",
)
PLACEHOLDER_EXACT_VALUES = frozenset(
    {
        "token",
        "jwt",
        "jwt_token",
        "api_key",
        "secret",
        "stepfun_api_key",
        "example",
        "...",
    }
)

SECRET_EXCERPT_REDACTION = re.compile(
    r"([A-Za-z0-9_-]{6})[A-Za-z0-9_.~+/=-]{8,}([A-Za-z0-9_-]{4})"
)


@dataclass(frozen=True)
class Finding:
    path: Path
    line_number: int
    pattern_name: str
    excerpt: str


def is_placeholder(line: str) -> bool:
    value = line.strip().strip("\"'")
    lowered = value.lower()
    if not value:
        return True
    if any(marker in value for marker in PLACEHOLDER_WRAPPERS):
        return True
    if lowered in PLACEHOLDER_EXACT_VALUES:
        return True
    if lowered.startswith(PLACEHOLDER_PREFIXES):
        return True
    return "placeholder" in lowered or "..." in lowered


def _match_secret(match: re.Match[str]) -> str:
    return match.groupdict().get("secret") or match.group(0)


def redact_excerpt(line: str) -> str:
    return SECRET_EXCERPT_REDACTION.sub(r"\1***\2", line.strip()[:160])


def scan_text(path: Path, text: str) -> list[Finding]:
    findings: list[Finding] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for name, pattern in SECRET_PATTERNS:
            for match in pattern.finditer(line):
                if is_placeholder(_match_secret(match)):
                    continue
                findings.append(
                    Finding(
                        path=path,
                        line_number=line_number,
                        pattern_name=name,
                        excerpt=redact_excerpt(line),
                    )
                )
    return findings


def is_excluded_report_path(path: Path) -> bool:
    name = path.name.lower()
    if name in EXCLUDED_REPORT_NAMES:
        return True
    return path.suffix.lower() == ".json" and any(
        marker in name for marker in EXCLUDED_REPORT_NAME_MARKERS
    )


def iter_files(
    root: Path,
    paths: tuple[str, ...],
    exclude_paths: tuple[Path, ...] = (),
) -> list[Path]:
    files: list[Path] = []
    excluded = {path.resolve() for path in exclude_paths}
    for item in paths:
        path = root / item
        if path.is_file():
            resolved_path = path.resolve()
            if resolved_path not in excluded and not is_excluded_report_path(path):
                files.append(path)
        elif path.is_dir():
            files.extend(
                p
                for p in path.rglob("*")
                if p.is_file()
                and p.resolve() not in excluded
                and not is_excluded_report_path(p)
            )
    return sorted({p.resolve() for p in files})


def git_root() -> Path:
    output = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True)
    return Path(output.strip())


def scan_paths(
    root: Path,
    paths: tuple[str, ...],
    exclude_paths: tuple[Path, ...] = (),
) -> list[Finding]:
    findings: list[Finding] = []
    for path in iter_files(root, paths, exclude_paths=exclude_paths):
        if path.suffix.lower() == ".zip":
            try:
                with zipfile.ZipFile(path) as archive:
                    for member in archive.infolist():
                        if member.is_dir() or member.file_size > MAX_ARCHIVE_MEMBER_BYTES:
                            continue
                        try:
                            text = archive.read(member).decode("utf-8")
                        except UnicodeDecodeError:
                            continue
                        try:
                            display_path = path.relative_to(root)
                        except ValueError:
                            display_path = path
                        findings.extend(
                            scan_text(
                                Path(f"{display_path.as_posix()}::{member.filename}"),
                                text,
                            )
                        )
            except zipfile.BadZipFile:
                continue
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        try:
            display_path = path.relative_to(root)
        except ValueError:
            display_path = path
        findings.extend(scan_text(display_path, text))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", help="Write a JSON secret scan report to this path")
    parser.add_argument("paths", nargs="*", default=list(DEFAULT_PATHS))
    args = parser.parse_args(argv)

    root = git_root()
    report_path = Path(args.report) if args.report else None
    if report_path is not None and not report_path.is_absolute():
        report_path = root / report_path
    exclude_paths = (report_path,) if report_path is not None else ()

    findings = scan_paths(root, tuple(args.paths), exclude_paths=exclude_paths)
    scanned_files = iter_files(root, tuple(args.paths), exclude_paths=exclude_paths)
    report = {
        "passed": not findings,
        "files_scanned": len(scanned_files),
        "findings": [
            asdict(finding) | {"path": str(finding.path)} for finding in findings
        ],
    }
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    if findings:
        print("Secret hygiene scan failed:", file=sys.stderr)
        for finding in findings:
            location = f"{finding.path}:{finding.line_number}"
            print(
                f"{location}: {finding.pattern_name}: {finding.excerpt}",
                file=sys.stderr,
            )
        return 1

    print(
        f"Secret hygiene scan passed ({len(scanned_files)} files scanned)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
