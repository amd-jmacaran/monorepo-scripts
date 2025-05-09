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
        self.installation_id = self._get_installation_id()
        logger.debug(f"GitHub App Client initialized with installation ID: {self.installation_id}")

    def _generate_jwt(self) -> str:
        """Generate a JWT for authenticating as the GitHub App."""
        payload = {
            "iat": int(time()),
            "exp": int(time()) + 60 * 10,
            "iss": (os.environ.get("APP_ID"))
        }
        encoded_jwt = jwt.encode(payload, os.environ.get("APP_PRIVATE_KEY"), algorithm="RS256")
        return encoded_jwt

    def _get_installation_id(self) -> Optional[int]:
        """Fetch the installation ID for the GitHub App."""
        url = f"https://api.github.com/app/installations"
        response = requests.get(url, headers=self._auth_header())
        if response.ok:
            installations = response.json()
            if installations:
                return installations[0]["id"]
            else:
                raise RuntimeError("No installations found for the GitHub App.")
        else:
            raise RuntimeError(f"Failed to fetch installations: {response.status_code} {response.text}")

    def _auth_header(self) -> dict:
        """Return the authorization header for making API requests."""
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
        }

    def get_access_token(self) -> str:
        """Generate an access token for the app's installation."""
        url = f"https://api.github.com/app/installations/{self.installation_id}/access_tokens"
        response = requests.post(url, headers=self._auth_header())
        if response.ok:
            return response.json()["token"]
        else:
            raise RuntimeError(f"Failed to create access token: {response.status_code} {response.text}")
