"""
Language detection and analysis strategies for different programming languages.
"""

import os
from typing import Dict, List, Optional

# Mapping from file extension to language name (for LLM prompts)
LANGUAGE_MAP = {
    # Python
    '.py': 'python',
    '.pyx': 'cython',

    # JavaScript/TypeScript
    '.js': 'javascript',
    '.jsx': 'javascript',
    '.ts': 'typescript',
    '.tsx': 'typescript',
    '.mjs': 'javascript',
    '.cjs': 'javascript',

    # Web
    '.html': 'html',
    '.css': 'css',
    '.scss': 'scss',
    '.vue': 'vue',

    # Java/Kotlin
    '.java': 'java',
    '.kt': 'kotlin',
    '.groovy': 'groovy',

    # C/C++
    '.c': 'c',
    '.cpp': 'cpp',
    '.h': 'c',
    '.hpp': 'cpp',

    # Go
    '.go': 'go',

    # Rust
    '.rs': 'rust',

    # Ruby
    '.rb': 'ruby',

    # PHP
    '.php': 'php',

    # Swift
    '.swift': 'swift',

    # Shell
    '.sh': 'bash',
    '.bash': 'bash',
    '.zsh': 'bash',

    # SQL
    '.sql': 'sql',

    # Configuration
    '.json': 'json',
    '.yaml': 'yaml',
    '.yml': 'yaml',
    '.toml': 'toml',
    '.xml': 'xml',

    # Markdown
    '.md': 'markdown',
}

# Languages that are well-supported with good prompts
WELL_SUPPORTED = {'python', 'javascript', 'typescript', 'go', 'java', 'rust'}

# Languages that need special handling (e.g., no functions/classes concept)
SCRIPT_LANGUAGES = {'bash', 'sql', 'html', 'css', 'json', 'yaml', 'markdown'}


def detect_language(filename: str) -> Optional[str]:
    """
    Detect programming language from file extension.

    Args:
        filename: Path to the file (e.g., "src/main.py")

    Returns:
        Language name (e.g., "python") or None if unknown
    """
    ext = os.path.splitext(filename)[1].lower()
    return LANGUAGE_MAP.get(ext)


def get_analysis_strategy(language: str, file_size: int, changes_ratio: float) -> str:
    """
    Determine which analysis strategy to use based on language and file characteristics.

    Args:
        language: Detected language
        file_size: Number of characters in file
        changes_ratio: Ratio of changed lines to total lines (0-1)

    Returns:
        Strategy: "full", "diff", "signature", or "skip"
    """
    # For script languages, always use full (they're usually small)
    if language in SCRIPT_LANGUAGES:
        return 'full'

    # Small files (< 500 chars) → full analysis
    if file_size < 500:
        return 'full'

    # Large changes (> 20% of file) → full analysis
    if changes_ratio > 0.2:
        return 'full'

    # Very large files (> 5000 chars) with small changes → signature only
    if file_size > 5000 and changes_ratio < 0.05:
        return 'signature'

    # Default → diff analysis
    return 'diff'


def extract_signatures(code: str, language: str) -> str:
    """
    Extract function/class signatures from code without full implementation.

    Args:
        code: Full file content
        language: Programming language

    Returns:
        String with extracted signatures
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
        # Fallback: return first 30 lines as "signatures"
        signatures = lines[:30]

    if not signatures:
        return "Unable to extract signatures. Here's the first 30 lines:\n" + '\n'.join(lines[:30])

    return '\n'.join(signatures[:100])


def get_supported_extensions() -> List[str]:
    """Return list of supported file extensions"""
    return list(LANGUAGE_MAP.keys())


def is_supported(filename: str) -> bool:
    """Check if file extension is supported"""
    return detect_language(filename) is not None