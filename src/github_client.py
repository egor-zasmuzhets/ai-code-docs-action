"""
GitHub API client for the AI Code Reviewer Action.

This module provides a wrapper around PyGithub for interacting with GitHub API.
Handles retrieving PR files, reading file contents, committing documentation,
and creating comments (both regular and inline).
"""

import base64
from typing import List, Dict, Any, Optional
from github import Github, GithubException


class GitHubClient:
    """
    GitHub API client for Pull Request operations.

    Provides a high-level interface for PR-related operations:
    - Retrieving PR information
    - Getting changed files and their contents
    - Committing documentation to the PR branch
    - Creating regular and inline comments

    Attributes:
        token (str): GitHub Personal Access Token (usually ${{ github.token }})
        repo_full_name (str): Repository name in "owner/repo" format
        pr_number (int): Pull Request number
        github (Github): PyGithub client instance
        repo (Repository): GitHub repository object
        pr (PullRequest): Pull Request object
    """

    def __init__(self, token: str, repo_full_name: str, pr_number: int):
        """
        Initializes the GitHub client.

        Creates a connection to GitHub API and fetches repository and PR objects.

        Args:
            token (str): GitHub token with repo and pull_requests permissions
            repo_full_name (str): Repository name in "owner/repo" format
            pr_number (int): Pull Request number to analyze

        Raises:
            GithubException: On authentication errors or if repo/PR is inaccessible
        """
        self.token = token
        self.repo_full_name = repo_full_name
        self.pr_number = pr_number

        self.github = Github(token)
        self.repo = self.github.get_repo(repo_full_name)
        self.pr = self.repo.get_pull(pr_number)

    def get_changed_files(self) -> List[Dict[str, Any]]:
        """
        Retrieves the list of changed files in the PR with their contents.

        Returns:
            List[Dict[str, Any]]: List of dictionaries, each containing:
                - filename (str): Path to the file
                - status (str): "added", "modified", or "removed"
                - additions (int): Number of lines added
                - deletions (int): Number of lines deleted
                - patch (str): Diff patch of the file
                - content (str|None): Full file content (None for removed files)

        Note:
            For removed files, content is None. For others, full content is loaded.
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
        Retrieves the full content of a file from the PR branch.

        Args:
            filepath (str): Path to the file in the repository

        Returns:
            Optional[str]: File content as string, or None if file not found

        Raises:
            GithubException: On GitHub API errors (except 404)

        Note:
            File content comes base64-encoded, so decoding is required.
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
        Retrieves basic information about the Pull Request.

        Returns:
            Dict[str, Any]: Dictionary with PR information:
                - title (str): PR title
                - description (str): PR body (empty string if None)
                - author (str): Author's GitHub login
                - branch (str): Head branch name
                - base_branch (str): Base branch name
                - url (str): PR URL on GitHub
                - number (int): PR number
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

    def commit_documentation(self, filepath: str, content: str, commit_message: str) -> bool:
        """
        Commits a documentation file to the PR branch (creates or updates).

        Args:
            filepath (str): Path where to create/update the file
            content (str): New file content
            commit_message (str): Git commit message

        Returns:
            bool: True on success, False on error

        Note:
            Automatically detects if the file exists:
            - If exists: updates it
            - If not: creates a new file
            On GitHub API error, prints message and returns False.
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
        Creates a regular comment in the Pull Request.

        Args:
            body (str): Comment text (Markdown supported)

        Returns:
            bool: True on success, False on error

        Note:
            The comment appears in the general PR discussion thread,
            not attached to specific code lines.
        """
        try:
            self.pr.create_issue_comment(body)
            return True
        except GithubException as e:
            print(f"Failed to create PR comment: {e}")
            return False

    def post_inline_comment(self, file_path: str, line_number: int, comment_body: str) -> bool:
        """
        Posts a comment attached to a specific line of code in the PR.

        Args:
            file_path (str): Path to the file for comment attachment
            line_number (int): Line number in the file (1-indexed)
            comment_body (str): Comment text (Markdown supported)

        Returns:
            bool: True on success, False on error

        Note:
            Compatible with different PyGithub versions — tries 4 different
            API signatures and uses the first that works.
            The comment appears directly in the PR code view.
        """
        try:
            commit_id = self.pr.head.sha

            # Try different API signatures for compatibility
            try:
                self.pr.create_review_comment(comment_body, commit_id, file_path, line_number)
                return True
            except (TypeError, AttributeError):
                pass

            try:
                self.pr.create_review_comment(
                    body=comment_body,
                    commit_id=commit_id,
                    path=file_path,
                    line=line_number
                )
                return True
            except (TypeError, AttributeError):
                pass

            try:
                self.pr.create_review_comment(
                    body=comment_body,
                    commit=commit_id,
                    path=file_path,
                    line=line_number
                )
                return True
            except (TypeError, AttributeError):
                pass

            try:
                review = self.pr.create_review(commit_id=commit_id, event="COMMENT")
                review.create_comment(body=comment_body, path=file_path, line=line_number)
                return True
            except Exception:
                pass

            print(f"   ⚠️ Could not post inline comment")
            return False
        except Exception as e:
            print(f"⚠️ Failed to post inline comment: {e}")
            return False

    def post_review_summary(self, body: str) -> bool:
        """
        Posts a summary comment with analysis results in the PR.

        Args:
            body (str): Summary text (Markdown supported)

        Returns:
            bool: True on success, False on error

        Note:
            Used to publish a brief report after analysis completes.
            Typically contains number of files analyzed and issues found.
        """
        try:
            self.pr.create_issue_comment(body)
            return True
        except GithubException as e:
            print(f"⚠️ Failed to post summary comment: {e}")
            return False