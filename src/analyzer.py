"""
Language detection and analysis strategies for different programming languages.
"""

import os
from typing import Dict, List, Optional

# Mapping from file extension to language name (for LLM prompts)
LANGUAGE_MAP = {
    '.py': 'python',
    '.pyx': 'cython',
    '.js': 'javascript',
    '.jsx': 'javascript',
    '.ts': 'typescript',
    '.tsx': 'typescript',
    '.mjs': 'javascript',
    '.cjs': 'javascript',
    '.html': 'html',
    '.css': 'css',
    '.scss': 'scss',
    '.vue': 'vue',
    '.java': 'java',
    '.kt': 'kotlin',
    '.groovy': 'groovy',
    '.c': 'c',
    '.cpp': 'cpp',
    '.h': 'c',
    '.hpp': 'cpp',
    '.go': 'go',
    '.rs': 'rust',
    '.rb': 'ruby',
    '.php': 'php',
    '.swift': 'swift',
    '.sh': 'bash',
    '.bash': 'bash',
    '.zsh': 'bash',
    '.sql': 'sql',
    '.json': 'json',
    '.yaml': 'yaml',
    '.yml': 'yaml',
    '.toml': 'toml',
    '.xml': 'xml',
    '.md': 'markdown',
}

WELL_SUPPORTED = {'python', 'javascript', 'typescript', 'go', 'java', 'rust'}
SCRIPT_LANGUAGES = {'bash', 'sql', 'html', 'css', 'json', 'yaml', 'markdown'}


def detect_language(filename: str) -> Optional[str]:
    """Detect programming language from file extension."""
    ext = os.path.splitext(filename)[1].lower()
    return LANGUAGE_MAP.get(ext)


def get_analysis_strategy(language: str, file_size: int, changes_ratio: float) -> str:
    """Determine which analysis strategy to use."""
    if language in SCRIPT_LANGUAGES:
        return 'full'
    if file_size < 500:
        return 'full'
    if changes_ratio > 0.2:
        return 'full'
    if file_size > 5000 and changes_ratio < 0.05:
        return 'signature'
    return 'diff'


def extract_signatures(code: str, language: str) -> str:
    """Extract function/class signatures from code without full implementation."""
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