#!/usr/bin/env python3

"""
GitHub App Client Utility
--------------------------
This utility provides a class for interacting with GitHub using a GitHub App's authentication.
It handles generating JWTs, retrieving installation tokens, and making authorized API requests
on behalf of the GitHub App.

The class does not directly manage resources like pull requests or issues. Those actions should
be handled by the other clients.

Requirements:
    - GitHub App credentials (App ID, private key) must be available via secrets passed in the env.
    - A GitHub App installation must be present and accessible for the operation.
"""

import os
import jwt
import requests
from time import time
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class GitHubAppClient:

    def __init__(self) -> None:
        """Initialize the GitHub App client for authentication."""
        # Check if the required environment variables are set
        app_id = os.environ.get("APP_ID")
        private_key = os.environ.get("APP_PRIVATE_KEY")
        if not private_key or not app_id:
            raise RuntimeError("Environment variables missing for GitHub App usage.")
        self.token = self._generate_jwt()
        logger.debug("GitHub App Client initialized.")

    def _generate_jwt(self) -> str:
        """Generate a JWT for authenticating as the GitHub App."""
        payload = {
            "iat": int(time()),
            "exp": int(time()) + 60 * 10,
            "iss": (os.environ.get("APP_ID"))
        }
        encoded_jwt = jwt.encode(payload, os.environ.get("APP_PRIVATE_KEY"), algorithm="RS256")
        return encoded_jwt

    def _auth_header(self) -> dict:
        """Return the authorization header for making API requests."""
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
        }

    def get_installation_id_for_repo(self, repo_full_name: str) -> int:
        """Get installation ID for a specific repository."""
        url = f"https://api.github.com/repos/{repo_full_name}/installation"
        response = requests.get(url, headers=self._auth_header())
        logger.debug(f"Installation ID for {repo_full_name}: {response.json()}")
        if response.ok:
            return response.json()["id"]
        else:
            raise RuntimeError(f"Failed to get installation for {repo_full_name}: {response.status_code} {response.text}")

    def get_access_token_for_repo(self, repo_full_name: str) -> str:
        """Get an installation access token for the specified repository."""
        installation_id = self.get_installation_id_for_repo(repo_full_name)
        url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"
        response = requests.post(url, headers=self._auth_header())
        logger.debug(f"Access token for {repo_full_name}: {response.json()}")
        if response.ok:
            return response.json()["token"]
        else:
            raise RuntimeError(f"Failed to get token for {repo_full_name}: {response.status_code} {response.text}")

    def get_authenticated_headers_for_repo(self, repo_full_name: str) -> dict:
        """Return headers with installation access token for a specific repository."""
        return {
            "Authorization": f"token {self.get_access_token_for_repo(repo_full_name)}",
            "Accept": "application/vnd.github+json",
        }
