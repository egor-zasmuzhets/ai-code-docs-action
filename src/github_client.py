import os
import base64
from github import Github, GithubException

class GitHubClient:
    def __init__(self, token: str, repo_full_name: str, pr_number: int):
        self.token = token
        self.repo_full_name = repo_full_name
        self.pr_number = pr_number
        
        self.github = Github(token)
        self.repo = self.github.get_repo(repo_full_name)
        self.pr = self.repo.get_pull(pr_number)
    
    def get_changed_files(self):
        """Get list of changed files in the PR"""
        files = []
        for file in self.pr.get_files():
            files.append({
                "filename": file.filename,
                "status": file.status,
                "additions": file.additions,
                "deletions": file.deletions,
                "patch": file.patch
            })
        return files

    def get_pr_info(self):
        """Get basic information about the PR."""
        return {
            "title": self.pr.title,
            "description": self.pr.body or "",
            "author": self.pr.user.login,
            "branch": self.pr.head.ref,  # ветка, из которой делают PR
            "base_branch": self.pr.base.ref,  # ветка, в которую хотят влить
            "url": self.pr.html_url,
            "number": self.pr.number
        }
    
    def create_pr_comment(self, body: str):
        """Post a comment to the PR"""
        try:
            self.pr.create_issue_comment(body)
            return True
        except GithubException as e:
            print(f"Failed to create comment: {e}")
            return False