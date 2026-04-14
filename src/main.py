"""
Main entry point for the GitHub Action.
Fetches PR files, analyzes them with LLM, and generates documentation.
"""

import os
import sys
import json
from dotenv import load_dotenv

# Load .env for local testing (only if not in GitHub Actions)
if not os.getenv("GITHUB_ACTIONS"):
    load_dotenv()
    print("📁 LOCAL MODE: using .env file")
else:
    print("🚀 GITHUB ACTIONS MODE")

from github_client import GitHubClient
from llm_client import GroqClient


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

    # Debug info (safe, no secrets printed)
    print(f"\n📋 Configuration:")
    print(f"   Repository: {repo}")
    print(f"   PR Number: {pr_number_str}")
    print(f"   Groq Model: {groq_model}")
    print(f"   GITHUB_TOKEN exists: {bool(token)}")
    print(f"   GROQ_API_KEY exists: {bool(groq_api_key)}")

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
        llm = GroqClient(groq_api_key, model=groq_model)
    except Exception as e:
        print(f"\n❌ Failed to initialize clients: {e}")
        sys.exit(1)

    # =========================================================
    # 4. GET PR INFORMATION
    # =========================================================
    try:
        pr_info = github.get_pr_info()
        print(f"\n📋 Pull Request:")
        print(f"   Title: {pr_info['title']}")
        print(f"   Author: {pr_info['author']}")
        print(f"   Branch: {pr_info['branch']} → {pr_info['base_branch']}")
        print(f"   URL: {pr_info['url']}")
    except Exception as e:
        print(f"\n❌ Failed to get PR info: {e}")
        sys.exit(1)

    # =========================================================
    # 5. GET CHANGED FILES
    # =========================================================
    try:
        all_files = github.get_changed_files()
        python_files = [f for f in all_files if f['filename'].endswith('.py')]

        print(f"\n📁 Changed files: {len(all_files)} total")
        print(f"🐍 Python files to analyze: {len(python_files)}")

        if python_files:
            for f in python_files:
                print(f"   - {f['filename']} (+{f['additions']} -{f['deletions']})")

        if not python_files:
            print("\n⚠️ No Python files changed, skipping analysis")
            # Still post a comment saying nothing to analyze
            if os.getenv("GITHUB_ACTIONS"):
                comment = f"""🤖 **AI Code Reviewer**

No Python files were changed in this PR.

📁 Changed files: {len(all_files)} total
🐍 Python files: 0

Skipping analysis."""
                github.create_pr_comment(comment)
            print("\n✅ Done (no Python files to analyze)")
            sys.exit(0)
    except Exception as e:
        print(f"\n❌ Failed to get changed files: {e}")
        sys.exit(1)

    # =========================================================
    # 6. ANALYZE EACH PYTHON FILE WITH LLM
    # =========================================================
    all_documentation = []
    all_issues = []
    analysis_errors = 0

    print("\n🔍 Starting code analysis...")
    print("-" * 55)

    for idx, py_file in enumerate(python_files, 1):
        print(f"\n[{idx}/{len(python_files)}] Analyzing: {py_file['filename']}")

        # Get file content
        content = github._get_file_content(py_file['filename'])
        if not content:
            print(f"   ⚠️ Could not read file content, skipping")
            analysis_errors += 1
            continue

        print(f"   📏 Size: {len(content)} characters, {len(content.splitlines())} lines")

        # Analyze with LLM
        try:
            result = llm.analyze_code(content)
        except Exception as e:
            print(f"   ❌ LLM analysis failed: {e}")
            analysis_errors += 1
            continue

        # Collect documentation
        doc = result.get("documentation", {})
        all_documentation.append({
            "file": py_file['filename'],
            "doc": doc
        })

        # Collect issues
        review = result.get("review", {})
        issues = review.get("issues", [])
        for issue in issues:
            issue["file"] = py_file['filename']
            all_issues.append(issue)

        print(f"   ✅ Found {len(issues)} issues")
        if issues:
            for issue in issues[:3]:  # Show first 3 issues
                severity_icon = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}.get(issue.get('severity'), '⚪')
                print(f"      {severity_icon} {issue.get('type', 'issue')}: {issue.get('description', '')[:60]}")
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
        doc_path = "docs/auto/DOCUMENTATION.md"

        if os.getenv("GITHUB_ACTIONS"):
            try:
                github.commit_documentation(
                    doc_path,
                    doc_content,
                    f"docs: auto-update documentation for PR #{pr_number}"
                )
                print(f"\n📄 Documentation updated: {doc_path}")
            except Exception as e:
                print(f"\n⚠️ Failed to commit documentation: {e}")
        else:
            print(f"\n📄 Documentation preview (not committed in local mode):")
            print(f"   Path: {doc_path}")
            # Print first 500 chars as preview
            print("\n   Preview:")
            print("   " + doc_content[:500].replace("\n", "\n   ") + "...")

    # =========================================================
    # 8. GENERATE REVIEW REPORT
    # =========================================================
    if all_issues:
        review_content = generate_review_report(all_issues, pr_info)
        review_path = f"docs/reviews/PR-{pr_number}.md"

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
    # 9. POST PR COMMENT (only in GitHub Actions)
    # =========================================================
    if os.getenv("GITHUB_ACTIONS"):
        try:
            comment = generate_pr_comment(
                num_files=len(all_documentation),
                num_issues=len(all_issues),
                pr_number=pr_number,
                pr_title=pr_info['title']
            )
            github.create_pr_comment(comment)
            print("\n💬 Comment posted to PR")
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
    from datetime import datetime

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
        content += f"""
## 📄 `{item['file']}`

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
    from datetime import datetime

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
        content += f"- `{file}` ({len(file_issues)} issue(s))\n"

    content += "\n---\n\n## 🔍 Detailed Issues\n\n"

    for severity in ['high', 'medium', 'low']:
        severity_issues = [i for i in issues if i.get('severity') == severity]
        if not severity_issues:
            continue

        severity_icon = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}[severity]
        severity_name = {'high': 'High', 'medium': 'Medium', 'low': 'Low'}[severity]
        content += f"\n### {severity_icon} {severity_name} Severity Issues\n\n"

        for issue in severity_issues:
            content += f"""<details>
<summary><b>{issue.get('type', 'issue').upper()}</b>: {issue.get('description', 'No description')[:80]}...</summary>

| Property | Value |
|----------|-------|
| **File** | `{issue.get('file', 'unknown')}` |
| **Severity** | {issue.get('severity', 'unknown')} |
| **Type** | {issue.get('type', 'unknown')} |

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
    severity_icons = ""
    if num_issues > 0:
        severity_icons = "⚠️"
    else:
        severity_icons = "✅"

    return f"""## 🤖 AI Code Reviewer

{severity_icons} Automated analysis complete for **PR #{pr_number}**

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


if __name__ == "__main__":
    main()