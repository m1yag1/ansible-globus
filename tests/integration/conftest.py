"""
Integration test fixtures for ansible-globus.

Provides fixtures for running Ansible playbooks in integration tests.

Note: Coverage is disabled for integration tests because modules execute
in separate Ansible subprocesses where pytest-cov cannot track them.
"""

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def aws_gcs_instance_discovery():
    """
    Discover GCS test instance using AWS EC2 API.

    Returns a function that queries AWS EC2 for GCS instances by name.
    Uses boto3 with environment AWS credentials (works with OIDC).

    This allows tests to dynamically discover the test instance IP
    instead of using hardcoded values.
    """

    def _discover_instance(instance_name="ansible-test-gcs-01"):
        try:
            import boto3
        except ImportError:
            pytest.skip("boto3 not available for instance discovery")

        try:
            # Use default credential chain (supports OIDC, environment vars, etc.)
            ec2 = boto3.client("ec2", region_name=os.getenv("AWS_REGION", "us-east-1"))

            # Query instances by Name tag
            response = ec2.describe_instances(
                Filters=[
                    {"Name": "tag:Name", "Values": [instance_name]},
                    {"Name": "instance-state-name", "Values": ["running", "pending"]},
                ]
            )

            # Extract instance from reservations
            instances = []
            for reservation in response.get("Reservations", []):
                instances.extend(reservation.get("Instances", []))

            if not instances:
                return None

            # Return first running instance
            instance = instances[0]
            return {
                "instance_id": instance.get("InstanceId"),
                "public_ip": instance.get("PublicIpAddress"),
                "private_ip": instance.get("PrivateIpAddress"),
                "state": instance.get("State", {}).get("Name"),
            }

        except Exception as e:
            # If AWS discovery fails, return None to allow fallback
            print(f"Warning: AWS instance discovery failed: {e}")
            return None

    return _discover_instance


@pytest.fixture(scope="session")
def sdk_version():
    """
    Get the current Globus SDK major version.

    Used to create unique resource names per SDK version when tests
    run in parallel (e.g., SDK 3 and SDK 4 integration tests).
    """
    try:
        import globus_sdk

        version = globus_sdk.__version__
        major = version.split(".")[0]
        return f"sdk{major}"
    except ImportError:
        return "sdk0"


@pytest.fixture(scope="session")
def test_user_identity():
    """
    Get the current test user's Globus identity.

    This discovers the identity dynamically from the authenticated user
    instead of using a hardcoded identity UUID.

    Returns the identity URN for use in role assignments and other tests.
    """
    # Get credentials from environment
    client_id = os.getenv("GLOBUS_CLIENT_ID")
    client_secret = os.getenv("GLOBUS_CLIENT_SECRET")

    if not client_id or not client_secret:
        pytest.skip("GLOBUS_CLIENT_ID and GLOBUS_CLIENT_SECRET required")

    # For a service account/client credentials, we use the client identity
    # which is in the format: <client_id>@clients.auth.globus.org
    identity_urn = f"urn:globus:auth:identity:{client_id}@clients.auth.globus.org"

    return identity_urn


@pytest.fixture
def test_playbooks_dir():
    """Create temporary directory for test playbooks."""
    temp_dir = tempfile.mkdtemp()
    playbooks_dir = Path(temp_dir) / "playbooks"
    playbooks_dir.mkdir()

    yield playbooks_dir

    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.fixture
def create_playbook(test_playbooks_dir):
    """Fixture that returns a function to create test playbook files."""

    def _create_playbook(content, filename="test_playbook.yml"):
        playbook_path = test_playbooks_dir / filename
        with open(playbook_path, "w") as f:
            f.write(content)
        return str(playbook_path)

    return _create_playbook


@pytest.fixture
def run_playbook():
    """
    Fixture that returns a function to run ansible-playbook.

    IMPORTANT: Extracts host from playbook and uses it as inventory.
    Without this, playbooks skip with "no hosts matched" but still return exit code 0.
    """

    def _run_playbook(playbook_path, extra_vars=None):
        # Read playbook to extract the host
        # This ensures ansible-playbook actually runs against the target
        with open(playbook_path) as f:
            content = f.read()
            # Extract host from "- hosts: X" line
            import re

            host_match = re.search(r"hosts:\s+([^\s]+)", content)
            if not host_match:
                raise ValueError(f"Could not find 'hosts:' in playbook {playbook_path}")

            host = host_match.group(1).strip()

            # Use comma-separated host list as inventory
            # The trailing comma tells ansible this is a host list, not a file
            cmd = ["ansible-playbook", "-i", f"{host},", playbook_path, "-v"]

        # Use python3 discovery on the remote host
        # The remote host needs Python 3 with globus_sdk installed
        # We use 'auto_legacy' which will discover python3 automatically
        cmd.extend(["-e", "ansible_python_interpreter=auto_legacy"])

        if extra_vars:
            cmd.extend(["-e", json.dumps(extra_vars)])

        # Pass through environment variables
        env = os.environ.copy()

        # Set ANSIBLE_COLLECTIONS_PATH to use local module code
        # For FQCN like m1yag1.globus.globus_gcs, we need to create the proper
        # collection directory structure
        project_root = Path(__file__).parent.parent.parent

        # Create a temporary collections path structure with symlinks
        # Ansible expects: <collections_path>/ansible_collections/<namespace>/<name>
        collections_temp = Path(tempfile.gettempdir()) / "ansible_test_collections"
        collection_path = collections_temp / "ansible_collections" / "m1yag1" / "globus"

        # Create directory structure and symlink to project root
        collection_path.parent.mkdir(parents=True, exist_ok=True)
        if collection_path.exists() or collection_path.is_symlink():
            if collection_path.is_symlink():
                collection_path.unlink()
            elif collection_path.is_dir():
                import shutil

                shutil.rmtree(collection_path)
        collection_path.symlink_to(project_root)

        # Set ANSIBLE_COLLECTIONS_PATH to our temp directory
        env["ANSIBLE_COLLECTIONS_PATH"] = str(collections_temp)

        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        return result

    return _run_playbook


def pytest_configure(config):
    """Disable coverage for integration tests."""
    # Coverage is meaningless for integration tests since modules run
    # in separate Ansible subprocesses
    cov = config.pluginmanager.get_plugin("_cov")
    if cov:
        cov.options.no_cov = True
