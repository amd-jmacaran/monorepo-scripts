#!/usr/bin/env python3

"""
GitHub CLI Client Utility
-------------------------
This utility provides a GitHubCLIClient class that wraps GitHub CLI (gh) operations
used across automation scripts, such as retrieving pull request file changes and labels.

When doing manual testing, you can run the same gh commands directly in the terminal.
These commands will be output by the debug logging in debug mode.

Requirements:
    - GitHub CLI (`gh`) must be installed and authenticated.
    - NOTE: GH_TOKEN environment variable hands authentication token to the CLI in a runner.
    - The repository must be accessible to the authenticated user.
"""

import subprocess
import json
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

class GitHubCLIClient:
    """Client for interacting with GitHub via the `gh` CLI."""

    def __init__(self, debug=False):
        if not self._gh_available():
            raise EnvironmentError("GitHub CLI (`gh`) is not installed or not in PATH.")

    def _gh_available(self) -> bool:
        """Check if GitHub CLI is available."""
        try:
            subprocess.run(["gh", "--version"], check=True, stdout=subprocess.DEVNULL)
            return True
        except subprocess.CalledProcessError:
            return False

    def _run_gh_command(self, args: List[str], dry_run: Optional[bool] = False) -> subprocess.CompletedProcess:
        """Run a `gh` CLI command and return the result."""
        cmd = ["gh"] + args
        logger.debug(f"Running command: {' '.join(cmd)}")
        # dry_run option only matters for operations that write to GitHub
        if dry_run:
            result = subprocess.CompletedProcess(cmd, 0, stdout="Dry run enabled. No changes made.", stderr="")
        else:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"Command failed: {' '.join(cmd)}\n{result.stderr.strip()}")
                raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)
        return result

    def get_changed_files(self, repo: str, pr: int) -> List[str]:
        """Fetch the changed files in a pull request using `gh` CLI."""
        result = self._run_gh_command(
            ["pr", "view", str(pr), "--repo", repo, "--json", "files"],
        )
        data = json.loads(result.stdout)
        files = [f["path"] for f in data.get("files", [])]
        logger.debug(f"Changed files in PR #{pr}: {files}")
        return files

    def get_defined_labels(self, repo: str) -> List[str]:
        """Get all labels defined in the given repository."""
        result = self._run_gh_command(["label", "list", "--repo", repo, "--json", "name"])
        return [label["name"] for label in json.loads(result.stdout)]

    def get_existing_labels_on_pr(self, repo: str, pr: int) -> List[str]:
        """Fetch current labels on a PR."""
        result = self._run_gh_command(
            ["pr", "view", str(pr), "--repo", repo, "--json", "labels"]
        )
        data = json.loads(result.stdout)
        labels = [label["name"] for label in data.get("labels", [])]
        logger.debug(f"Existing labels on PR #{pr}: {labels}")
        return labels

    def pr_view(self, repo: str, head: str) -> Optional[int]:
        """Check if a PR exists for the given repo and branch."""
        try:
            result = self._run_gh_command(["pr", "list", "--json", "number", "--repo", repo, "--head", head])
            pr_list = json.loads(result.stdout)
            if pr_list:
                return pr_list[0]["number"]
            else:
                return None
        except subprocess.CalledProcessError:
            return None  # PR does not exist

    def pr_create(self, repo: str, base: str, head: str, title: str, body: str, dry_run: Optional[bool] = False) -> None:
        """Create a new pull request."""
        cmd = [
            "pr", "create",
            "--repo", repo,
            "--base", base,
            "--head", head,
            "--title", title,
            "--body", body
        ]
        self._run_gh_command(cmd, dry_run=dry_run)
        logger.info(f"Created PR from {head} to {base} in {repo}.")

    def sync_labels(self, target_repo: str, pr_number: int, labels: List[str], dry_run: Optional[bool] = False) -> None:
        """Sync labels from the source repo to the target repo (only apply existing labels)."""
        logger.debug(f"Syncing labels to {target_repo} PR #{pr_number}.")
        result = self._run_gh_command(
            ["label", "list", "--repo", target_repo, "--json", "name"]
        )
        target_repo_labels = {label["name"] for label in json.loads(result.stdout)}
        labels_set = set(labels)
        labels_to_apply = labels_set & target_repo_labels
        # Apply labels that exist in both source PR and target repos
        # Wrap in quotes if label contains spaces
        labels_arg = ",".join(f'"{label}"' if " " in label else label for label in labels_to_apply)
        cmd = [
            "pr", "edit",
            str(pr_number),
            "--repo", target_repo,
            "--add-label", labels_arg
        ]
        if not dry_run:
            self._run_gh_command(cmd, dry_run=dry_run)
            logger.info(f"Applied labels '{labels_arg}' to PR #{pr_number} in {target_repo}.")
        else:
            logger.info(f"Dry run: Labels '{labels_arg}' would be applied to PR #{pr_number} in {target_repo}.")
