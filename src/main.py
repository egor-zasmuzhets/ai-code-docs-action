import os
import sys
from dotenv import load_dotenv

# Загружаем .env только при локальном запуске
if not os.getenv("GITHUB_ACTIONS"):
    load_dotenv()
    print("📁 LOCAL MODE: using .env file")
else:
    print("🚀 GITHUB ACTIONS MODE")

from github_client import GitHubClient


def main():
    print("=" * 50)
    print("AI Code Docs & Reviewer Action")
    print("=" * 50)
    
    token = os.getenv("GITHUB_TOKEN")
    repo = os.getenv("GITHUB_REPOSITORY")
    pr_number_str = os.getenv("GITHUB_PR_NUMBER")
    
    print(f"Token exists: {bool(token)}")
    print(f"Repository: {repo}")
    print(f"PR Number: {pr_number_str}")
    
    if not token:
        print("❌ GITHUB_TOKEN not found")
        print("   Create .env file with GITHUB_TOKEN=...")
        sys.exit(1)
    
    if not repo:
        print("❌ GITHUB_REPOSITORY not found")
        sys.exit(1)
    
    if not pr_number_str:
        print("❌ GITHUB_PR_NUMBER not found")
        sys.exit(1)
    
    pr_number = int(pr_number_str)
    
    # Создаём клиент
    client = GitHubClient(token, repo, pr_number)
    
    # Получаем информацию о PR
    info = client.get_pr_info()
    print(f"\n📋 PR: {info['title']}")
    print(f"👤 Author: {info['author']}")
    print(f"🌿 Branch: {info['branch']}")
    
    # Получаем изменённые файлы
    files = client.get_changed_files()
    python_files = [f for f in files if f['filename'].endswith('.py')]
    
    print(f"\n📁 Changed files: {len(files)}")
    print(f"🐍 Python files: {len(python_files)}")
    
    for f in python_files:
        print(f"   - {f['filename']} (+{f['additions']} -{f['deletions']})")
    
    # Комментарий в PR (только в реальном режиме, не при локальном тесте)
    if os.getenv("GITHUB_ACTIONS"):
        comment = f"""🤖 **AI Code Reviewer (Test)**

This is a dry run. Found **{len(python_files)}** Python files changed.

When fully operational, this bot will generate documentation and code reviews.
"""
        client.create_pr_comment(comment)
        print("💬 Test comment posted to PR")
    else:
        print("\n💡 LOCAL MODE: Skipping PR comment (would post in real GitHub)")
    
    print("\n✅ Done!")


if __name__ == "__main__":
    main()