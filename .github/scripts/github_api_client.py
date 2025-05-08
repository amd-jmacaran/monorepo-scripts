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

import os
import requests
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class GitHubAPIClient:
    def __init__(self) -> None:
        """Initialize the GitHub API client with a personal access token."""
        self.token = os.environ.get("GH_TOKEN")
        if not self.token:
            raise RuntimeError("GitHub token must be provided via GH_TOKEN env variable.")
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
        })
        self.api_url = "https://api.github.com"

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

    def _generate_check_run_payload(self, name: str, status: str, details_url: str,
                                    conclusion: str, summary: str) -> dict:
        """Create the payload for a check run with potentially empty fields safely coerced to strings."""
        return {
            "name": name,
            "head_sha": None,  # to be filled in `upsert_check_run`
            "status": status,
            "external_id": None,
            "details_url": details_url,
            "conclusion": conclusion if status == "completed" else None,
            "output": {
                "title": name,
                "summary": summary or "",
            }
        }

    def get_commit_sha(self, repo: str, pr_number: int) -> Optional[str]:
        """Fetch the commit SHA for a given PR number in a repository."""
        url = f"{self.api_url}/repos/{repo}/pulls/{pr_number}"
        data = self._get_json(url, f"Failed to fetch PR #{pr_number} in {repo}")
        return data.get("head", {}).get("sha")

    def get_check_runs_for_commit(self, repo: str, sha: str) -> list:
        """Fetch check runs for a specific commit SHA in a repository."""
        url = f"{self.api_url}/repos/{repo}/commits/{sha}/check-runs"
        data = self._get_json(url, f"Failed to get check runs for {repo}@{sha}")
        return data.get("check_runs", [])

    def get_pr_by_head_branch(self, repo: str, head_branch: str) -> Optional[dict]:
        """Fetch the PR object for a given head branch in a repository, if it exists."""
        url = f"{self.api_url}/repos/{repo}/pulls?head={repo.split('/')[0]}:{head_branch}&state=open"
        data = self._get_json(url, f"Failed to get PRs for {repo} with head {head_branch}")
        return data[0] if data else None

    def get_check_run_by_name(self, repo: str, sha: str, name: str):
        """Return the check run with a given name for a specific commit SHA, if it exists."""
        check_runs = self.get_check_runs_for_commit(repo, sha)
        for check in check_runs:
            if check["name"] == name:
                return check
        return None

    def upsert_check_run(self, repo: str, name: str, sha: str, status: str,
                         details_url: str, conclusion: str, summary: str):
        """Create or update a check run for a specific commit SHA."""
        existing = self.get_check_run_by_name(repo, sha, name)
        payload = self._generate_check_run_payload(name, status, details_url, conclusion, summary)
        payload["head_sha"] = sha
        if existing:
            check_id = existing["id"]
            url = f"{self.api_url}/repos/{repo}/check-runs/{check_id}"
            logger.debug(f"Updating check run '{name}' for {repo}@{sha}")
            return self._request_json("PATCH", url, payload, f"Failed to update check run '{name}'")
        else:
            url = f"{self.api_url}/repos/{repo}/check-runs"
            logger.debug(f"Creating new check run '{name}' for {repo}@{sha}")
            return self._request_json("POST", url, payload, f"Failed to create check run '{name}'")
