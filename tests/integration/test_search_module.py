#!/usr/bin/env python
"""
Integration tests for globus_search module.

These tests create, verify, and delete Globus Search indexes.

NOTE: Search indexes are limited to 3 trial indexes per account.
Trial indexes auto-delete after 30 days. These tests clean up after
themselves, but if tests are interrupted, you may need to manually
delete indexes via the Globus web interface.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def auth_method_suffix():
    """Get suffix based on auth method to avoid conflicts."""
    auth_method = os.getenv("TEST_AUTH_METHOD", "default")
    return auth_method.replace("_", "-")


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
    """Fixture that returns a function to run ansible-playbook for localhost tests."""

    def _run_playbook(playbook_path, extra_vars=None):
        cmd = ["ansible-playbook", playbook_path, "-v"]

        # Use the current Python interpreter for module execution
        # This ensures globus_sdk and other dependencies are available
        python_interpreter = sys.executable
        cmd.extend(["-e", f"ansible_python_interpreter={python_interpreter}"])

        if extra_vars:
            cmd.extend(["-e", json.dumps(extra_vars)])

        # Pass through environment variables
        env = os.environ.copy()

        # Set ANSIBLE_COLLECTIONS_PATH to use local module code
        project_root = Path(__file__).parent.parent.parent

        # Create a temporary collections path structure with symlinks
        collections_temp = Path(tempfile.gettempdir()) / "ansible_test_collections"
        collection_path = collections_temp / "ansible_collections" / "m1yag1" / "globus"

        # Create directory structure and symlink to project root
        collection_path.parent.mkdir(parents=True, exist_ok=True)
        if collection_path.exists() or collection_path.is_symlink():
            if collection_path.is_symlink():
                collection_path.unlink()
            elif collection_path.is_dir():
                shutil.rmtree(collection_path)
        collection_path.symlink_to(project_root)

        # Set ANSIBLE_COLLECTIONS_PATH to our temp directory
        env["ANSIBLE_COLLECTIONS_PATH"] = str(collections_temp)

        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        return result

    return _run_playbook


def test_search_index_create_and_delete(
    ansible_playbook_auth_params_search,
    create_playbook,
    run_playbook,
    sdk_version,
    auth_method_suffix,
):
    """Test creating and deleting a Globus Search index."""
    # Use unique name with SDK version and auth method to avoid conflicts
    index_name = f"ansible-test-{sdk_version}-{auth_method_suffix}"

    playbook_content = f"""
---
- hosts: localhost
  connection: local
  gather_facts: false
  tasks:
    - name: Delete any existing test index (cleanup from previous runs)
      m1yag1.globus.globus_search:
        name: "{index_name}"
        {ansible_playbook_auth_params_search}
        state: absent
      register: cleanup_result

    - name: Create test search index
      m1yag1.globus.globus_search:
        name: "{index_name}"
        description: "Integration test index for Ansible - {sdk_version}"
        {ansible_playbook_auth_params_search}
        state: present
      register: create_result

    - name: Verify index was created
      assert:
        that:
          - create_result.changed
          - create_result.index_id is defined
          - create_result.name == "{index_name}"
        fail_msg: "Index creation failed or missing expected fields"

    - name: Test idempotency - create again should not change
      m1yag1.globus.globus_search:
        name: "{index_name}"
        description: "Integration test index for Ansible - {sdk_version}"
        {ansible_playbook_auth_params_search}
        state: present
      register: idempotent_result

    - name: Verify idempotency
      assert:
        that:
          - not idempotent_result.changed
          - idempotent_result.index_id == create_result.index_id
        fail_msg: "Second create should not have changed anything"

    - name: Delete test search index
      m1yag1.globus.globus_search:
        name: "{index_name}"
        {ansible_playbook_auth_params_search}
        state: absent
      register: delete_result

    - name: Verify index was deleted
      assert:
        that:
          - delete_result.changed
        fail_msg: "Index deletion should have changed state"

    - name: Test delete idempotency - delete again should not change
      m1yag1.globus.globus_search:
        name: "{index_name}"
        {ansible_playbook_auth_params_search}
        state: absent
      register: delete_idempotent_result

    - name: Verify delete idempotency
      assert:
        that:
          - not delete_idempotent_result.changed
        fail_msg: "Second delete should not have changed anything"
"""

    playbook_path = create_playbook(playbook_content, "test_search_index.yml")
    result = run_playbook(playbook_path)

    # Print output for debugging
    print(f"STDOUT:\n{result.stdout}")
    print(f"STDERR:\n{result.stderr}")

    assert (
        result.returncode == 0
    ), f"Playbook failed:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"


def test_search_index_check_mode(
    ansible_playbook_auth_params_search,
    create_playbook,
    run_playbook,
    sdk_version,
    auth_method_suffix,
):
    """Test check mode for search index operations."""
    index_name = f"ansible-check-{sdk_version}-{auth_method_suffix}"

    playbook_content = f"""
---
- hosts: localhost
  connection: local
  gather_facts: false
  tasks:
    - name: Delete any existing test index (cleanup)
      m1yag1.globus.globus_search:
        name: "{index_name}"
        {ansible_playbook_auth_params_search}
        state: absent

    - name: Check mode - create index (should not actually create)
      m1yag1.globus.globus_search:
        name: "{index_name}"
        description: "Check mode test index"
        {ansible_playbook_auth_params_search}
        state: present
      check_mode: true
      register: check_create

    - name: Verify check mode reports would change
      assert:
        that:
          - check_create.changed
        fail_msg: "Check mode should report it would create"

    - name: Verify index was NOT actually created
      m1yag1.globus.globus_search:
        name: "{index_name}"
        {ansible_playbook_auth_params_search}
        state: absent
      register: verify_not_created

    - name: Confirm index did not exist
      assert:
        that:
          - not verify_not_created.changed
        fail_msg: "Index should not have been created in check mode"
"""

    playbook_path = create_playbook(playbook_content, "test_search_check_mode.yml")
    result = run_playbook(playbook_path)

    print(f"STDOUT:\n{result.stdout}")
    print(f"STDERR:\n{result.stderr}")

    assert (
        result.returncode == 0
    ), f"Playbook failed:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
