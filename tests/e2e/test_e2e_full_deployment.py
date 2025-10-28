#!/usr/bin/env python
"""
End-to-end tests for complete Globus infrastructure deployment.
"""

import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

import pytest


class TestE2EGlobusDeployment:
    """End-to-end tests for full Globus deployment scenarios."""

    @pytest.fixture(scope="class")
    def test_config(self):
        """Configuration for E2E tests."""
        config = {
            "client_id": os.getenv("GLOBUS_CLIENT_ID"),
            "client_secret": os.getenv("GLOBUS_CLIENT_SECRET"),
            "test_scope": "test-ansible-globus",
            "cleanup_delay": 30,  # seconds to wait before cleanup
        }

        # Validate required environment variables
        if not config["client_id"] or not config["client_secret"]:
            pytest.skip(
                "GLOBUS_CLIENT_ID and GLOBUS_CLIENT_SECRET required for E2E tests"
            )

        return config

    @pytest.fixture(scope="class")
    def temp_workspace(self):
        """Create temporary workspace for test artifacts."""
        workspace = tempfile.mkdtemp(prefix="globus-e2e-")
        yield Path(workspace)

        # Cleanup
        import shutil

        shutil.rmtree(workspace)

    def create_test_playbook(self, workspace, playbook_content, name="test.yml"):
        """Create a test playbook file."""
        playbook_path = workspace / name
        with open(playbook_path, "w") as f:
            f.write(playbook_content)
        return str(playbook_path)

    def run_ansible_playbook(self, playbook_path, extra_vars=None, expect_success=True):
        """Run Ansible playbook and return results."""
        cmd = ["ansible-playbook", playbook_path, "-v", "--connection", "local"]

        if extra_vars:
            cmd.extend(["-e", json.dumps(extra_vars)])

        result = subprocess.run(cmd, capture_output=True, text=True)

        if expect_success and result.returncode != 0:
            pytest.fail(
                f"Playbook failed:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
            )

        return result

    def test_complete_research_infrastructure(self, test_config, temp_workspace):
        """Test complete research infrastructure deployment."""

        # Generate unique identifiers for this test run
        import uuid

        test_id = str(uuid.uuid4())[:8]

        playbook_content = f"""
---
- name: E2E Test - Complete Research Infrastructure
  hosts: localhost
  connection: local
  gather_facts: false
  vars:
    test_id: "{test_id}"
    globus_client_id: "{test_config['client_id']}"
    globus_client_secret: "{test_config['client_secret']}"

  tasks:
    # Phase 1: Create Research Group
    - name: Create research group
      globus_group:
        name: "e2e-research-group-{{{{ test_id }}}}"
        description: "E2E test research group"
        visibility: "private"
        auth_method: "client_credentials"
        client_id: "{{{{ globus_client_id }}}}"
        client_secret: "{{{{ globus_client_secret }}}}"
        state: present
      register: research_group

    - name: Verify group creation
      assert:
        that:
          - research_group.changed
          - research_group.group_id is defined

    # Phase 2: Create Endpoint
    - name: Create test endpoint
      globus_endpoint:
        name: "e2e-test-endpoint-{{{{ test_id }}}}"
        description: "E2E test endpoint"
        organization: "Ansible E2E Test"
        contact_email: "test@example.com"
        endpoint_type: "personal"
        public: false
        auth_method: "client_credentials"
        client_id: "{{{{ globus_client_id }}}}"
        client_secret: "{{{{ globus_client_secret }}}}"
        state: present
      register: test_endpoint

    - name: Verify endpoint creation
      assert:
        that:
          - test_endpoint.changed
          - test_endpoint.endpoint_id is defined

    # Phase 3: Create Collections
    - name: Create test collection
      globus_collection:
        name: "e2e-test-collection-{{{{ test_id }}}}"
        endpoint_id: "{{{{ test_endpoint.endpoint_id }}}}"
        path: "/tmp/test-data"
        collection_type: "mapped"
        description: "E2E test collection"
        public: false
        auth_method: "client_credentials"
        client_id: "{{{{ globus_client_id }}}}"
        client_secret: "{{{{ globus_client_secret }}}}"
        state: present
      register: test_collection

    - name: Verify collection creation
      assert:
        that:
          - test_collection.changed
          - test_collection.collection_id is defined

    # Phase 4: Create Compute Endpoint (if supported)
    - name: Create compute endpoint
      globus_compute:
        name: "e2e-compute-{{{{ test_id }}}}"
        description: "E2E test compute endpoint"
        public: false
        executor_type: "ThreadPoolExecutor"
        max_workers: 2
        auth_method: "client_credentials"
        client_id: "{{{{ globus_client_id }}}}"
        client_secret: "{{{{ globus_client_secret }}}}"
        state: present
      register: compute_endpoint
      ignore_errors: true  # Compute may not be available in test environment

    # Phase 5: Create Flow (if compute available)
    - name: Create test flow
      globus_flow:
        title: "e2e-test-flow-{{{{ test_id }}}}"
        description: "E2E test automation flow"
        definition:
          Comment: "Simple test flow"
          StartAt: "TestStep"
          States:
            TestStep:
              Type: "Pass"
              Result: "E2E test completed"
              End: true
        visible_to:
          - "{{{{ research_group.group_id }}}}"
        runnable_by:
          - "{{{{ research_group.group_id }}}}"
        auth_method: "client_credentials"
        client_id: "{{{{ globus_client_id }}}}"
        client_secret: "{{{{ globus_client_secret }}}}"
        state: present
      register: test_flow
      when: compute_endpoint is succeeded

    # Phase 6: Verification
    - name: Display deployment summary
      debug:
        msg: |
          E2E Deployment Summary:
          Group ID: {{{{ research_group.group_id }}}}
          Endpoint ID: {{{{ test_endpoint.endpoint_id }}}}
          Collection ID: {{{{ test_collection.collection_id }}}}
          Compute ID: {{{{ compute_endpoint.endpoint_id | default('N/A') }}}}
          Flow ID: {{{{ test_flow.flow_id | default('N/A') }}}}

    # Phase 7: Cleanup
    - name: Wait before cleanup
      pause:
        seconds: {test_config['cleanup_delay']}

    - name: Delete test flow
      globus_flow:
        title: "e2e-test-flow-{{{{ test_id }}}}"
        auth_method: "client_credentials"
        client_id: "{{{{ globus_client_id }}}}"
        client_secret: "{{{{ globus_client_secret }}}}"
        state: absent
      when: test_flow is defined and test_flow is succeeded
      ignore_errors: true

    - name: Delete test collection
      globus_collection:
        name: "e2e-test-collection-{{{{ test_id }}}}"
        endpoint_id: "{{{{ test_endpoint.endpoint_id }}}}"
        path: "/tmp/test-data"
        auth_method: "client_credentials"
        client_id: "{{{{ globus_client_id }}}}"
        client_secret: "{{{{ globus_client_secret }}}}"
        state: absent
      ignore_errors: true

    - name: Delete test endpoint
      globus_endpoint:
        name: "e2e-test-endpoint-{{{{ test_id }}}}"
        auth_method: "client_credentials"
        client_id: "{{{{ globus_client_id }}}}"
        client_secret: "{{{{ globus_client_secret }}}}"
        state: absent
      ignore_errors: true

    - name: Delete research group
      globus_group:
        name: "e2e-research-group-{{{{ test_id }}}}"
        auth_method: "client_credentials"
        client_id: "{{{{ globus_client_id }}}}"
        client_secret: "{{{{ globus_client_secret }}}}"
        state: absent
      ignore_errors: true

    - name: Delete compute endpoint
      globus_compute:
        name: "e2e-compute-{{{{ test_id }}}}"
        auth_method: "client_credentials"
        client_id: "{{{{ globus_client_id }}}}"
        client_secret: "{{{{ globus_client_secret }}}}"
        state: absent
      when: compute_endpoint is succeeded
      ignore_errors: true
"""

        playbook_path = self.create_test_playbook(
            temp_workspace, playbook_content, "complete_deployment.yml"
        )

        # Run the complete deployment test
        result = self.run_ansible_playbook(playbook_path)

        # Verify successful execution
        assert "PLAY RECAP" in result.stdout
        assert "failed=0" in result.stdout or result.returncode == 0

    def test_idempotency_verification(self, test_config, temp_workspace):
        """Test that operations are truly idempotent."""

        test_id = str(time.time()).replace(".", "")

        playbook_content = f"""
---
- name: E2E Test - Idempotency
  hosts: localhost
  connection: local
  gather_facts: false
  vars:
    test_id: "{test_id}"

  tasks:
    - name: Create group (first time)
      globus_group:
        name: "idempotency-test-{{{{ test_id }}}}"
        description: "Idempotency test group"
        auth_method: "client_credentials"
        client_id: "{test_config['client_id']}"
        client_secret: "{test_config['client_secret']}"
        state: present
      register: first_run

    - name: Create same group (second time)
      globus_group:
        name: "idempotency-test-{{{{ test_id }}}}"
        description: "Idempotency test group"
        auth_method: "client_credentials"
        client_id: "{test_config['client_id']}"
        client_secret: "{test_config['client_secret']}"
        state: present
      register: second_run

    - name: Verify idempotency
      assert:
        that:
          - first_run.changed
          - not second_run.changed
          - first_run.group_id == second_run.group_id

    - name: Cleanup
      globus_group:
        name: "idempotency-test-{{{{ test_id }}}}"
        auth_method: "client_credentials"
        client_id: "{test_config['client_id']}"
        client_secret: "{test_config['client_secret']}"
        state: absent
      ignore_errors: true
"""

        playbook_path = self.create_test_playbook(
            temp_workspace, playbook_content, "idempotency.yml"
        )

        result = self.run_ansible_playbook(playbook_path)
        assert "failed=0" in result.stdout or result.returncode == 0

    def test_error_handling(self, test_config, temp_workspace):
        """Test proper error handling for invalid operations."""

        playbook_content = f"""
---
- name: E2E Test - Error Handling
  hosts: localhost
  connection: local
  gather_facts: false

  tasks:
    - name: Try to create collection without endpoint
      globus_collection:
        name: "invalid-collection"
        endpoint_id: "00000000-0000-0000-0000-000000000000"
        path: "/invalid/path"
        auth_method: "client_credentials"
        client_id: "{test_config['client_id']}"
        client_secret: "{test_config['client_secret']}"
        state: present
      register: invalid_collection
      ignore_errors: true

    - name: Verify error was caught
      assert:
        that:
          - invalid_collection.failed
          - invalid_collection.msg is defined

    - name: Try invalid authentication
      globus_group:
        name: "auth-test"
        auth_method: "client_credentials"
        client_id: "invalid"
        client_secret: "invalid"
        state: present
      register: invalid_auth
      ignore_errors: true

    - name: Verify auth error was caught
      assert:
        that:
          - invalid_auth.failed
          - '"Authentication failed" in invalid_auth.msg or "failed" in invalid_auth.msg'
"""

        playbook_path = self.create_test_playbook(
            temp_workspace, playbook_content, "error_handling.yml"
        )

        result = self.run_ansible_playbook(playbook_path)
        assert "failed=0" in result.stdout or result.returncode == 0

    def test_check_mode(self, test_config, temp_workspace):
        """Test check mode functionality."""

        playbook_content = f"""
---
- name: E2E Test - Check Mode
  hosts: localhost
  connection: local
  gather_facts: false

  tasks:
    - name: Create group in check mode
      globus_group:
        name: "check-mode-test"
        description: "Should not be created"
        auth_method: "client_credentials"
        client_id: "{test_config['client_id']}"
        client_secret: "{test_config['client_secret']}"
        state: present
      check_mode: true
      register: check_result

    - name: Verify check mode behavior
      assert:
        that:
          - check_result.changed
          - check_result.group_id is not defined

    - name: Verify group was not created
      globus_group:
        name: "check-mode-test"
        auth_method: "client_credentials"
        client_id: "{test_config['client_id']}"
        client_secret: "{test_config['client_secret']}"
        state: absent
      register: cleanup

    - name: Verify no cleanup needed
      assert:
        that:
          - not cleanup.changed
"""

        playbook_path = self.create_test_playbook(
            temp_workspace, playbook_content, "check_mode.yml"
        )

        result = self.run_ansible_playbook(playbook_path, extra_vars={"check": True})
        assert result.returncode == 0


@pytest.mark.e2e
class TestE2EPerformance:
    """Performance and load testing for Globus modules."""

    def test_concurrent_operations(self, test_config):
        """Test handling of concurrent operations."""
        # This would test multiple parallel operations
        pytest.skip("Concurrent operations test - implement for load testing")

    def test_large_scale_deployment(self, test_config):
        """Test deployment of many resources."""
        # This would test creating many endpoints/collections/groups
        pytest.skip("Large scale test - implement for stress testing")
