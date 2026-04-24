#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_PARTS = {
    ".git",
    ".github",
    ".next",
    ".pnpm-store",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "coverage",
    "dist",
    "node_modules",
    "storage",
}
TEXT_SUFFIXES = {
    ".env.example",
    ".json",
    ".md",
    ".py",
    ".sh",
    ".toml",
    ".tsx",
    ".ts",
    ".txt",
    ".yaml",
    ".yml",
}
ALLOWLIST_VALUES = {
    "",
    "abc",
    "change-me",
    "changeme",
    "ci-secret-key-not-default",
    "creatoros",
    "dev-secret-key",
    "password",
    "raw-key",
    "raw-token",
    "replace-me",
    "session-secret",
    "session-value",
}
ALLOWLIST_HOSTS = {"example.com", "localhost", "127.0.0.1"}
PATTERNS = {
    "private_key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "openai_key": re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    "github_token": re.compile(r"\b(?:ghp|github_pat)_[A-Za-z0-9_]{20,}\b"),
    "aws_access_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "quoted_sensitive_assignment": re.compile(
        r"(?i)(?:['\"])?"
        r"([A-Za-z0-9_-]*(?:secret|token|api[_-]?key|password|passwd|cookie|session)[A-Za-z0-9_-]*)"
        r"(?:['\"])?\s*[:=]\s*['\"]([A-Za-z0-9_.:/@+-]{4,})['\"]"
    ),
    "env_sensitive_assignment": re.compile(
        r"\b([A-Z0-9_]*(?:SECRET|TOKEN|API_KEY|PASSWORD|PASSWD|COOKIE|SESSION)[A-Z0-9_]*)"
        r"\s*=\s*([A-Za-z0-9_.:/@+-]{4,})"
    ),
    "credential_url": re.compile(r"\b[a-z][a-z0-9+.-]*://([^/\s:@]+):([^/\s@]+)@([^/\s:?#]+)"),
}


def should_scan(path: Path) -> bool:
    if any(part in SKIP_PARTS for part in path.parts):
        return False
    if path.name.endswith(".env.example"):
        return True
    return path.suffix in TEXT_SUFFIXES


def scan_file(path: Path) -> list[str]:
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []

    findings: list[str] = []
    for lineno, line in enumerate(content.splitlines(), start=1):
        if "secret-scan: ignore" in line:
            continue

        for name, pattern in PATTERNS.items():
            for match in pattern.finditer(line):
                if name in {"quoted_sensitive_assignment", "env_sensitive_assignment"}:
                    value = match.group(2).strip().strip("'\"")
                    if value.lower() in ALLOWLIST_VALUES:
                        continue
                if name == "credential_url":
                    username = match.group(1).strip().lower()
                    password = match.group(2).strip().lower()
                    host = match.group(3).strip().lower()
                    if host in ALLOWLIST_HOSTS and {
                        username,
                        password,
                    }.issubset({"creatoros", "password", "user"}):
                        continue
                findings.append(f"{path.relative_to(ROOT)}:{lineno}: potential {name}")
    return findings


def main() -> int:
    findings: list[str] = []
    for root, dirnames, filenames in os.walk(ROOT, followlinks=False):
        dirnames[:] = [
            dirname
            for dirname in dirnames
            if dirname not in SKIP_PARTS and not Path(root, dirname).is_symlink()
        ]

        for filename in filenames:
            path = Path(root, filename)
            if path.is_symlink() or not should_scan(path):
                continue
            findings.extend(scan_file(path))

    if findings:
        print("Secret scan found suspicious hardcoded values:", file=sys.stderr)
        for finding in findings:
            print(f"  - {finding}", file=sys.stderr)
        return 1

    print("Secret scan passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
