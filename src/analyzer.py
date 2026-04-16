"""
Language detection and analysis strategies for different programming languages.

This module provides functionality for:
- Detecting programming language from file extensions
- Selecting optimal analysis strategy based on file size and change ratio
- Extracting function/class signatures from code (for large files)
- Identifying supported file types
"""

import os
from typing import List, Optional

# Mapping from file extension to language name (for LLM prompts)
# Supports 25+ file extensions across multiple programming languages
LANGUAGE_MAP = {
    # Python family
    '.py': 'python',
    '.pyx': 'cython',
    # JavaScript/TypeScript family
    '.js': 'javascript',
    '.jsx': 'javascript',
    '.ts': 'typescript',
    '.tsx': 'typescript',
    '.mjs': 'javascript',
    '.cjs': 'javascript',
    # Web technologies
    '.html': 'html',
    '.css': 'css',
    '.scss': 'scss',
    '.vue': 'vue',
    # JVM languages
    '.java': 'java',
    '.kt': 'kotlin',
    # Systems languages
    '.go': 'go',
    '.rs': 'rust',
    # Scripting languages
    '.rb': 'ruby',
    '.php': 'php',
    '.sh': 'bash',
    # Data/Query languages
    '.sql': 'sql',
    '.json': 'json',
    '.yaml': 'yaml',
    '.yml': 'yaml',
    # Documentation
    '.md': 'markdown',
}

# Languages that don't have functions/classes concept (scripting or markup)
# These always use 'full' analysis strategy
SCRIPT_LANGUAGES = {'bash', 'sql', 'html', 'css', 'json', 'yaml', 'markdown'}


def detect_language(filename: str) -> Optional[str]:
    """
    Detects programming language from file extension.

    Args:
        filename (str): Path to the file (e.g., "src/main.py" or "script.js")

    Returns:
        Optional[str]: Language name (e.g., "python", "javascript") or None if unknown

    Example:
        >>> detect_language("src/main.py")
        'python'
        >>> detect_language("unknown.xyz")
        None
    """
    ext = os.path.splitext(filename)[1].lower()
    return LANGUAGE_MAP.get(ext)


def get_analysis_strategy(language: str, file_size: int, changes_ratio: float) -> str:
    """
    Determines which analysis strategy to use based on language and file characteristics.

    Strategies:
        - 'full': Send entire file to LLM (most accurate, higher token cost)
        - 'signature': Send only function/class signatures (lower token cost, less context)
        - 'diff': Send only changed lines with context (planned for future implementation)

    Decision logic:
        1. Script languages (bash, sql, etc.) → 'full'
        2. Small files (< 500 chars) → 'full'
        3. Large changes (> 20% of file) → 'full'
        4. Very large files (> 5000 chars) with tiny changes (< 5%) → 'signature'
        5. Everything else → 'diff' (currently falls back to 'full')

    Args:
        language (str): Programming language from detect_language()
        file_size (int): File size in characters
        changes_ratio (float): Ratio of changed lines to total lines (0.0 to 1.0)

    Returns:
        str: Strategy name - 'full', 'signature', or 'diff'

    Example:
        >>> get_analysis_strategy('python', 100, 0.5)
        'full'
        >>> get_analysis_strategy('python', 10000, 0.02)
        'signature'
    """
    # Script languages are usually small and need full context
    if language in SCRIPT_LANGUAGES:
        return 'full'
    # Small files: cheap to analyze fully
    if file_size < 500:
        return 'full'
    # Large changes: need full context to understand impact
    if changes_ratio > 0.2:
        return 'full'
    # Huge files with tiny changes: signatures are enough
    if file_size > 5000 and changes_ratio < 0.05:
        return 'signature'
    # Default strategy (currently falls back to full)
    return 'diff'


def extract_signatures(code: str, language: str) -> str:
    """
    Extracts function/class signatures from code without full implementation.

    This is used for the 'signature' strategy to reduce token usage while
    preserving structural context about the code.

    Args:
        code (str): Full source code content
        language (str): Programming language (e.g., "python", "javascript")

    Returns:
        str: Extracted signatures as a string, or first 30 lines as fallback.
             Limited to 100 signatures maximum.

    Language-specific extraction:
        - Python: 'def ' and 'class ' lines
        - JavaScript/TypeScript: 'function ', 'const ... =>', 'class ', 'export '
        - Go: 'func ' and 'type ' lines
        - Java: public/private/protected and class declarations
        - Rust: 'fn ', 'pub fn ', 'struct ', 'enum ' lines
        - Others: First 30 lines as fallback

    Example:
        >>> code = "def add(a, b):\\n    return a + b\\n\\ndef sub(a, b):\\n    return a - b"
        >>> extract_signatures(code, 'python')
        'def add(a, b):\\ndef sub(a, b):'
    """
    lines = code.split('\n')
    signatures = []

    if language == 'python':
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('def ') or stripped.startswith('class '):
                if '(' in stripped:
                    signatures.append(stripped)
                elif stripped.startswith('def '):
                    signatures.append(stripped + '(...)')
                else:
                    signatures.append(stripped)
    elif language in ('javascript', 'typescript'):
        for line in lines:
            stripped = line.strip()
            if (stripped.startswith('function ') or
                stripped.startswith('const ') and '=>' in stripped or
                stripped.startswith('class ') or
                stripped.startswith('export ')):
                signatures.append(stripped[:200])
    elif language == 'go':
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('func ') or stripped.startswith('type '):
                signatures.append(stripped[:200])
    elif language == 'java':
        for line in lines:
            stripped = line.strip()
            if (stripped.startswith('public ') or stripped.startswith('private ') or
                stripped.startswith('protected ') or stripped.startswith('class ')):
                signatures.append(stripped[:200])
    elif language == 'rust':
        for line in lines:
            stripped = line.strip()
            if (stripped.startswith('fn ') or stripped.startswith('pub fn ') or
                stripped.startswith('struct ') or stripped.startswith('enum ')):
                signatures.append(stripped[:200])
    else:
        # Unknown language: return first 30 lines as context
        signatures = lines[:30]

    if not signatures:
        return "Unable to extract signatures. Here's the first 30 lines:\n" + '\n'.join(lines[:30])

    # Limit to 100 signatures to avoid token overflow
    return '\n'.join(signatures[:100])


def is_supported(filename: str) -> bool:
    """
    Checks if a file extension is supported for analysis.

    Args:
        filename (str): Path to the file (e.g., "src/main.py")

    Returns:
        bool: True if the file extension is in LANGUAGE_MAP, False otherwise

    Example
        >>> is_supported("src/main.py")
        True
        >>> is_supported("image.png")
        False
    """
    return detect_language(filename) is not None