"""
Local development entry point for the AI Code Reviewer Action.

This module is used for testing the Action locally.
It loads environment variables from a .env file and simulates GitHub Actions.
"""

import os
import sys
from datetime import datetime
from typing import Dict, List, Any
from dotenv import load_dotenv

from github_client import GitHubClient
from llm_client import GroqClient
from analyzer import detect_language, get_analysis_strategy, extract_signatures
from utils import parse_exclude_patterns, is_excluded
from logger import Logger


def load_env_file() -> None:
    """
    Load environment variables from .env file.

    Exits with error if .env file doesn't exist or is incomplete.
    """
    load_dotenv()
    Logger.info(f"Loaded .env")


def get_env_or_exit_local(var_name: str) -> str:
    """
    Get environment variable or exit with helpful message.

    Args:
        var_name (str): Name of the environment variable

    Returns:
        str: Value of the environment variable
    """
    value = os.getenv(var_name)
    if not value:
        Logger.error(f"Missing {var_name} in .env file")
        print(f"\n💡 Add {var_name}=... to your .env file")
        sys.exit(1)
    return value


def preview_output(content: str, max_chars: int = 500) -> None:
    """
    Print a preview of generated content without committing.

    Args:
        content (str): Content to preview
        max_chars (int): Maximum characters to show
    """
    print("\n   Preview:")
    print("   " + content[:max_chars].replace("\n", "\n   ") + ("..." if len(content) > max_chars else ""))


def main() -> None:
    """Local development entry point."""
    Logger.header("AI Code Docs & Reviewer - LOCAL MODE")

    # Load .env file
    load_env_file()

    # =========================================================
    # 1. GET ENVIRONMENT VARIABLES
    # =========================================================
    token = get_env_or_exit_local("GITHUB_TOKEN")
    repo = get_env_or_exit_local("GITHUB_REPOSITORY")
    pr_number_str = get_env_or_exit_local("GITHUB_PR_NUMBER")
    groq_api_key = get_env_or_exit_local("GROQ_API_KEY")

    groq_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    review_prompt = os.getenv("REVIEW_PROMPT")
    doc_prompt = os.getenv("DOC_PROMPT")
    exclude_str = os.getenv("EXCLUDE_PATTERNS", "")
    doc_output_path = os.getenv("DOC_OUTPUT_PATH", "docs/auto/DOCUMENTATION.md")
    review_output_path = os.getenv("REVIEW_OUTPUT_PATH", "docs/reviews/")

    exclude_patterns = parse_exclude_patterns(exclude_str)
    pr_number = int(pr_number_str)

    # =========================================================
    # 2. DISPLAY CONFIGURATION
    # =========================================================
    print()
    Logger.config("Repository", repo)
    Logger.config("PR Number", pr_number)
    Logger.config("Groq Model", groq_model)
    Logger.config("Exclude patterns", exclude_patterns if exclude_patterns else "None")

    # =========================================================
    # 3. INITIALIZE CLIENTS
    # =========================================================
    try:
        github = GitHubClient(token, repo, pr_number)
        llm = GroqClient(groq_api_key, groq_model, review_prompt, doc_prompt)
    except Exception as e:
        Logger.error(f"Failed to initialize clients: {e}")
        sys.exit(1)

    # =========================================================
    # 4. GET PR INFORMATION
    # =========================================================
    try:
        pr_info = github.get_pr_info()
        print()
        Logger.config("PR Title", pr_info['title'])
        Logger.config("Author", f"@{pr_info['author']}")
        Logger.config("Branch", f"{pr_info['branch']} → {pr_info['base_branch']}")
    except Exception as e:
        Logger.error(f"Failed to get PR info: {e}")
        sys.exit(1)

    # =========================================================
    # 5. GET AND FILTER CHANGED FILES
    # =========================================================
    try:
        all_files = github.get_changed_files()

        relevant_files = []
        excluded_count = 0
        unknown_count = 0

        for f in all_files:
            if is_excluded(f['filename'], exclude_patterns):
                excluded_count += 1
                continue

            lang = detect_language(f['filename'])
            if not lang:
                unknown_count += 1
                continue

            relevant_files.append({**f, 'language': lang})

        print()
        Logger.config("Changed files", len(all_files))
        Logger.config("To analyze", len(relevant_files))
        if excluded_count:
            Logger.warning(f"Excluded: {excluded_count}")
        if unknown_count:
            Logger.warning(f"Unknown language: {unknown_count}")

        if not relevant_files:
            Logger.warning("No files to analyze")
            sys.exit(0)
    except Exception as e:
        Logger.error(f"Failed to get files: {e}")
        sys.exit(1)

    # =========================================================
    # 6. ANALYZE FILES
    # =========================================================
    all_docs: List[Dict[str, Any]] = []
    all_issues: List[Dict[str, Any]] = []
    analysis_errors = 0

    print()
    Logger.info("Starting analysis...")
    Logger.separator()

    for idx, f in enumerate(relevant_files, 1):
        Logger.file_progress(idx, len(relevant_files), f['filename'], f['language'])

        # Get file content
        content = f.get('content')
        if not content:
            content = github._get_file_content(f['filename'])

        if not content:
            Logger.warning("Could not read file")
            analysis_errors += 1
            continue

        # Determine analysis strategy
        size = len(content)
        ratio = (f['additions'] + f['deletions']) / max(size / 10, 1)
        strategy = get_analysis_strategy(f['language'], size, ratio)

        Logger.file_metric("Size", f"{size} chars, {len(content.splitlines())} lines")
        Logger.file_metric("Strategy", strategy)

        # Prepare code for analysis
        if strategy == 'signature':
            code_to_analyze = extract_signatures(content, f['language'])
        else:
            code_to_analyze = content

        # Analyze with LLM
        try:
            result = llm.analyze_code(code_to_analyze, f['language'])
        except Exception as e:
            Logger.error(f"Analysis failed: {e}")
            analysis_errors += 1
            continue

        # Collect documentation
        doc = result.get("documentation", {})
        all_docs.append({"file": f['filename'], "doc": doc})

        # Collect issues
        review = result.get("review", {})
        issues = review.get("issues", [])
        for issue in issues:
            issue["file"] = f['filename']
            issue["language"] = f['language']
            all_issues.append(issue)

        Logger.success(f"Found {len(issues)} issues")

    Logger.summary({
        'files': len(all_docs),
        'issues': len(all_issues),
        'errors': analysis_errors
    })

    # =========================================================
    # 7. PREVIEW DOCUMENTATION (no commit in local mode)
    # =========================================================
    if all_docs:
        doc_content = generate_documentation(all_docs, pr_info)
        print(f"\n📄 Documentation preview (not committed): {doc_output_path}")
        preview_output(doc_content)

    # =========================================================
    # 8. PREVIEW REVIEW REPORT (no commit in local mode)
    # =========================================================
    if all_issues:
        review_content = generate_review_report(all_issues, pr_info)
        review_path = f"{review_output_path}PR-{pr_number}.md"
        print(f"\n🔍 Review report preview (not committed): {review_path}")
        preview_output(review_content)

    print("\n💡 LOCAL MODE: No comments posted, no files committed")
    print("\n✅ Done!")


def generate_documentation(docs: List[Dict[str, Any]], pr_info: Dict[str, Any]) -> str:
    """
    Generate markdown documentation from LLM results.

    Args:
        docs (List[Dict]): List of documentation entries per file
        pr_info (Dict): Pull Request information

    Returns:
        str: Markdown formatted documentation
    """
    content = f"""# Auto-Generated Documentation

> **PR:** #{pr_info['number']} - {pr_info['title']}
> **Author:** @{pr_info['author']}
> **Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}

"""
    for item in docs:
        doc = item['doc']
        content += f"\n## 📄 `{item['file']}`\n\n"
        content += f"**Description:** {doc.get('description', 'N/A')}\n\n"
        content += f"**Functions:** {', '.join(doc.get('functions', [])) or 'None'}\n\n"
        content += f"**Classes:** {', '.join(doc.get('classes', [])) or 'None'}\n\n"
        content += f"**Dependencies:** {', '.join(doc.get('dependencies', [])) or 'None'}\n\n---\n"
    return content


def generate_review_report(issues: List[Dict[str, Any]], pr_info: Dict[str, Any]) -> str:
    """
    Generate markdown review report with code snippets and line numbers.

    Args:
        issues (List[Dict]): List of issues found during analysis
        pr_info (Dict): Pull Request information

    Returns:
        str: Markdown formatted review report
    """
    high = [i for i in issues if i.get('severity') == 'high']
    medium = [i for i in issues if i.get('severity') == 'medium']
    low = [i for i in issues if i.get('severity') == 'low']

    content = f"""# Code Review Report - PR #{pr_info['number']}

> **PR:** {pr_info['title']}
> **Author:** @{pr_info['author']}
> **Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}

## Summary

| Severity | Count |
|----------|-------|
| 🔴 High | {len(high)} |
| 🟡 Medium | {len(medium)} |
| 🟢 Low | {len(low)} |
| **Total** | {len(issues)} |

## Detailed Issues

"""
    for issue in issues:
        icon = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}.get(issue.get('severity'), '⚪')
        line_info = f" (line {issue.get('line')})" if issue.get('line', 0) > 0 else ""
        content += f"\n### {icon} {issue.get('type', 'issue').upper()}{line_info}\n\n"

        content += "| Property | Value |\n"
        content += "|----------|-------|\n"
        content += f"| **File** | `{issue.get('file')}` |\n"
        if issue.get('code_snippet'):
            snippet = issue.get('code_snippet').replace('|', '\\|')
            content += f"| **Code** | `{snippet[:100]}` |\n"
        content += f"| **Description** | {issue.get('description')} |\n"
        content += f"| **Suggestion** | {issue.get('suggestion')} |\n\n"

    return content


if __name__ == "__main__":
    main()