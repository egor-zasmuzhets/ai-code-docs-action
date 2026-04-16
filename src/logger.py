"""
Logging and output formatting utilities for the AI Code Reviewer Action.

This module provides functions for consistent log output with emojis,
colors (when supported), and structured formatting.
"""

import sys
from typing import Any, Dict, List, Optional


class Logger:
    """
    Unified logger for consistent output formatting.

    Provides methods for different log levels with emoji indicators.
    """

    @staticmethod
    def header(text: str, width: int = 55) -> None:
        """Print a header with equals signs."""
        print("=" * width)
        print(f"🤖 {text}")
        print("=" * width)

    @staticmethod
    def info(text: str) -> None:
        """Print an info message."""
        print(f"   ℹ️ {text}")

    @staticmethod
    def success(text: str) -> None:
        """Print a success message."""
        print(f"   ✅ {text}")

    @staticmethod
    def warning(text: str) -> None:
        """Print a warning message."""
        print(f"   ⚠️ {text}")

    @staticmethod
    def error(text: str) -> None:
        """Print an error message."""
        print(f"   ❌ {text}")

    @staticmethod
    def debug(text: str) -> None:
        """Print a debug message (only when DEBUG env var is set)."""
        import os
        if os.getenv("DEBUG"):
            print(f"   🔍 {text}")

    @staticmethod
    def separator(char: str = "-", width: int = 55) -> None:
        """Print a separator line."""
        print(char * width)

    @staticmethod
    def config(key: str, value: Any) -> None:
        """Print a configuration line."""
        print(f"   {key}: {value}")

    @staticmethod
    def file_progress(current: int, total: int, filename: str, language: str) -> None:
        """Print file analysis progress."""
        print(f"\n[{current}/{total}] 📄 {filename} ({language})")

    @staticmethod
    def file_metric(metric: str, value: Any) -> None:
        """Print a file analysis metric."""
        print(f"   {metric}: {value}")

    @staticmethod
    def issue_found(severity: str, issue_type: str, line: Optional[int] = None) -> None:
        """Print an issue found message."""
        icons = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}
        icon = icons.get(severity, '⚪')
        line_info = f" at line {line}" if line else ""
        print(f"      {icon} {severity.upper()} - {issue_type}{line_info}")

    @staticmethod
    def inline_posted(line: int) -> None:
        """Print inline comment posted message."""
        print(f"      💬 Inline comment posted at line {line}")

    @staticmethod
    def summary(stats: Dict[str, int]) -> None:
        """Print final summary statistics."""
        Logger.separator()
        print(f"\n📊 Complete: {stats.get('files', 0)} files, {stats.get('issues', 0)} issues")
        if stats.get('errors', 0) > 0:
            Logger.warning(f"Errors: {stats.get('errors', 0)}")

    @staticmethod
    def missing_vars(vars_list: List[str], is_local: bool = False) -> None:
        """Print missing environment variables message."""
        Logger.error(f"Missing: {', '.join(vars_list)}")
        if is_local:
            print("\n💡 Create .env file with:")
            for var in vars_list:
                print(f"   {var}=...")