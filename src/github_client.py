"""
GitHub API client for the AI Code Reviewer Action.
"""

import base64
from typing import List, Dict, Any, Optional
from github import Github, GithubException


class GitHubClient:
    def __init__(self, token: str, repo_full_name: str, pr_number: int):
        self.token = token
        self.repo_full_name = repo_full_name
        self.pr_number = pr_number

        self.github = Github(token)
        self.repo = self.github.get_repo(repo_full_name)
        self.pr = self.repo.get_pull(pr_number)

    def get_changed_files(self) -> List[Dict[str, Any]]:
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
        try:
            contents = self.repo.get_contents(filepath, ref=self.pr.head.sha)
            decoded = base64.b64decode(contents.content).decode("utf-8")
            return decoded
        except GithubException as e:
            if e.status == 404:
                return None
            raise

    def get_pr_info(self) -> Dict[str, Any]:
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
        try:
            self.pr.create_issue_comment(body)
            return True
        except GithubException as e:
            print(f"Failed to create PR comment: {e}")
            return False

    def post_inline_comment(self, file_path: str, line_number: int, comment_body: str) -> bool:
        try:
            commit_id = self.pr.head.sha

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
        try:
            self.pr.create_issue_comment(body)
            return True
        except GithubException as e:
            print(f"⚠️ Failed to post summary comment: {e}")
            return False