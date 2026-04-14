"""
Main entry point for the GitHub Action.
Fetches PR files, analyzes them with LLM, and generates documentation.
"""

import os
import sys
import json
from datetime import datetime
from dotenv import load_dotenv

# Load .env for local testing (only if not in GitHub Actions)
if not os.getenv("GITHUB_ACTIONS"):
    load_dotenv()
    print("📁 LOCAL MODE: using .env file")
else:
    print("🚀 GITHUB ACTIONS MODE")

from github_client import GitHubClient
from llm_client import GroqClient
from analyzer import detect_language, get_analysis_strategy, extract_signatures, is_supported


def main():
    print("=" * 55)
    print("🤖 AI Code Docs & Reviewer - Running")
    print("=" * 55)

    # =========================================================
    # 1. GET ENVIRONMENT VARIABLES
    # =========================================================
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

    from utils import parse_exclude_patterns, is_excluded

    # Parse exclude patterns
    exclude_patterns = parse_exclude_patterns(exclude_str)

    # Debug info (safe, no secrets printed)
    print(f"\n📋 Configuration:")
    print(f"   Repository: {repo}")
    print(f"   PR Number: {pr_number_str}")
    print(f"   Groq Model: {groq_model}")
    print(f"   GITHUB_TOKEN exists: {bool(token)}")
    print(f"   GROQ_API_KEY exists: {bool(groq_api_key)}")
    print(f"   Custom review prompt: {'Yes' if review_prompt else 'No'}")
    print(f"   Custom doc prompt: {'Yes' if doc_prompt else 'No'}")
    print(f"   Exclude patterns: {exclude_patterns if exclude_patterns else 'None'}")

    # =========================================================
    # 2. VALIDATE REQUIRED VARIABLES
    # =========================================================
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
        print(f"\n❌ Missing required environment variables: {', '.join(missing_vars)}")
        if not os.getenv("GITHUB_ACTIONS"):
            print("\n💡 For local testing, create .env file with:")
            print("   GITHUB_TOKEN=your_token")
            print("   GITHUB_REPOSITORY=owner/repo")
            print("   GITHUB_PR_NUMBER=123")
            print("   GROQ_API_KEY=gsk_...")
        sys.exit(1)

    pr_number = int(pr_number_str)

    # =========================================================
    # 3. INITIALIZE CLIENTS
    # =========================================================
    try:
        github = GitHubClient(token, repo, pr_number)
        llm = GroqClient(groq_api_key, model=groq_model,
                         review_prompt=review_prompt,
                         doc_prompt=doc_prompt)
    except Exception as e:
        print(f"\n❌ Failed to initialize clients: {e}")
        sys.exit(1)

    # =========================================================
    # 4. GET PR INFORMATION
    # =========================================================
    try:
        pr_info = github.get_pr_info()
        print(f"\n📋 Pull Request:")
        print(f"   Title: {pr_info.get('title', 'N/A')}")
        print(f"   Author: {pr_info.get('author', 'N/A')}")
        print(f"   Branch: {pr_info.get('branch', 'N/A')} → {pr_info.get('base_branch', 'N/A')}")
        print(f"   URL: {pr_info.get('url', 'N/A')}")
    except Exception as e:
        print(f"\n❌ Failed to get PR info: {e}")
        pr_info = {
            "title": "Unknown PR",
            "description": "",
            "author": "unknown",
            "branch": "unknown",
            "base_branch": "main",
            "url": "",
            "number": pr_number
        }
        print("   ⚠️ Using fallback PR info")

    # =========================================================
    # 5. GET CHANGED FILES
    # =========================================================
    try:
        all_files = github.get_changed_files()

        # Filter by language AND exclude patterns

        from utils import is_excluded, parse_exclude_patterns, is_self_generated

        # Filter files
        relevant_files = []
        excluded_count = 0
        unknown_lang_count = 0
        self_generated_count = 0  # ← новая переменная

        for f in all_files:
            # ← НОВАЯ ПРОВЕРКА: пропускаем файлы, созданные самим Action
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
                comment = f"""🤖 **AI Code Reviewer**

No relevant files were changed in this PR.

📁 Changed files: {len(all_files)} total
🔍 Supported files: 0

Skipping analysis."""
                github.create_pr_comment(comment)
            print("\n✅ Done (no files to analyze)")
            sys.exit(0)

    except Exception as e:
        print(f"\n❌ Failed to get changed files: {e}")
        sys.exit(1)

    # =========================================================
    # 6. ANALYZE EACH FILE WITH LLM
    # =========================================================
    all_documentation = []
    all_issues = []
    analysis_errors = 0

    print("\n🔍 Starting code analysis...")
    print("-" * 55)

    for idx, file_info in enumerate(relevant_files, 1):
        filename = file_info['filename']
        language = file_info['language']

        print(f"\n[{idx}/{len(relevant_files)}] Analyzing: {filename} ({language})")

        # Get file content
        content = file_info.get('content')
        if not content:
            content = github._get_file_content(filename)

        if not content:
            print(f"   ⚠️ Could not read file content, skipping")
            analysis_errors += 1
            continue

        # Determine analysis strategy
        file_size = len(content)
        changes_ratio = (file_info['additions'] + file_info['deletions']) / max(file_size / 10, 1)
        strategy = get_analysis_strategy(language, file_size, changes_ratio)

        print(f"   📏 Size: {file_size} characters, {len(content.splitlines())} lines")
        print(f"   📊 Strategy: {strategy}")
        print(f"   📝 Changes: +{file_info['additions']} -{file_info['deletions']}")

        # Prepare code for analysis based on strategy
        if strategy == 'signature':
            code_to_analyze = extract_signatures(content, language)
            print(f"   📋 Signatures extracted: {len(code_to_analyze)} chars")
        else:
            code_to_analyze = content

        # Analyze with LLM
        try:
            result = llm.analyze_code(code_to_analyze, language=language)
        except Exception as e:
            print(f"   ❌ LLM analysis failed: {e}")
            analysis_errors += 1
            continue

        # Collect documentation
        doc = result.get("documentation", {})
        all_documentation.append({
            "file": filename,
            "language": language,
            "doc": doc
        })

        # Collect issues
        review = result.get("review", {})
        issues = review.get("issues", [])
        for issue in issues:
            issue["file"] = filename
            issue["language"] = language
            all_issues.append(issue)

            # Post inline comment if line number is available and in GitHub Actions
            if os.getenv("GITHUB_ACTIONS") and issue.get('line') and issue.get('line') > 0:
                severity_icon = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}.get(issue.get('severity'), '⚪')
                comment_body = f"""**{severity_icon} {issue.get('severity', 'issue').upper()}** - {issue.get('type', 'issue')}

**Issue:** {issue.get('description', 'No description')}

**Suggestion:** {issue.get('suggestion', 'No suggestion provided')}
"""
                github.post_inline_comment(filename, issue.get('line'), comment_body)
                print(f"      💬 Inline comment posted at line {issue.get('line')}")

        print(f"   ✅ Found {len(issues)} issues")
        if issues:
            for issue in issues[:3]:
                severity_icon = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}.get(issue.get('severity'), '⚪')
                desc = issue.get('description', '')[:60]
                print(f"      {severity_icon} {issue.get('type', 'issue')}: {desc}")
            if len(issues) > 3:
                print(f"      ... and {len(issues) - 3} more")

    print("-" * 55)
    print(f"\n📊 Analysis complete:")
    print(f"   Files analyzed: {len(all_documentation)}")
    print(f"   Total issues found: {len(all_issues)}")
    print(f"   Errors: {analysis_errors}")

    # =========================================================
    # 7. GENERATE DOCUMENTATION FILE
    # =========================================================
    if all_documentation:
        doc_content = generate_documentation(all_documentation, pr_info)

        if os.getenv("GITHUB_ACTIONS"):
            try:
                github.commit_documentation(
                    doc_output_path,
                    doc_content,
                    f"docs: auto-update documentation for PR #{pr_number}"
                )
                print(f"\n📄 Documentation updated: {doc_output_path}")
            except Exception as e:
                print(f"\n⚠️ Failed to commit documentation: {e}")
        else:
            print(f"\n📄 Documentation preview (not committed in local mode):")
            print(f"   Path: {doc_output_path}")
            print("\n   Preview:")
            print("   " + doc_content[:500].replace("\n", "\n   ") + "...")

    # =========================================================
    # 8. GENERATE REVIEW REPORT
    # =========================================================
    if all_issues:
        review_content = generate_review_report(all_issues, pr_info)
        review_path = os.path.join(review_output_path, f"PR-{pr_number}.md")

        if os.getenv("GITHUB_ACTIONS"):
            try:
                github.commit_documentation(
                    review_path,
                    review_content,
                    f"review: add code review report for PR #{pr_number}"
                )
                print(f"🔍 Review report created: {review_path}")
            except Exception as e:
                print(f"\n⚠️ Failed to commit review report: {e}")
        else:
            print(f"\n🔍 Review report preview (not committed in local mode):")
            print(f"   Path: {review_path}")
            print("\n   Preview:")
            print("   " + review_content[:500].replace("\n", "\n   ") + "...")
    else:
        print("\n🔍 No issues found — skipping review report")

    # =========================================================
    # 9. POST PR SUMMARY COMMENT (only in GitHub Actions)
    # =========================================================
    if os.getenv("GITHUB_ACTIONS"):
        try:
            comment = generate_pr_comment(
                num_files=len(all_documentation),
                num_issues=len(all_issues),
                pr_number=pr_number,
                pr_title=pr_info['title']
            )
            github.post_review_summary(comment)
            print("\n💬 Summary comment posted to PR")
        except Exception as e:
            print(f"\n⚠️ Failed to post PR comment: {e}")
    else:
        print("\n💡 LOCAL MODE: Skipping PR comment (would post in GitHub Actions)")

    # =========================================================
    # 10. FINAL SUMMARY
    # =========================================================
    print("\n" + "=" * 55)
    print("✅ AI Code Docs & Reviewer completed successfully!")
    print(f"   📄 Documentation: {'updated' if all_documentation else 'none'}")
    print(f"   🔍 Issues found: {len(all_issues)}")
    print(f"   📁 Files analyzed: {len(all_documentation)}")
    print("=" * 55)


def generate_documentation(docs_list, pr_info):
    """Generate markdown documentation from LLM results"""
    content = f"""# Auto-Generated Documentation

> **This documentation was automatically generated by AI**
> 
> - **PR:** #{pr_info['number']} - {pr_info['title']}
> - **Author:** @{pr_info['author']}
> - **Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}
> - **Branch:** `{pr_info['branch']}` → `{pr_info['base_branch']}`

---

"""
    for item in docs_list:
        doc = item['doc']
        lang_icon = get_language_icon(item.get('language', 'python'))

        content += f"""
## {lang_icon} `{item['file']}`

### Description
{doc.get('description', 'No description provided')}

### Functions
"""
        functions = doc.get('functions', [])
        if functions:
            for func in functions:
                content += f"- `{func}`\n"
        else:
            content += "- None\n"

        content += f"""
### Classes
"""
        classes = doc.get('classes', [])
        if classes:
            for cls in classes:
                content += f"- `{cls}`\n"
        else:
            content += "- None\n"

        content += f"""
### Dependencies
"""
        deps = doc.get('dependencies', [])
        if deps:
            for dep in deps:
                content += f"- `{dep}`\n"
        else:
            content += "- None\n"

        content += "\n---\n"

    return content


def generate_review_report(issues, pr_info):
    """Generate markdown review report"""
    high = [i for i in issues if i.get('severity') == 'high']
    medium = [i for i in issues if i.get('severity') == 'medium']
    low = [i for i in issues if i.get('severity') == 'low']

    files_with_issues = sorted(set(i.get('file', 'unknown') for i in issues))

    content = f"""# Code Review Report - PR #{pr_info['number']}

> **Automated code review generated by AI**
>
> - **PR:** {pr_info['title']}
> - **Author:** @{pr_info['author']}
> - **Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}

---

## 📊 Summary

| Metric | Value |
|--------|-------|
| **Total issues** | {len(issues)} |
| 🔴 **High severity** | {len(high)} |
| 🟡 **Medium severity** | {len(medium)} |
| 🟢 **Low severity** | {len(low)} |
| **Files with issues** | {len(files_with_issues)} |

---

## 📁 Files Affected

"""
    for file in files_with_issues:
        file_issues = [i for i in issues if i.get('file') == file]
        lang_icon = get_language_icon(file_issues[0].get('language', 'python')) if file_issues else '📄'
        content += f"- {lang_icon} `{file}` ({len(file_issues)} issue(s))\n"

    content += "\n---\n\n## 🔍 Detailed Issues\n\n"

    for severity in ['high', 'medium', 'low']:
        severity_issues = [i for i in issues if i.get('severity') == severity]
        if not severity_issues:
            continue

        severity_icon = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}[severity]
        severity_name = {'high': 'High', 'medium': 'Medium', 'low': 'Low'}[severity]
        content += f"\n### {severity_icon} {severity_name} Severity Issues\n\n"

        for issue in severity_issues:
            line_info = f" (line {issue.get('line')})" if issue.get('line') else ""
            content += f"""<details>
<summary><b>{issue.get('type', 'issue').upper()}</b>: {issue.get('description', 'No description')[:80]}...{line_info}</summary>

| Property | Value |
|----------|-------|
| **File** | `{issue.get('file', 'unknown')}` |
| **Severity** | {issue.get('severity', 'unknown')} |
| **Type** | {issue.get('type', 'unknown')} |
| **Language** | {issue.get('language', 'unknown')} |

**Description:** {issue.get('description', 'No description')}

**Suggestion:** {issue.get('suggestion', 'No suggestion provided')}

</details>

"""

    content += """
---

*This review was automatically generated by AI. Please verify suggestions manually before merging.*
"""
    return content


def generate_pr_comment(num_files, num_issues, pr_number, pr_title):
    """Generate comment to post in PR"""
    if num_issues > 0:
        status_icon = "⚠️"
        status_text = "Issues Found"
    else:
        status_icon = "✅"
        status_text = "No Issues Found"

    return f"""## 🤖 AI Code Reviewer

{status_icon} **{status_text}** for PR #{pr_number}

---

### 📊 Summary

| Metric | Result |
|--------|--------|
| **Files analyzed** | {num_files} |
| **Issues found** | {num_issues} |

---

### 📄 Generated Artifacts

- 📚 **Documentation:** `docs/auto/DOCUMENTATION.md`
- 🔍 **Detailed review:** `docs/reviews/PR-{pr_number}.md`

---

### 💡 Next Steps

1. Review the documentation and code review reports
2. Address any high-severity issues
3. Merge when ready

---
*This review was automatically generated. Please verify suggestions manually.*
"""


def get_language_icon(language: str) -> str:
    """Return an icon for a programming language"""
    icons = {
        'python': '🐍',
        'javascript': '🟨',
        'typescript': '💙',
        'go': '🐹',
        'java': '☕',
        'rust': '🦀',
        'c': '⚙️',
        'cpp': '⚙️',
        'ruby': '💎',
        'php': '🐘',
        'html': '🌐',
        'css': '🎨',
        'sql': '🗄️',
        'bash': '📟',
        'json': '📦',
        'yaml': '📋',
        'markdown': '📝',
    }
    return icons.get(language, '📄')


if __name__ == "__main__":
    main()