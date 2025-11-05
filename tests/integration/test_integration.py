#!/usr/bin/env python

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest


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
    """Fixture that returns a function to run ansible-playbook."""

    def _run_playbook(playbook_path, extra_vars=None):
        cmd = ["ansible-playbook", playbook_path, "-v"]

        # Use the current Python interpreter for module execution
        # This ensures globus_sdk and other dependencies are available
        import sys

        python_interpreter = sys.executable
        cmd.extend(["-e", f"ansible_python_interpreter={python_interpreter}"])

        if extra_vars:
            cmd.extend(["-e", json.dumps(extra_vars)])

        # Pass through environment variables
        env = os.environ.copy()

        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        return result

    return _run_playbook


def test_group_management(ansible_playbook_auth_params, create_playbook, run_playbook):
    """Test Globus group creation and deletion."""
    playbook_content = f"""
---
- hosts: localhost
  connection: local
  gather_facts: true
  tasks:
    - name: Create test group
      m1yag1.globus.globus_group:
        name: "ansible-test-group-{{{{ ansible_date_time.epoch }}}}"
        description: "Test group created by Ansible integration test"
        visibility: "private"
        {ansible_playbook_auth_params}
        state: present
      register: group_result

    - name: Verify group was created
      assert:
        that:
          - group_result.changed
          - group_result.group_id is defined
          - group_result.name is defined

    - name: Delete test group
      m1yag1.globus.globus_group:
        name: "{{{{ group_result.name }}}}"
        {ansible_playbook_auth_params}
        state: absent
      register: delete_result

    - name: Verify group was deleted
      assert:
        that:
          - delete_result.changed
"""

    playbook_path = create_playbook(playbook_content)
    result = run_playbook(playbook_path)

    assert result.returncode == 0, f"Playbook failed: {result.stderr}"


@pytest.mark.skip(
    reason="Requires GCS v5 infrastructure (EC2 instance with Globus Connect Server)"
)
def test_endpoint_management(
    ansible_playbook_auth_params_transfer, create_playbook, run_playbook
):
    """Test Globus endpoint operations."""
    playbook_content = f"""
---
- hosts: localhost
  connection: local
  gather_facts: true
  tasks:
    - name: Create test endpoint
      m1yag1.globus.globus_endpoint:
        name: "ansible-test-endpoint-{{{{ ansible_date_time.epoch }}}}"
        description: "Test endpoint created by Ansible integration test"
        organization: "Ansible Test Org"
        endpoint_type: "personal"
        public: false
        {ansible_playbook_auth_params_transfer}
        state: present
      register: endpoint_result

    - name: Verify endpoint was created
      assert:
        that:
          - endpoint_result.changed
          - endpoint_result.endpoint_id is defined
          - endpoint_result.name is defined

    - name: Update endpoint description
      m1yag1.globus.globus_endpoint:
        name: "{{{{ endpoint_result.name }}}}"
        description: "Updated description"
        {ansible_playbook_auth_params_transfer}
        state: present
      register: update_result

    - name: Verify endpoint was updated
      assert:
        that:
          - update_result.changed

    - name: Delete test endpoint
      m1yag1.globus.globus_endpoint:
        name: "{{{{ endpoint_result.name }}}}"
        {ansible_playbook_auth_params_transfer}
        state: absent
      register: delete_result

    - name: Verify endpoint was deleted
      assert:
        that:
          - delete_result.changed
"""

    playbook_path = create_playbook(playbook_content)
    result = run_playbook(playbook_path)

    assert result.returncode == 0, f"Playbook failed: {result.stderr}"


def test_flow_management_with_file(
    ansible_playbook_auth_params_flows,
    test_playbooks_dir,
    create_playbook,
    run_playbook,
):
    """Test Globus flow creation from file."""
    # Create a test flow definition file
    flow_definition = {
        "Comment": "Test flow for Ansible integration",
        "StartAt": "TestState",
        "States": {
            "TestState": {
                "Type": "Pass",
                "Result": {
                    "message": "Hello from Ansible test!"
                },  # Result must be an object
                "End": True,
            }
        },
    }

    flow_file_path = test_playbooks_dir / "test_flow.json"
    with open(flow_file_path, "w") as f:
        json.dump(flow_definition, f, indent=2)

    playbook_content = f"""
---
- hosts: localhost
  connection: local
  gather_facts: true
  tasks:
    - name: Create test flow from file
      m1yag1.globus.globus_flow:
        title: "ansible-test-flow-{{{{ ansible_date_time.epoch }}}}"
        subtitle: "Test flow from file"
        description: "Test flow created by Ansible integration test"
        definition_file: "{flow_file_path}"
        visible_to:
          - "public"
        runnable_by:
          - "all_authenticated_users"
        deploy: true
        {ansible_playbook_auth_params_flows}
        state: present
      register: flow_result

    - name: Verify flow was created
      assert:
        that:
          - flow_result.changed
          - flow_result.flow_id is defined
          - flow_result.title is defined

    - name: Delete test flow
      m1yag1.globus.globus_flow:
        title: "{{{{ flow_result.title }}}}"
        {ansible_playbook_auth_params_flows}
        state: absent
      register: delete_result

    - name: Verify flow was deleted
      assert:
        that:
          - delete_result.changed
"""

    playbook_path = create_playbook(playbook_content)
    result = run_playbook(playbook_path)

    assert result.returncode == 0, f"Playbook failed: {result.stderr}"


def test_timer_management(
    ansible_playbook_auth_params_timers, create_playbook, run_playbook
):
    """Test Globus timer operations."""
    playbook_content = f"""
---
- hosts: localhost
  connection: local
  gather_facts: true
  tasks:
    - name: Create recurring timer
      m1yag1.globus.globus_timer:
        name: "ansible-test-timer-{{{{ ansible_date_time.epoch }}}}"
        schedule:
          type: recurring
          interval_hours: 24
        start: "2025-12-01T00:00:00Z"
        callback_url: "https://actions.globus.org/hello_world"
        callback_body:
          message: "Test timer"
        {ansible_playbook_auth_params_timers}
        state: present
      register: timer_result

    - name: Verify timer was created
      assert:
        that:
          - timer_result.changed
          - timer_result.timer_id is defined
          - timer_result.name is defined
          - timer_result.status in ["active", "loaded"]

    - name: Delete timer
      m1yag1.globus.globus_timer:
        name: "{{{{ timer_result.name }}}}"
        {ansible_playbook_auth_params_timers}
        state: absent
      register: delete_result

    - name: Verify timer was deleted
      assert:
        that:
          - delete_result.changed
"""

    playbook_path = create_playbook(playbook_content)
    result = run_playbook(playbook_path)

    assert result.returncode == 0, f"Playbook failed: {result.stderr}"


def test_flow_timer(
    ansible_playbook_auth_params_flows,
    ansible_playbook_auth_params_timers,
    test_playbooks_dir,
    create_playbook,
    run_playbook,
):
    """Test creating a timer that runs a Globus Flow on a schedule."""
    # Create a test flow definition file
    flow_definition = {
        "Comment": "Test flow triggered by timer",
        "StartAt": "TestState",
        "States": {
            "TestState": {
                "Type": "Pass",
                "Result": {
                    "message": "Flow triggered by timer!",
                    "triggered_at": "$.input.triggered_at",
                },
                "End": True,
            }
        },
    }

    flow_file_path = test_playbooks_dir / "timer_flow.json"
    with open(flow_file_path, "w") as f:
        json.dump(flow_definition, f, indent=2)

    playbook_content = f"""
---
- hosts: localhost
  connection: local
  gather_facts: true
  tasks:
    - name: Create test flow for timer
      m1yag1.globus.globus_flow:
        title: "ansible-timer-flow-{{{{ ansible_date_time.epoch }}}}"
        subtitle: "Flow triggered by timer"
        description: "Test flow for timer integration"
        definition_file: "{flow_file_path}"
        visible_to:
          - "public"
        runnable_by:
          - "all_authenticated_users"
        deploy: true
        {ansible_playbook_auth_params_flows}
        state: present
      register: flow_result

    - name: Verify flow was created
      assert:
        that:
          - flow_result.changed
          - flow_result.flow_id is defined
          - flow_result.flow_scope is defined

    - name: Create timer to run the flow daily
      m1yag1.globus.globus_timer:
        name: "ansible-flow-timer-{{{{ ansible_date_time.epoch }}}}"
        schedule:
          type: recurring
          interval_hours: 24
        start: "2025-12-01T00:00:00Z"
        callback_url: "https://flows.globus.org/flows/{{{{ flow_result.flow_id }}}}/run"
        callback_body:
          body:
            triggered_at: "scheduled-run"
            message: "Timer triggered this flow"
          run_managers:
            - "urn:globus:auth:identity:46bd0f56-e24f-11e5-a510-131bef46955c"
        # Note: scope parameter omitted - timer will use its default authorization
        # For production use, you would need to ensure the timer has proper flow scope
        {ansible_playbook_auth_params_timers}
        state: present
      register: timer_result

    - name: Verify timer was created
      assert:
        that:
          - timer_result.changed
          - timer_result.timer_id is defined
          - timer_result.name is defined

    - name: Debug timer and flow info
      debug:
        msg:
          - "Flow ID: {{{{ flow_result.flow_id }}}}"
          - "Timer ID: {{{{ timer_result.timer_id }}}}"
          - "Timer will run flow every 24 hours starting 2025-12-01"

    - name: Delete timer
      m1yag1.globus.globus_timer:
        name: "{{{{ timer_result.name }}}}"
        {ansible_playbook_auth_params_timers}
        state: absent
      register: timer_delete

    - name: Verify timer was deleted
      assert:
        that:
          - timer_delete.changed

    - name: Delete flow
      m1yag1.globus.globus_flow:
        title: "{{{{ flow_result.title }}}}"
        {ansible_playbook_auth_params_flows}
        state: absent
      register: flow_delete

    - name: Verify flow was deleted
      assert:
        that:
          - flow_delete.changed
"""

    playbook_path = create_playbook(playbook_content)
    result = run_playbook(playbook_path)

    assert result.returncode == 0, f"Playbook failed: {result.stderr}"


def test_idempotency(ansible_playbook_auth_params, create_playbook, run_playbook):
    """Test that modules are idempotent."""
    playbook_content = f"""
---
- hosts: localhost
  connection: local
  gather_facts: true
  tasks:
    - name: Create test group
      m1yag1.globus.globus_group:
        name: "ansible-idempotency-test"
        description: "Test group for idempotency"
        visibility: "private"
        {ansible_playbook_auth_params}
        state: present
      register: first_run

    - name: Create same group again
      m1yag1.globus.globus_group:
        name: "ansible-idempotency-test"
        description: "Test group for idempotency"
        visibility: "private"
        {ansible_playbook_auth_params}
        state: present
      register: second_run

    - name: Verify idempotency
      assert:
        that:
          - first_run.changed
          - not second_run.changed
          - first_run.group_id == second_run.group_id

    - name: Cleanup test group
      m1yag1.globus.globus_group:
        name: "ansible-idempotency-test"
        {ansible_playbook_auth_params}
        state: absent
"""

    playbook_path = create_playbook(playbook_content)
    result = run_playbook(playbook_path)

    assert result.returncode == 0, f"Playbook failed: {result.stderr}"


def test_check_mode(ansible_playbook_auth_params, create_playbook, run_playbook):
    """Test check mode functionality."""
    playbook_content = f"""
---
- hosts: localhost
  connection: local
  gather_facts: true
  tasks:
    - name: Create test group in check mode
      m1yag1.globus.globus_group:
        name: "ansible-check-mode-test"
        description: "This should not be created"
        {ansible_playbook_auth_params}
        state: present
      check_mode: true
      register: check_result

    - name: Verify check mode behavior
      assert:
        that:
          - check_result.changed
          - check_result.group_id is not defined

    - name: Verify group was not actually created
      m1yag1.globus.globus_group:
        name: "ansible-check-mode-test"
        {ansible_playbook_auth_params}
        state: absent
      register: cleanup_result

    - name: Verify no cleanup was needed
      assert:
        that:
          - not cleanup_result.changed
"""

    playbook_path = create_playbook(playbook_content)
    result = run_playbook(playbook_path)

    assert result.returncode == 0, f"Playbook failed: {result.stderr}"


@pytest.mark.high_assurance
def test_auth_project_management(
    ansible_playbook_auth_params_auth, create_playbook, run_playbook
):
    """Test Globus Auth project creation.

    Note: Project creation requires high-assurance authentication (MFA within 30 min)
    which is not available in CI. Run locally with: pytest -m high_assurance
    """
    playbook_content = f"""
---
- hosts: localhost
  connection: local
  gather_facts: true
  tasks:
    - name: Create test project
      m1yag1.globus.globus_auth:
        resource_type: project
        name: "ansible-test-project-{{{{ ansible_date_time.epoch }}}}"
        contact_email: "test@example.com"
        description: "Test project created by Ansible integration test"
        admin_ids:
          - "{{{{ lookup('env', 'GLOBUS_ADMIN_IDS') }}}}"
        {ansible_playbook_auth_params_auth}
        state: present
      register: project_result

    - name: Verify project was created
      assert:
        that:
          - project_result.changed
          - project_result.resource_id is defined
          - project_result.resource_type == "project"
"""

    playbook_path = create_playbook(playbook_content)
    result = run_playbook(playbook_path)

    assert result.returncode == 0, f"Playbook failed: {result.stderr}"


@pytest.mark.high_assurance
def test_auth_client_confidential(
    ansible_playbook_auth_params_auth, create_playbook, run_playbook
):
    """Test creating a confidential OAuth client (service account).

    Note: Client creation requires high-assurance authentication (MFA within 30 min)
    which is not available in CI. Run locally with: pytest -m high_assurance
    """
    playbook_content = f"""
---
- hosts: localhost
  connection: local
  gather_facts: true
  tasks:
    - name: Create or reuse test project
      m1yag1.globus.globus_auth:
        resource_type: project
        name: "ansible-integration-test-project"
        contact_email: "test@example.com"
        description: "Shared project for Ansible integration tests"
        admin_ids:
          - "{{{{ lookup('env', 'GLOBUS_ADMIN_IDS') }}}}"
        {ansible_playbook_auth_params_auth}
        state: present
      register: project_result

    - name: Create confidential client (service account)
      m1yag1.globus.globus_auth:
        resource_type: client
        name: "test-service-account-{{{{ ansible_date_time.epoch }}}}"
        project_id: "{{{{ project_result.resource_id }}}}"
        client_type: confidential_client
        redirect_uris:
          - "https://example.com/callback"
        visibility: private
        {ansible_playbook_auth_params_auth}
        state: present
      register: client_result
      no_log: false  # For debugging, normally should be true

    - name: Verify client was created with credentials
      assert:
        that:
          - client_result.changed
          - client_result.client_id is defined
          - client_result.client_secret is defined
          - client_result.client_credentials is defined
          - client_result.client_credentials.ansible_env is defined
          - client_result.client_credentials.shell_export is defined
          - client_result.warning is defined
"""

    playbook_path = create_playbook(playbook_content)
    result = run_playbook(playbook_path)

    assert result.returncode == 0, f"Playbook failed: {result.stderr}"


@pytest.mark.high_assurance
def test_auth_client_public_installed(
    ansible_playbook_auth_params_auth, create_playbook, run_playbook
):
    """Test creating a public installed client (thick client).

    Note: Client creation requires high-assurance authentication (MFA within 30 min)
    which is not available in CI. Run locally with: pytest -m high_assurance
    """
    playbook_content = f"""
---
- hosts: localhost
  connection: local
  gather_facts: true
  tasks:
    - name: Create or reuse test project
      m1yag1.globus.globus_auth:
        resource_type: project
        name: "ansible-integration-test-project"
        contact_email: "test@example.com"
        description: "Shared project for Ansible integration tests"
        admin_ids:
          - "{{{{ lookup('env', 'GLOBUS_ADMIN_IDS') }}}}"
        {ansible_playbook_auth_params_auth}
        state: present
      register: project_result

    - name: Create public installed client (thick client)
      m1yag1.globus.globus_auth:
        resource_type: client
        name: "test-desktop-app-{{{{ ansible_date_time.epoch }}}}"
        project_id: "{{{{ project_result.resource_id }}}}"
        client_type: public_installed_client
        redirect_uris:
          - "https://auth.globus.org/v2/web/auth-code"
        visibility: public
        {ansible_playbook_auth_params_auth}
        state: present
      register: client_result

    - name: Verify client was created
      assert:
        that:
          - client_result.changed
          - client_result.client_id is defined
          - client_result.resource_type == "client"
"""

    playbook_path = create_playbook(playbook_content)
    result = run_playbook(playbook_path)

    assert result.returncode == 0, f"Playbook failed: {result.stderr}"


@pytest.mark.high_assurance
def test_auth_client_identity(
    ansible_playbook_auth_params_auth, create_playbook, run_playbook
):
    """Test creating a client identity for automation.

    Note: Client creation requires high-assurance authentication (MFA within 30 min)
    which is not available in CI. Run locally with: pytest -m high_assurance
    """
    playbook_content = f"""
---
- hosts: localhost
  connection: local
  gather_facts: true
  tasks:
    - name: Create or reuse test project
      m1yag1.globus.globus_auth:
        resource_type: project
        name: "ansible-integration-test-project"
        contact_email: "test@example.com"
        description: "Shared project for Ansible integration tests"
        admin_ids:
          - "{{{{ lookup('env', 'GLOBUS_ADMIN_IDS') }}}}"
        {ansible_playbook_auth_params_auth}
        state: present
      register: project_result

    - name: Create client identity
      m1yag1.globus.globus_auth:
        resource_type: client
        name: "test-ci-cd-{{{{ ansible_date_time.epoch }}}}"
        project_id: "{{{{ project_result.resource_id }}}}"
        client_type: client_identity
        {ansible_playbook_auth_params_auth}
        state: present
      register: client_result

    - name: Verify client identity was created with credentials
      assert:
        that:
          - client_result.changed
          - client_result.client_id is defined
          - client_result.client_secret is defined
"""

    playbook_path = create_playbook(playbook_content)
    result = run_playbook(playbook_path)

    assert result.returncode == 0, f"Playbook failed: {result.stderr}"


@pytest.mark.high_assurance
def test_auth_client_with_file_output(
    ansible_playbook_auth_params_auth, test_playbooks_dir, create_playbook, run_playbook
):
    """Test creating a client with credential file output.

    Note: Client creation requires high-assurance authentication (MFA within 30 min)
    which is not available in CI. Run locally with: pytest -m high_assurance
    """
    cred_file = test_playbooks_dir / "client-credentials.json"

    playbook_content = f"""
---
- hosts: localhost
  connection: local
  gather_facts: true
  tasks:
    - name: Create or reuse test project
      m1yag1.globus.globus_auth:
        resource_type: project
        name: "ansible-integration-test-project"
        contact_email: "test@example.com"
        description: "Shared project for Ansible integration tests"
        admin_ids:
          - "{{{{ lookup('env', 'GLOBUS_ADMIN_IDS') }}}}"
        {ansible_playbook_auth_params_auth}
        state: present
      register: project_result

    - name: Create client with credential file output
      m1yag1.globus.globus_auth:
        resource_type: client
        name: "test-file-output-{{{{ ansible_date_time.epoch }}}}"
        project_id: "{{{{ project_result.resource_id }}}}"
        client_type: confidential_client
        credential_output_file: "{cred_file}"
        {ansible_playbook_auth_params_auth}
        state: present
      register: client_result

    - name: Verify client was created and file saved
      assert:
        that:
          - client_result.changed
          - client_result.client_id is defined
          - client_result.client_secret is defined
          - client_result.client_credentials.json_file is defined

    - name: Verify credential file exists
      stat:
        path: "{cred_file}"
      register: file_stat

    - name: Check file exists
      assert:
        that:
          - file_stat.stat.exists
"""

    playbook_path = create_playbook(playbook_content)
    result = run_playbook(playbook_path)

    assert result.returncode == 0, f"Playbook failed: {result.stderr}"


# NOTE: Project and OAuth client deletion tests have been removed
# BUG: Service clients cannot delete projects/clients due to high-assurance auth requirement
# This is a known issue in Globus Auth that may be resolved in the future
# TODO: Re-enable deletion tests when auth service is fixed
# For now, users must delete these resources manually at https://app.globus.org/settings/developers


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
