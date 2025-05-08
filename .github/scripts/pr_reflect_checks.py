#!/usr/bin/env python3

"""
PR Checks Reflection Script
-----------------------------
This script polls the status of checks on fanned-out pull requests (in sub-repositories)
and reflects them as synthetic checks on the original monorepo pull request.

Each fanned-out PR must use the naming convention:
    monorepo-pr-<pr_number>-<subtree>

Arguments:
    --repo      : Full     --repo      : Full repository name (e.g., org/repo)
 name (e.g., org/repo)
    --pr        : Pull request number
    --config    : OPTIONAL, path to the repos-config.json file
    --dry-run   : If set, will only log actions without making changes.
    --debug     : If set, enables detailed debug logging.

Example Usage:
    To run in debug mode and perform a dry-run (no changes made):
        python pr-reflect-checks.py --repo ROCm/rocm-libraries --pr 123 --debug --dry-run
"""

import argparse
import logging
from typing import List, Optional

from github_api_client import GitHubAPIClient
from repo_config_model import RepoEntry
from config_loader import load_repo_config
from utils_fanout_naming import FanoutNaming

logger = logging.getLogger(__name__)

def parse_arguments(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Reflect fanned-out PR checks onto the monorepo PR.")
    parser.add_argument("--repo", required=True, help="Full repository name (e.g., org/repo)")
    parser.add_argument("--pr", required=True, type=int, help="Pull request number")
    parser.add_argument("--config", required=False, default=".github/repos-config.json", help="Path to the repos-config.json file")
    parser.add_argument("--dry-run", action="store_true", help="If set, only logs actions without making changes.")
    parser.add_argument("--debug", action="store_true", help="If set, enables detailed debug logging.")
    return parser.parse_args(argv)

def main(argv: Optional[List[str]] = None) -> None:
    """Main function to execute the PR checks reflection logic."""
    args = parse_arguments(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO
    )
    client = GitHubAPIClient()
    config = load_repo_config(args.config)
    monorepo_branch = client.get_branch_name_for_pr(args.repo, args.pr)
    monorepo_checks = {
        check["name"]: check
        for check in client.get_check_runs_for_ref(args.repo, monorepo_branch)
    }
    for entry in config:
        subrepo = entry.url
        branch = FanoutNaming.compute_branch_name(args.pr, entry.name)
        pr = client.get_pr_by_head_branch(subrepo, branch)
        if not pr:
            logger.info(f"No open PR found in {subrepo} for branch {branch}")
            continue
        checks = client.get_check_runs_for_ref(subrepo, branch)
        for check in checks:
            synthetic_name = f"{entry.name}: {check['name']}"
            status = check["status"]
            conclusion = check.get("conclusion", "neutral")
            details_url = check.get("details_url", "")
            summary = check.get("output", {}).get("summary", "")
            existing = monorepo_checks.get(synthetic_name)
            needs_update = (
                not existing or
                existing["status"] != status or
                existing.get("conclusion") != conclusion or
                existing.get("output", {}).get("summary") != summary
            )
            if not needs_update:
                logger.debug(f"Skipped unchanged check: {synthetic_name}")
                continue
            logger.info(f"Reflecting check: {synthetic_name}")
            if not args.dry_run:
                client.upsert_check_run(
                    args.repo, synthetic_name, args.pr,
                    status, details_url, conclusion, summary
                )

if __name__ == "__main__":
    main()
