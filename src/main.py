"""
Main entry point for the GitHub Action.
Fetches PR files, analyzes them with LLM, and generates documentation.
"""

import os
import sys
import json
from datetime import datetime
from dotenv import load_dotenv

if not os.getenv("GITHUB_ACTIONS"):
    load_dotenv()
    print("📁 LOCAL MODE: using .env file")
else:
    print("🚀 GITHUB ACTIONS MODE")

from github_client import GitHubClient
from llm_factory import get_llm_client
from analyzer import detect_language, get_analysis_strategy, extract_signatures, is_supported
from utils import parse_exclude_patterns, is_excluded, is_self_generated


def main():
    print("=" * 55)
    print("🤖 AI Code Docs & Reviewer - Running")
    print("=" * 55)

    # Get environment variables
    token = os.getenv("GITHUB_TOKEN")
    repo = os.getenv("GITHUB_REPOSITORY")
    pr_number_str = os.getenv("GITHUB_PR_NUMBER")
    groq_api_key = os.getenv("GROQ_API_KEY")
    github_token = os.getenv("GITHUB_TOKEN")
    provider = os.getenv("LLM_PROVIDER", "auto")
    model = os.getenv("LLM_MODEL", "")
    review_prompt = os.getenv("REVIEW_PROMPT")
    doc_prompt = os.getenv("DOC_PROMPT")
    exclude_str = os.getenv("EXCLUDE_PATTERNS", "")
    doc_output_path = os.getenv("DOC_OUTPUT_PATH", "docs/auto/DOCUMENTATION.md")
    review_output_path = os.getenv("REVIEW_OUTPUT_PATH", "docs/reviews/")

    exclude_patterns = parse_exclude_patterns(exclude_str)

    print(f"\n📋 Configuration:")
    print(f"   Repository: {repo}")
    print(f"   PR Number: {pr_number_str}")
    print(f"   LLM Provider: {provider}")
    print(f"   GITHUB_TOKEN exists: {bool(token)}")
    print(f"   GROQ_API_KEY exists: {bool(groq_api_key)}")
    print(f"   Exclude patterns: {exclude_patterns if exclude_patterns else 'None'}")

    # Validate required variables
    missing_vars = []
    if not token:
        missing_vars.append("GITHUB_TOKEN")
    if not repo:
        missing_vars.append("GITHUB_REPOSITORY")
    if not pr_number_str:
        missing_vars.append("GITHUB_PR_NUMBER")

    if missing_vars:
        print(f"\n❌ Missing required environment variables: {', '.join(missing_vars)}")
        sys.exit(1)

    pr_number = int(pr_number_str)

    # Initialize GitHub client
    try:
        github = GitHubClient(token, repo, pr_number)
    except Exception as e:
        print(f"\n❌ Failed to initialize GitHub client: {e}")
        sys.exit(1)

    # Initialize LLM client
    try:
        llm = get_llm_client(
            provider=provider,
            groq_api_key=groq_api_key,
            github_token=github_token,
            model=model,
            review_prompt=review_prompt,
            doc_prompt=doc_prompt
        )
    except ValueError as e:
        print(f"\n❌ {e}")
        sys.exit(1)

    # Get PR info
    try:
        pr_info = github.get_pr_info()
        print(f"\n📋 Pull Request:")
        print(f"   Title: {pr_info.get('title', 'N/A')}")
        print(f"   Author: {pr_info.get('author', 'N/A')}")
        print(f"   Branch: {pr_info.get('branch', 'N/A')} → {pr_info.get('base_branch', 'N/A')}")
    except Exception as e:
        print(f"\n❌ Failed to get PR info: {e}")
        sys.exit(1)

    # Get changed files
    try:
        all_files = github.get_changed_files()

        relevant_files = []
        excluded_count = 0
        unknown_lang_count = 0
        self_generated_count = 0

        for f in all_files:
            if is_self_generated(f['filename']):
                self_generated_count += 1
                continue

            language = detect_language(f['filename'])
            if not language:
                unknown_lang_count += 1
                continue

            if is_excluded(f['filename'], exclude_patterns):
                excluded_count += 1
                continue

            relevant_files.append({
                **f,
                'language': language
            })

        print(f"\n📁 Changed files: {len(all_files)} total")
        print(f"🔍 Files to analyze: {len(relevant_files)}")
        if self_generated_count:
            print(f"   🔄 Self-generated (skipped): {self_generated_count}")
        if unknown_lang_count:
            print(f"   ⚠️ Unknown language: {unknown_lang_count}")
        if excluded_count:
            print(f"   🚫 Excluded by pattern: {excluded_count}")

        if not relevant_files:
            print("\n⚠️ No relevant files to analyze")
            if os.getenv("GITHUB_ACTIONS"):
                github.create_pr_comment(f"🤖 **AI Code Reviewer**\n\nNo relevant files were changed in this PR.\n\n📁 Changed files: {len(all_files)} total\n🔍 Supported files: 0\n\nSkipping analysis.")
            sys.exit(0)

    except Exception as e:
        print(f"\n❌ Failed to get changed files: {e}")
        sys.exit(1)

    # Analyze each file
    all_documentation = []
    all_issues = []
    analysis_errors = 0

    print("\n🔍 Starting code analysis...")
    print("-" * 55)

    for idx, file_info in enumerate(relevant_files, 1):
        filename = file_info['filename']
        language = file_info['language']

        print(f"\n[{idx}/{len(relevant_files)}] Analyzing: {filename} ({language})")

        content = file_info.get('content')
        if not content:
            content = github._get_file_content(filename)

        if not content:
            print(f"   ⚠️ Could not read file content, skipping")
            analysis_errors += 1
            continue

        file_size = len(content)
        changes_ratio = (file_info['additions'] + file_info['deletions']) / max(file_size / 10, 1)
        strategy = get_analysis_strategy(language, file_size, changes_ratio)

        print(f"   📏 Size: {file_size} chars, {len(content.splitlines())} lines")
        print(f"   📊 Strategy: {strategy}")

        if strategy == 'signature':
            code_to_analyze = extract_signatures(content, language)
            print(f"   📋 Signatures extracted: {len(code_to_analyze)} chars")
        else:
            code_to_analyze = content

        try:
            result = llm.analyze_code(code_to_analyze, language=language)
        except Exception as e:
            print(f"   ❌ LLM analysis failed: {e}")
            analysis_errors += 1
            continue

        doc = result.get("documentation", {})
        all_documentation.append({
            "file": filename,
            "language": language,
            "doc": doc
        })

        review = result.get("review", {})
        issues = review.get("issues", [])
        for issue in issues:
            issue["file"] = filename
            issue["language"] = language
            all_issues.append(issue)

            if os.getenv("GITHUB_ACTIONS") and issue.get('line') and issue.get('line') > 0:
                severity_icon = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}.get(issue.get('severity'), '⚪')
                comment_body = f"""**{severity_icon} {issue.get('severity', 'issue').upper()}** - {issue.get('type', 'issue')}

**Issue:** {issue.get('description', 'No description')}

**Suggestion:** {issue.get('suggestion', 'No suggestion provided')}"""
                github.post_inline_comment(filename, issue.get('line'), comment_body)
                print(f"      💬 Inline comment at line {issue.get('line')}")

        print(f"   ✅ Found {len(issues)} issues")

    print("-" * 55)
    print(f"\n📊 Analysis complete: {len(all_documentation)} files, {len(all_issues)} issues, {analysis_errors} errors")

    # Generate documentation
    if all_documentation:
        doc_content = _generate_documentation(all_documentation, pr_info)
        if os.getenv("GITHUB_ACTIONS"):
            github.commit_documentation(doc_output_path, doc_content, f"docs: auto-update for PR #{pr_number}")
            print(f"\n📄 Documentation: {doc_output_path}")

    # Generate review report
    if all_issues:
        review_content = _generate_review_report(all_issues, pr_info)
        review_path = os.path.join(review_output_path, f"PR-{pr_number}.md")
        if os.getenv("GITHUB_ACTIONS"):
            github.commit_documentation(review_path, review_content, f"review: report for PR #{pr_number}")
            print(f"🔍 Review report: {review_path}")

    # Post summary comment
    if os.getenv("GITHUB_ACTIONS"):
        comment = _generate_pr_comment(len(all_documentation), len(all_issues), pr_number, pr_info['title'])
        github.post_review_summary(comment)
        print("\n💬 Summary comment posted")

    print("\n✅ Done!")


def _generate_documentation(docs_list, pr_info):
    content = f"""# Auto-Generated Documentation

> **PR:** #{pr_info['number']} - {pr_info['title']}
> **Author:** @{pr_info['author']}
> **Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}

"""
    for item in docs_list:
        doc = item['doc']
        content += f"\n## 📄 `{item['file']}`\n\n"
        content += f"**Description:** {doc.get('description', 'No description')}\n\n"
        content += f"**Functions:** {', '.join(doc.get('functions', [])) or 'None'}\n\n"
        content += f"**Classes:** {', '.join(doc.get('classes', [])) or 'None'}\n\n"
        content += f"**Dependencies:** {', '.join(doc.get('dependencies', [])) or 'None'}\n\n---\n"
    return content


def _generate_review_report(issues, pr_info):
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

## Details

"""
    for issue in issues:
        severity_icon = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}.get(issue.get('severity'), '⚪')
        content += f"\n### {severity_icon} {issue.get('type', 'issue').upper()}\n"
        content += f"- **File:** `{issue.get('file')}`\n"
        content += f"- **Description:** {issue.get('description')}\n"
        content += f"- **Suggestion:** {issue.get('suggestion')}\n"
    return content


def _generate_pr_comment(num_files, num_issues, pr_number, pr_title):
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