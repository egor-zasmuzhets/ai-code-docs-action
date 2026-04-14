"""
GitHub API client for the AI Code Reviewer Action.
Handles:
- Getting changed files from a PR
- Reading file contents
- Committing documentation back to the PR branch
- Posting inline comments
"""

import os
import base64
from typing import List, Dict, Any, Optional
from github import Github, GithubException


class GitHubClient:
    """Wrapper around PyGithub with convenience methods for the Action."""

    def __init__(self, token: str, repo_full_name: str, pr_number: int):
        """
        Initialize GitHub client.

        Args:
            token: GitHub token (usually ${{ github.token }})
            repo_full_name: Format "owner/repo"
            pr_number: Pull request number
        """
        self.token = token
        self.repo_full_name = repo_full_name
        self.pr_number = pr_number

        self.github = Github(token)
        self.repo = self.github.get_repo(repo_full_name)
        self.pr = self.repo.get_pull(pr_number)

    def get_changed_files(self) -> List[Dict[str, Any]]:
        """
        Get list of changed files in the PR with their contents.

        Returns:
            List of dicts with keys:
            - filename: str
            - status: "added" | "modified" | "removed"
            - additions: int
            - deletions: int
            - content: str (full file content, None for removed files)
            - patch: str (diff snippet, if available)
        """
        changed_files = []

        for file in self.pr.get_files():
            file_info = {
                "filename": file.filename,
                "status": file.status,
                "additions": file.additions,
                "deletions": file.deletions,
                "patch": file.patch,
                "content": None
            }

            if file.status != "removed":
                file_info["content"] = self._get_file_content(file.filename)

            changed_files.append(file_info)

        return changed_files

    def _get_file_content(self, filepath: str) -> Optional[str]:
        """
        Get the full content of a file from the PR's branch.

        Args:
            filepath: Path to the file in the repository

        Returns:
            File content as string, or None if file not found
        """
        try:
            contents = self.repo.get_contents(filepath, ref=self.pr.head.sha)
            decoded = base64.b64decode(contents.content).decode("utf-8")
            return decoded
        except GithubException as e:
            if e.status == 404:
                return None
            raise

    def get_pr_info(self) -> Dict[str, Any]:
        """
        Get basic information about the PR.

        Returns:
            Dict with keys: title, description, author, branch, base_branch, url, number
        """
        return {
            "title": self.pr.title,
            "description": self.pr.body or "",
            "author": self.pr.user.login,
            "branch": self.pr.head.ref,
            "base_branch": self.pr.base.ref,
            "url": self.pr.html_url,
            "number": self.pr.number
        }

    def get_file_diff_stats(self, filename: str) -> Dict[str, int]:
        """
        Get diff statistics for a specific file.

        Args:
            filename: The file path

        Returns:
            Dict with 'added' and 'removed' line counts
        """
        for file in self.pr.get_files():
            if file.filename == filename:
                return {"added": file.additions, "removed": file.deletions}
        return {"added": 0, "removed": 0}

    def commit_documentation(self, filepath: str, content: str, commit_message: str) -> bool:
        """
        Commit a documentation file to the PR branch.

        Args:
            filepath: Path where to create/update the file
            content: New content of the file
            commit_message: Git commit message

        Returns:
            True if successful, False otherwise
        """
        try:
            try:
                existing_file = self.repo.get_contents(filepath, ref=self.pr.head.ref)
                self.repo.update_file(
                    path=filepath,
                    message=commit_message,
                    content=content,
                    sha=existing_file.sha,
                    branch=self.pr.head.ref
                )
            except GithubException as e:
                if e.status == 404:
                    self.repo.create_file(
                        path=filepath,
                        message=commit_message,
                        content=content,
                        branch=self.pr.head.ref
                    )
                else:
                    raise
            return True
        except GithubException as e:
            print(f"Failed to commit documentation: {e}")
            return False

    def create_pr_comment(self, body: str) -> bool:
        """
        Create a comment in the PR.

        Args:
            body: Comment text (markdown supported)

        Returns:
            True if successful, False otherwise
        """
        try:
            self.pr.create_issue_comment(body)
            return True
        except GithubException as e:
            print(f"Failed to create PR comment: {e}")
            return False

    def post_inline_comment(self, file_path: str, line_number: int, comment_body: str) -> bool:
        """
        Post a comment on a specific line in the PR.

        Args:
            file_path: Path to the file (e.g., "src/main.py")
            line_number: Line number in the file (1-indexed)
            comment_body: Markdown content of the comment

        Returns:
            True if successful, False otherwise
        """
        try:
            commit_id = self.pr.head.sha
            self.pr.create_review_comment(
                body=comment_body,
                commit_id=commit_id,
                path=file_path,
                line=line_number
            )
            return True
        except GithubException as e:
            print(f"⚠️ Failed to post inline comment: {e}")
            return False

    def post_review_summary(self, body: str) -> bool:
        """
        Post a general review summary comment in the PR.

        Args:
            body: Comment text (markdown supported)

        Returns:
            True if successful, False otherwise
        """
        try:
            self.pr.create_issue_comment(body)
            return True
        except GithubException as e:
            print(f"⚠️ Failed to post summary comment: {e}")
            return False

    def file_exists_in_pr(self, filepath: str) -> bool:
        """
        Check if a file exists in the PR branch.

        Args:
            filepath: Path to check

        Returns:
            True if exists, False otherwise
        """
        try:
            self.repo.get_contents(filepath, ref=self.pr.head.sha)
            return True
        except GithubException:
            return False