#!/usr/bin/env python3
"""
Utility functions for naming conventions and templates in monorepo fanout automation.

Example usage:
    from monorepo_utils import FanoutNaming

    # Full naming object for use in loops
    naming = FanoutNaming(pr_number=42, repo="my-org/monorepo", category="projects", name="rocBLAS", url="ROCm/rocBLAS")
    print(naming.branch_name)

    # Static method when only branch name is needed
    branch = FanoutNaming.compute_branch_name(42, "rocBLAS")

    naming = FanoutNaming(
        pr_number=args.pr,
        repo=args.repo,
        category=entry.category,
        name=entry.name,
        url=entry.url
    )
    branch = naming.branch_name

    branch = FanoutNaming.compute_branch_name(args.pr, entry.name)
"""

from dataclasses import dataclass

@dataclass
class FanoutNaming:
    pr_number: int
    repo: str           # monorepo full name, e.g., "my-org/monorepo"
    category: str
    name: str
    url: str            # e.g., "ROCm/rocBLAS"

    @property
    def branch_name(self) -> str:
        return self.compute_branch_name(self.pr_number, self.name)

    @staticmethod
    def compute_branch_name(pr_number: int, name: str) -> str:
        return f"monorepo-pr-{pr_number}-{name}"

    @property
    def prefix(self) -> str:
        return f"{self.category}/{self.name}"

    @property
    def subrepo_full_url(self) -> str:
        return f"https://github.com/{self.url}.git"

    @property
    def pr_title(self) -> str:
        return f"[DO NOT MERGE] [Fanout] [Monorepo] PR #{self.pr_number} to {self.name}"

    @property
    def pr_body(self) -> str:
        return (
            f"This is an automated PR for subtree `{self.prefix}` "
            f"originating from monorepo PR [#{self.pr_number}](https://github.com/{self.repo}/pull/{self.pr_number}). "
            f"PLEASE DO NOT MERGE OR TOUCH THIS PR, AUTOMATED WORKFLOWS FROM THE MONOREPO ARE USING IT."
        )
