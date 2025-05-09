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
import re
from time import time
from typing import Optional, List
from github_app_client import GitHubAppClient

logger = logging.getLogger(__name__)

class GitHubAPIClient:

    def __init__(self) -> None:
        """Initialize the GitHub API client using GitHub App authentication."""
        self.api_url = "https://api.github.com"
        self.session = requests.Session()
        self.github_app_client = GitHubAppClient()

    def _get_total_pages(self, response) -> int:
        """Extract the total number of pages from the response's Link header."""
        try:
            # Get the total page count from the 'Link' header if available
            if 'link' in response.headers:
                link_header = response.headers['link']
                # Example: <https://api.github.com/repositories/12345678/issues?page=2>; rel="next", <https://api.github.com/repositories/12345678/issues?page=5>; rel="last"
                match = re.search(r'page=(\d+)\s*>; rel="last"', link_header)
                if match:
                    return int(match.group(1))  # Return the total number of pages
        except Exception as e:
            logger.error(f"Failed to extract total pages: {e}")
        return 1  # Default to 1 page if no pagination info is found

    def _get_json(self, url: str, error_msg: str) -> dict:
        """Helper method to perform a GET request and return the JSON response, handling pagination."""
        page = 1
        per_page = 100
        all_results = []
        # First request to determine the number of pages
        response = self.session.get(f"{url}?page={page}&per_page={per_page}", headers=self.github_app_client.get_authenticated_headers())
        if not response.ok:
            logger.error(f"{error_msg}: {response.status_code} {response.text}")
            return {}
        data = response.json()
        all_results.extend(data)
        # Check pagination headers to determine if more pages exist
        total_pages = self._get_total_pages(response)  # Implement this function to get the total number of pages from headers
        # If more than 1 page, iterate over the remaining pages
        for page in range(2, total_pages + 1):
            response = self.session.get(f"{url}?page={page}&per_page={per_page}", headers=self.github_app_client.get_authenticated_headers())
            if not response.ok:
                logger.error(f"{error_msg}: {response.status_code} {response.text}")
                break
            data = response.json()
            all_results.extend(data)
        return all_results

    def _request_json(self, method: str, url: str, json: dict, error_msg: str) -> dict:
        """Helper method to perform a request and return JSON response with dry-run option."""
        response = self.session.request(method, url, headers=self.github_app_client.get_authenticated_headers(), json=json)
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

    def get_changed_files(self, repo: str, pr: int) -> List[str]:
        """Fetch the changed files in a pull request using GitHub API."""
        files_url = f"{self.api_url}/repos/{repo}/pulls/{pr}/files"
        files_data = self._get_json(files_url, f"Failed to fetch files for PR #{pr} in {repo}")
        files = [file["filename"] for file in files_data]
        logger.debug(f"Changed files in PR #{pr}: {files}")
        return files

    def get_defined_labels(self, repo: str) -> List[str]:
        """Get all labels defined in the given repository."""
        url = f"{self.api_url}/repos/{repo}/labels"
        labels_data = self._get_json(url, f"Failed to fetch labels from {repo}")
        labels = [label["name"] for label in labels_data]
        logger.debug(f"Defined labels in {repo}: {labels}")
        return labels

    def get_existing_labels_on_pr(self, repo: str, pr: int) -> List[str]:
        """Fetch current labels on a PR."""
        url = f"{self.api_url}/repos/{repo}/issues/{pr}/labels"
        labels_data = self._get_json(url, f"Failed to fetch labels for PR #{pr} in {repo}")
        labels = [label["name"] for label in labels_data]
        logger.debug(f"Existing labels on PR #{pr}: {labels}")
        return labels

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

    def pr_view(self, repo: str, head: str) -> Optional[int]:
        """Check if a PR exists for the given repo and branch."""
        url = f"{self.api_url}/repos/{repo}/pulls?head={head}"
        try:
            result = self._get_json(url, f"Failed to retrieve PR for head branch {head} in repo {repo}")
            return result[0]["number"] if result else None
        except Exception as e:
            logger.warning(f"Failed to retrieve PR from {repo} with head {head}: {e}")
            return None  # PR does not exist

    def get_pr_by_head_branch(self, repo: str, head: str) -> Optional[dict]:
        """Fetch the PR object for a given head branch in a repository, if it exists."""
        url = f"{self.api_url}/repos/{repo}/pulls?head={repo.split('/')[0]}:{head}&state=open"
        data = self._get_json(url, f"Failed to get PRs for {repo} with head {head}")
        return data[0] if data else None

    def get_check_run_by_name(self, repo: str, sha: str, name: str) -> Optional[dict]:
        """Return the check run with a given name for a specific commit SHA, if it exists."""
        check_runs = self.get_check_runs_for_ref(repo, sha)
        for check in check_runs:
            if check["name"] == name:
                return check
        return None

    def pr_create(self, repo: str, base: str, head: str, title: str, body: str) -> None:
        """Create a new pull request."""
        url = f"{self.api_url}/repos/{repo}/pulls"
        payload = {
            "title": title,
            "body": body,
            "head": head,
            "base": base
        }
        self._request_json("POST", url, payload, f"Failed to create PR from {head} to {base} in {repo}")
        logger.info(f"Created PR from {head} to {base} in {repo}.")

    def close_pr_and_delete_branch(self, repo: str, pr_number: int) -> None:
        """Close a pull request and delete the associated branch using the GitHub API."""
        url = f"{self.api_url}/repos/{repo}/pulls/{pr_number}"
        payload = {"state": "closed"}
        self._request_json("PATCH", url, payload, f"Failed to close PR #{pr_number} in {repo}")
        branch_url = f"{self.api_url}/repos/{repo}/git/refs/heads/{pr_number}"
        self._request_json("DELETE", branch_url, {}, f"Failed to delete branch for PR #{pr_number}")
        logger.info(f"Closed pull request #{pr_number} and deleted the associated branch in {repo}.")

    def sync_labels(self, target_repo: str, pr_number: int, labels: List[str], dry_run: Optional[bool] = False) -> None:
        """Sync labels from the source repo to the target repo (only apply existing labels)."""
        logger.debug(f"Syncing labels to {target_repo} PR #{pr_number}.")
        url = f"{self.api_url}/repos/{target_repo}/labels"
        target_repo_labels = {label["name"] for label in self._get_json(url, f"Failed to fetch labels for {target_repo}")}
        labels_set = set(labels)
        labels_to_apply = labels_set & target_repo_labels
        # Apply labels that exist in both source PR and target repos
        # Wrap in quotes if label contains spaces
        labels_arg = [f'"{label}"' if " " in label else label for label in labels_to_apply]
        if labels_to_apply:
            url = f"{self.api_url}/repos/{target_repo}/issues/{pr_number}/labels"
            payload = {"labels": list(labels_to_apply)}
            if not dry_run:
                self._request_json("POST", url, payload, f"Failed to apply labels to PR #{pr_number} in {target_repo}")
                logger.info(f"Applied labels '{', '.join(labels_arg)}' to PR #{pr_number} in {target_repo}.")
            else:
                logger.info(f"Dry run: Labels '{', '.join(labels_arg)}' would be applied to PR #{pr_number} in {target_repo}.")
        else:
            logger.info(f"No valid labels to apply to PR #{pr_number} in {target_repo}.")

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
