#!/usr/bin/env python
"""
Integration tests for globus_group module.

These tests create, verify, and delete Globus Groups, including
member management functionality.
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


def test_group_create_and_delete(
    ansible_playbook_auth_params,
    create_playbook,
    run_playbook,
    sdk_version,
    auth_method_suffix,
):
    """Test creating and deleting a Globus Group."""
    group_name = f"ansible-test-group-{sdk_version}-{auth_method_suffix}"

    playbook_content = f"""
---
- hosts: localhost
  connection: local
  gather_facts: false
  tasks:
    - name: Delete any existing test group (cleanup from previous runs)
      m1yag1.globus.globus_group:
        name: "{group_name}"
        {ansible_playbook_auth_params}
        state: absent
      register: cleanup_result

    - name: Create test group
      m1yag1.globus.globus_group:
        name: "{group_name}"
        description: "Integration test group for Ansible - {sdk_version}"
        {ansible_playbook_auth_params}
        state: present
      register: create_result

    - name: Verify group was created
      assert:
        that:
          - create_result.changed
          - create_result.group_id is defined
          - create_result.name == "{group_name}"
        fail_msg: "Group creation failed or missing expected fields"

    - name: Test idempotency - create again should not change
      m1yag1.globus.globus_group:
        name: "{group_name}"
        description: "Integration test group for Ansible - {sdk_version}"
        {ansible_playbook_auth_params}
        state: present
      register: idempotent_result

    - name: Verify idempotency
      assert:
        that:
          - not idempotent_result.changed
          - idempotent_result.group_id == create_result.group_id
        fail_msg: "Second create should not have changed anything"

    - name: Delete test group
      m1yag1.globus.globus_group:
        name: "{group_name}"
        {ansible_playbook_auth_params}
        state: absent
      register: delete_result

    - name: Verify group was deleted
      assert:
        that:
          - delete_result.changed
        fail_msg: "Group deletion should have changed state"

    - name: Test delete idempotency - delete again should not change
      m1yag1.globus.globus_group:
        name: "{group_name}"
        {ansible_playbook_auth_params}
        state: absent
      register: delete_idempotent_result

    - name: Verify delete idempotency
      assert:
        that:
          - not delete_idempotent_result.changed
        fail_msg: "Second delete should not have changed anything"
"""

    playbook_path = create_playbook(playbook_content, "test_group.yml")
    result = run_playbook(playbook_path)

    # Print output for debugging
    print(f"STDOUT:\n{result.stdout}")
    print(f"STDERR:\n{result.stderr}")

    assert (
        result.returncode == 0
    ), f"Playbook failed:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"


def test_group_with_members(
    ansible_playbook_auth_params,
    create_playbook,
    run_playbook,
    sdk_version,
    auth_method_suffix,
):
    """Test creating a group with members.

    This test specifically tests the manage_members functionality which
    should add members to the group after creation.
    """
    group_name = f"ansible-test-members-{sdk_version}-{auth_method_suffix}"
    # Use a test identity - for client_credentials, we can add the client itself
    # Note: We use a known test identity that exists in the Globus system
    test_member = "art@globusid.org"

    playbook_content = f"""
---
- hosts: localhost
  connection: local
  gather_facts: false
  tasks:
    - name: Delete any existing test group (cleanup from previous runs)
      m1yag1.globus.globus_group:
        name: "{group_name}"
        {ansible_playbook_auth_params}
        state: absent
      register: cleanup_result

    - name: Create test group with members
      m1yag1.globus.globus_group:
        name: "{group_name}"
        description: "Integration test group with members - {sdk_version}"
        members:
          - "{test_member}"
        {ansible_playbook_auth_params}
        state: present
      register: create_result

    - name: Verify group was created
      assert:
        that:
          - create_result.changed
          - create_result.group_id is defined
          - create_result.name == "{group_name}"
        fail_msg: "Group creation with members failed"

    - name: Cleanup - delete test group
      m1yag1.globus.globus_group:
        name: "{group_name}"
        {ansible_playbook_auth_params}
        state: absent
      register: delete_result
"""

    playbook_path = create_playbook(playbook_content, "test_group_members.yml")
    result = run_playbook(playbook_path)

    # Print output for debugging
    print(f"STDOUT:\n{result.stdout}")
    print(f"STDERR:\n{result.stderr}")

    assert (
        result.returncode == 0
    ), f"Playbook failed:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"


def test_group_member_lifecycle(
    ansible_playbook_auth_params,
    create_playbook,
    run_playbook,
    sdk_version,
    auth_method_suffix,
):
    """Test member lifecycle: add member, add admin, update group.

    This test exercises the member management functionality more thoroughly:
    1. Create group (empty)
    2. Update group to add a member
    3. Update group to add an admin
    4. Update group to add another member
    5. Clean up

    Note: Member removal is not currently supported by the module,
    but could be added in the future.
    """
    group_name = f"ansible-test-lifecycle-{sdk_version}-{auth_method_suffix}"
    test_member1 = "art@globusid.org"
    test_member2 = "m1yag1@globusid.org"

    playbook_content = f"""
---
- hosts: localhost
  connection: local
  gather_facts: false
  tasks:
    - name: Delete any existing test group (cleanup from previous runs)
      m1yag1.globus.globus_group:
        name: "{group_name}"
        {ansible_playbook_auth_params}
        state: absent

    - name: Create empty test group
      m1yag1.globus.globus_group:
        name: "{group_name}"
        description: "Member lifecycle test group - {sdk_version}"
        {ansible_playbook_auth_params}
        state: present
      register: create_result

    - name: Verify group was created
      assert:
        that:
          - create_result.changed
          - create_result.group_id is defined
        fail_msg: "Group creation failed"

    - name: Add a member to the group
      m1yag1.globus.globus_group:
        name: "{group_name}"
        members:
          - "{test_member1}"
        {ansible_playbook_auth_params}
        state: present
      register: add_member_result

    - name: Verify member was added
      assert:
        that:
          - add_member_result.changed
        fail_msg: "Adding member should have changed the group"

    - name: Add member as admin
      m1yag1.globus.globus_group:
        name: "{group_name}"
        admins:
          - "{test_member2}"
        {ansible_playbook_auth_params}
        state: present
      register: add_admin_result

    - name: Verify admin was added
      assert:
        that:
          - add_admin_result.changed
        fail_msg: "Adding admin should have changed the group"

    - name: Add same member again (idempotency test)
      m1yag1.globus.globus_group:
        name: "{group_name}"
        members:
          - "{test_member1}"
        {ansible_playbook_auth_params}
        state: present
      register: idempotent_result

    - name: Verify idempotency - adding same member should not change
      assert:
        that:
          - not idempotent_result.changed
        fail_msg: "Adding same member again should not change anything"

    - name: Cleanup - delete test group
      m1yag1.globus.globus_group:
        name: "{group_name}"
        {ansible_playbook_auth_params}
        state: absent
      register: delete_result

    - name: Verify cleanup
      assert:
        that:
          - delete_result.changed
        fail_msg: "Group deletion should have changed state"
"""

    playbook_path = create_playbook(playbook_content, "test_group_lifecycle.yml")
    result = run_playbook(playbook_path)

    # Print output for debugging
    print(f"STDOUT:\n{result.stdout}")
    print(f"STDERR:\n{result.stderr}")

    assert (
        result.returncode == 0
    ), f"Playbook failed:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
