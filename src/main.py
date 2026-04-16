"""
Main entry point for the GitHub Action.
"""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv

if not os.getenv("GITHUB_ACTIONS"):
    load_dotenv()
    print("📁 LOCAL MODE")

from github_client import GitHubClient
from llm_client import GroqClient
from analyzer import detect_language, get_analysis_strategy, extract_signatures
from utils import parse_exclude_patterns, is_excluded


def main():
    print("=" * 55)
    print("🤖 AI Code Docs & Reviewer - Running")
    print("=" * 55)

    # Get environment variables
    token = os.getenv("GITHUB_TOKEN")
    repo = os.getenv("GITHUB_REPOSITORY")
    pr_number_str = os.getenv("GITHUB_PR_NUMBER")
    groq_api_key = os.getenv("GROQ_API_KEY")
    groq_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    review_prompt = os.getenv("REVIEW_PROMPT")
    doc_prompt = os.getenv("DOC_PROMPT")
    exclude_str = os.getenv("EXCLUDE_PATTERNS", "")
    doc_output_path = os.getenv("DOC_OUTPUT_PATH", "docs/auto/DOCUMENTATION.md")
    review_output_path = os.getenv("REVIEW_OUTPUT_PATH", "docs/reviews/")

    exclude_patterns = parse_exclude_patterns(exclude_str)

    print(f"\n📋 Configuration:")
    print(f"   Repository: {repo}")
    print(f"   PR Number: {pr_number_str}")
    print(f"   Groq Model: {groq_model}")
    print(f"   Exclude patterns: {exclude_patterns if exclude_patterns else 'None'}")

    # Validate
    missing_vars = []
    if not token:
        missing_vars.append("GITHUB_TOKEN")
    if not repo:
        missing_vars.append("GITHUB_REPOSITORY")
    if not pr_number_str:
        missing_vars.append("GITHUB_PR_NUMBER")
    if not groq_api_key:
        missing_vars.append("GROQ_API_KEY")

    if missing_vars:
        print(f"\n❌ Missing: {', '.join(missing_vars)}")
        if not os.getenv("GITHUB_ACTIONS"):
            print("\n💡 Create .env file with:\n   GROQ_API_KEY=...\n   GITHUB_TOKEN=...")
        sys.exit(1)

    pr_number = int(pr_number_str)

    # Initialize clients
    try:
        github = GitHubClient(token, repo, pr_number)
        llm = GroqClient(groq_api_key, groq_model, review_prompt, doc_prompt)
    except Exception as e:
        print(f"\n❌ Failed to initialize: {e}")
        sys.exit(1)

    # Get PR info
    try:
        pr_info = github.get_pr_info()
        print(f"\n📋 PR: {pr_info['title']}")
        print(f"   Author: {pr_info['author']}")
        print(f"   Branch: {pr_info['branch']} → {pr_info['base_branch']}")
    except Exception as e:
        print(f"\n❌ Failed to get PR info: {e}")
        sys.exit(1)

    # Get changed files
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

        print(f"\n📁 Changed files: {len(all_files)} total")
        print(f"🔍 To analyze: {len(relevant_files)}")
        if excluded_count:
            print(f"   🚫 Excluded: {excluded_count}")
        if unknown_count:
            print(f"   ⚠️ Unknown language: {unknown_count}")

        if not relevant_files:
            print("\n⚠️ No files to analyze")
            sys.exit(0)
    except Exception as e:
        print(f"\n❌ Failed to get files: {e}")
        sys.exit(1)

    # Analyze files
    all_docs = []
    all_issues = []

    print("\n🔍 Starting analysis...")
    print("-" * 55)

    for idx, f in enumerate(relevant_files, 1):
        print(f"\n[{idx}/{len(relevant_files)}] {f['filename']} ({f['language']})")

        content = f.get('content')
        if not content:
            content = github._get_file_content(f['filename'])

        if not content:
            print("   ⚠️ Could not read file")
            continue

        size = len(content)
        ratio = (f['additions'] + f['deletions']) / max(size / 10, 1)
        strategy = get_analysis_strategy(f['language'], size, ratio)

        print(f"   📏 Size: {size} chars, {len(content.splitlines())} lines")
        print(f"   📊 Strategy: {strategy}")

        if strategy == 'signature':
            code_to_analyze = extract_signatures(content, f['language'])
        else:
            code_to_analyze = content

        try:
            result = llm.analyze_code(code_to_analyze, f['language'])
        except Exception as e:
            print(f"   ❌ Analysis failed: {e}")
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

            # Post inline comment if line number is available
            if os.getenv("GITHUB_ACTIONS") and issue.get('line', 0) > 0:
                icon = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}.get(issue.get('severity'), '⚪')
                body = f"""**{icon} {issue.get('severity', '').upper()}** - {issue.get('type', 'issue')}

**Issue:** {issue.get('description')}

"""
                if issue.get('code_snippet'):
                    body += f"**Code:**\n```{f['language']}\n{issue.get('code_snippet')}\n```\n\n"
                body += f"**Suggestion:** {issue.get('suggestion')}"

                github.post_inline_comment(f['filename'], issue['line'], body)
                print(f"      💬 Inline comment at line {issue['line']}")

        print(f"   ✅ Found {len(issues)} issues")

    print("-" * 55)
    print(f"\n📊 Complete: {len(all_docs)} files, {len(all_issues)} issues")

    # Generate documentation
    if all_docs:
        doc_content = generate_documentation(all_docs, pr_info)
        if os.getenv("GITHUB_ACTIONS"):
            github.commit_documentation(doc_output_path, doc_content, f"docs: update PR #{pr_number}")
            print(f"\n📄 Docs: {doc_output_path}")

    # Generate review report
    if all_issues:
        review_content = generate_review_report(all_issues, pr_info)
        review_path = f"{review_output_path}PR-{pr_number}.md"
        if os.getenv("GITHUB_ACTIONS"):
            github.commit_documentation(review_path, review_content, f"review: PR #{pr_number}")
            print(f"🔍 Report: {review_path}")

    # Post summary
    if os.getenv("GITHUB_ACTIONS"):
        comment = generate_summary(len(all_docs), len(all_issues), pr_number, pr_info['title'])
        github.post_review_summary(comment)
        print("\n💬 Comment posted")

    print("\n✅ Done!")


def generate_documentation(docs, pr_info):
    """Generate markdown documentation from LLM results."""
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


def generate_review_report(issues, pr_info):
    """Generate markdown review report with code snippets and line numbers."""
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

        # Create a table for each issue
        content += "| Property | Value |\n"
        content += "|----------|-------|\n"
        content += f"| **File** | `{issue.get('file')}` |\n"
        if issue.get('code_snippet'):
            snippet = issue.get('code_snippet').replace('|', '\\|')
            content += f"| **Code** | `{snippet[:100]}` |\n"
        content += f"| **Description** | {issue.get('description')} |\n"
        content += f"| **Suggestion** | {issue.get('suggestion')} |\n\n"

    return content


def generate_summary(num_files, num_issues, pr_number, pr_title):
    """Generate summary comment for PR."""
    status = "⚠️ Issues Found" if num_issues > 0 else "✅ No Issues"
    return f"""## 🤖 AI Code Reviewer

{status} for PR #{pr_number}

**Files analyzed:** {num_files}
**Issues found:** {num_issues}

📄 Documentation: `docs/auto/DOCUMENTATION.md`
🔍 Review report: `docs/reviews/PR-{pr_number}.md`

---
*Automated review. Please verify manually.*"""


if __name__ == "__main__":
    main()