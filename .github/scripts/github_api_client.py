#!/usr/bin/env python3
"""
GitHub API Client
-----------------
Provides high-level GitHub REST API operations used by reflection scripts.
This client exists because the GitHub CLI does not support creating check runs directly.

This includes:
- Fetching PR details
- Fetching check runs for a commit SHA
- Creating or updating synthetic check runs

Requires:
    GH_TOKEN environment variable (automatically available in GitHub Actions)

Author: Your Name
"""

import requests
import logging
from typing import Optional
from time import time
from github_app_client import GitHubAppClient

logger = logging.getLogger(__name__)

class GitHubAPIClient:

    def __init__(self) -> None:
        """Initialize the GitHub API client using GitHub App authentication."""
        self.api_url = "https://api.github.com"
        self.session = requests.Session()
        github_app_client = GitHubAppClient()
        self.session.headers.update({
            "Authorization": f"Bearer {github_app_client.token}",
            "Accept": "application/vnd.github+json",
        })

    def _get_json(self, url: str, error_msg: str) -> dict:
        """Helper method to perform a GET request and return JSON response."""
        response = self.session.get(url)
        if not response.ok:
            logger.error(f"{error_msg}: {response.status_code} {response.text}")
            return {}
        return response.json()

    def _request_json(self, method: str, url: str, json: dict, error_msg: str) -> dict:
        """Helper method to perform a request and return JSON response."""
        response = self.session.request(method, url, json=json)
        if not response.ok:
            logger.error(f"{error_msg}: {response.status_code} {response.text}")
            return {}
        return response.json()

    def _generate_check_run_payload(self, name: str, head_sha: str, status: str,
                                    details_url: str, conclusion: str, completed_at: str,
                                    title: str, summary: str) -> dict:
        """Create the payload for a check run with potentially empty fields safely coerced to strings."""
        return {
            "name": name,
            "head_sha": head_sha,
            "status": status,
            "details_url": details_url,
            "conclusion": conclusion if status == "completed" else "",
            "completed_at": completed_at if status == "completed" else "",
            "output": {
                "title": title or name,
                "summary": summary or "",
            }
        }

    def get_head_sha_for_pr(self, repo: str, pr_number: int) -> Optional[str]:
        """Fetch the head SHA for a given pull request number in a repository."""
        url = f"{self.api_url}/repos/{repo}/pulls/{pr_number}"
        data = self._get_json(url, f"Failed to fetch PR #{pr_number} in {repo}")
        return data.get("head", {}).get("sha")

    def get_branch_name_for_pr(self, repo: str, pr_number: int) -> Optional[str]:
        """Fetch the head branch name for a given pull request number in a repository."""
        url = f"{self.api_url}/repos/{repo}/pulls/{pr_number}"
        data = self._get_json(url, f"Failed to fetch PR #{pr_number} in {repo}")
        return data.get("head", {}).get("ref")

    def get_check_runs_for_ref(self, repo: str, ref: str) -> list:
        """Fetch check runs for a specific reference in a repository."""
        url = f"{self.api_url}/repos/{repo}/commits/{ref}/check-runs"
        data = self._get_json(url, f"Failed to get check runs for {repo}@{ref}")
        return data.get("check_runs", [])

    def get_pr_by_head_branch(self, repo: str, head_branch: str) -> Optional[dict]:
        """Fetch the PR object for a given head branch in a repository, if it exists."""
        url = f"{self.api_url}/repos/{repo}/pulls?head={repo.split('/')[0]}:{head_branch}&state=open"
        data = self._get_json(url, f"Failed to get PRs for {repo} with head {head_branch}")
        return data[0] if data else None

    def get_check_run_by_name(self, repo: str, sha: str, name: str) -> Optional[dict]:
        """Return the check run with a given name for a specific commit SHA, if it exists."""
        check_runs = self.get_check_runs_for_ref(repo, sha)
        for check in check_runs:
            if check["name"] == name:
                return check
        return None

    def upsert_check_run(self, repo: str, name: str, sha: str, status: str,
                         details_url: str, conclusion: str, completed_at: str,
                         title: str, summary: str) -> dict:
        """Create or update a check run for a specific commit SHA."""
        existing = self.get_check_run_by_name(repo, sha, name)
        payload = self._generate_check_run_payload(name, sha, status, details_url,
                                                   conclusion, completed_at, title, summary)
        logger.debug(f"Check run payload: {payload}")
        if existing:
            check_id = existing["id"]
            url = f"{self.api_url}/repos/{repo}/check-runs/{check_id}"
            logger.debug(f"Updating check run '{name}' for {repo}@{sha}")
            return self._request_json("PATCH", url, payload, f"Failed to update check run '{name}'")
        else:
            url = f"{self.api_url}/repos/{repo}/check-runs"
            logger.debug(f"Creating new check run '{name}' for {repo}@{sha}")
            return self._request_json("POST", url, payload, f"Failed to create check run '{name}'")
