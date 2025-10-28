#!/usr/bin/python
"""
Common utilities for Globus Ansible modules.
"""

import json
import typing as t


class GlobusModuleBase:
    """Base class for Globus Ansible modules."""

    def __init__(self, module: t.Any) -> None:
        self.module = module
        self.changed: bool = False
        self.result: dict[str, t.Any] = {"changed": False, "msg": ""}

    def run_command(
        self, cmd: list[str], check_rc: bool = True
    ) -> tuple[int, str, str]:
        """Execute a command and return result."""
        rc, stdout, stderr = self.module.run_command(cmd, check_rc=check_rc)
        return rc, stdout, stderr

    def parse_json_output(self, output: str) -> dict[str, t.Any]:
        """Parse JSON output from Globus CLI commands."""
        try:
            return json.loads(output)
        except json.JSONDecodeError as e:
            self.module.fail_json(msg=f"Failed to parse JSON output: {e}")
            # This is unreachable but mypy doesn't know that fail_json exits
            raise

    def check_globus_cli(self) -> None:
        """Verify Globus CLI is installed and available."""
        rc, _, _ = self.run_command(["which", "globus"], check_rc=False)
        if rc != 0:
            self.module.fail_json(msg="Globus CLI not found. Please install it first.")

    def is_authenticated(self) -> bool:
        """Check if user is authenticated with Globus."""
        rc, stdout, _ = self.run_command(["globus", "whoami"], check_rc=False)
        if rc != 0:
            return False
        try:
            data = json.loads(stdout)
            return "id" in data
        except json.JSONDecodeError:
            return False

    def exit_json(self, **kwargs: t.Any) -> None:
        """Exit with JSON result."""
        self.result.update(kwargs)
        self.result["changed"] = self.changed
        self.module.exit_json(**self.result)

    def fail_json(self, msg: str) -> None:
        """Exit with failure."""
        self.module.fail_json(msg=msg)


def globus_argument_spec() -> dict[str, t.Any]:
    """Common argument specification for Globus modules."""
    return {
        "state": {
            "type": "str",
            "default": "present",
            "choices": ["present", "absent"],
        },
        "auth_method": {
            "type": "str",
            "default": "cli",
            "choices": ["cli", "client_credentials", "access_token"],
        },
        "client_id": {"type": "str", "no_log": False},
        "client_secret": {"type": "str", "no_log": True},
        "access_token": {"type": "str", "no_log": True},
    }
