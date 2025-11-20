#!/usr/bin/python
"""
API interaction utilities for Globus Ansible modules.
"""

import os
import typing as t

import requests  # type: ignore

from .globus_auth import GlobusAuth
from .globus_common import GlobusModuleBase


class GlobusAPI(GlobusModuleBase):
    """Handle Globus API interactions."""

    BASE_URLS: dict[str, str] = {
        "auth": "https://auth.globus.org/v2",
        "transfer": "https://transfer.api.globus.org/v0.10",
        "groups": "https://groups.api.globus.org/v2",
        "compute": "https://compute.api.globus.org/v2",
        "flows": "https://flows.api.globus.org",
    }

    # Test environment URLs (from Globus SDK)
    TEST_URLS: dict[str, str] = {
        "auth": "https://auth.test.globuscs.info/v2",
        "transfer": "https://transfer.api.test.globuscs.info/v0.10",
        "groups": "https://groups.api.test.globuscs.info/v2",
        "compute": "https://compute.api.test.globuscs.info",
        "flows": "https://test.flows.automate.globus.org",
    }

    def __init__(self, module: t.Any, service: str = "transfer") -> None:
        super().__init__(module)
        self.service = service

        # Check for environment override
        globus_env = os.getenv("GLOBUS_SDK_ENVIRONMENT", "production")
        urls = self.TEST_URLS if globus_env == "test" else self.BASE_URLS

        self.base_url: str | None = urls.get(service)
        if not self.base_url:
            self.fail_json(f"Unknown service: {service}")

        self.auth = GlobusAuth(module)
        self.auth.authenticate()
        self.headers: dict[str, str] = self.auth.get_auth_headers()
        # Note: Content-Type is automatically set by requests when using json= parameter

    def get(
        self, endpoint: str, params: dict[str, t.Any] | None = None
    ) -> dict[str, t.Any]:
        """Make GET request to Globus API."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            response = requests.get(
                url, headers=self.headers, params=params, timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            self.fail_json(f"API GET request failed: {e}")
            # Unreachable but needed for mypy
            return {}

    def post(
        self, endpoint: str, data: dict[str, t.Any] | None = None
    ) -> dict[str, t.Any]:
        """Make POST request to Globus API."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            # Use json= parameter to let requests handle serialization and Content-Type
            response = requests.post(url, headers=self.headers, json=data, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            self.fail_json(f"API POST request failed: {e}")
            # Unreachable but needed for mypy
            return {}

    def put(
        self, endpoint: str, data: dict[str, t.Any] | None = None
    ) -> dict[str, t.Any]:
        """Make PUT request to Globus API."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            # Use json= parameter to let requests handle serialization and Content-Type
            response = requests.put(url, headers=self.headers, json=data, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            self.fail_json(f"API PUT request failed: {e}")
            # Unreachable but needed for mypy
            return {}

    def delete(self, endpoint: str) -> bool | dict[str, t.Any]:
        """Make DELETE request to Globus API."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            response = requests.delete(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            return response.status_code == 204 or response.json()
        except requests.RequestException as e:
            self.fail_json(f"API DELETE request failed: {e}")
            # Unreachable but needed for mypy
            return False

    def cli_command(self, cmd_parts: list[str]) -> dict[str, t.Any]:
        """Execute Globus CLI command and return parsed JSON."""
        cmd = ["globus"] + cmd_parts + ["--format", "json"]
        rc, stdout, stderr = self.run_command(cmd)

        if rc != 0:
            self.fail_json(f"Globus CLI command failed: {stderr}")

        return self.parse_json_output(stdout)
