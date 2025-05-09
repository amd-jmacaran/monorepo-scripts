#!/usr/bin/env python3

"""
Repository Configuration Utilities
-----------------------------------
This module contains utility functions for loading and validating repository
configuration from a JSON file. It utilizes Pydantic for validation, ensuring
the configuration is well-formed and consistent with the expected schema.

Key functionality:
- Loading repository configuration from a JSON file
- Validating the configuration using Pydantic
- Handling errors in loading or validating the configuration

Required environment:
- The `repo_config_model` module containing `RepoConfig` and `RepoEntry` classes.
"""

import json
import sys
import logging
from typing import List
from repo_config_model import RepoConfig, RepoEntry

logger = logging.getLogger(__name__)

def load_repo_config(config_path: str) -> List[RepoEntry]:
    """Load and validate repository config from JSON using Pydantic."""
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        config = RepoConfig(**data)
        return config.repositories
    except Exception as e:
        logger.error(f"Failed to load or validate config file '{config_path}': {e}")
        sys.exit(1)
