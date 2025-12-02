#!/usr/bin/env python
"""
Integration tests for Globus Connect Server (GCS) modules.

These tests require a running GCS v5.4 instance. Use the test endpoint
deployed via globus-console deployment-ansible-globus.yml configuration.

Dynamic Discovery:
    The tests automatically discover the GCS test instance via AWS EC2 API
    using boto3 with your AWS credentials (OIDC or environment variables).
    This eliminates the need for hardcoded IP addresses.

    The test instance is discovered by name tag: "ansible-test-gcs-01"

To run these tests:
    # With AWS credentials (recommended - uses dynamic discovery)
    export GLOBUS_SDK_ENVIRONMENT=test
    export GLOBUS_CLIENT_ID=e6cda9e4-3139-40b5-9b3b-e48527013bdf
    export GLOBUS_CLIENT_SECRET=<from ~/.gcs/credentials/globus_test.json>
    export AWS_REGION=us-east-1

    cd ansible-globus
    tox -e integration -- -m gcs -v

    # Or with hardcoded IP (fallback for local testing)
    export TEST_GCS_HOST=<instance-ip>
    export TEST_GCS_SSH_USER=ubuntu

Environment Variables:
    - GLOBUS_CLIENT_ID: Client ID for test environment
    - GLOBUS_CLIENT_SECRET: Client secret for authentication
    - GLOBUS_SDK_ENVIRONMENT: Globus environment (test/production)
    - AWS_REGION: AWS region for instance discovery (default: us-east-1)
    - TEST_GCS_INSTANCE_NAME: Instance name to discover (default: ansible-test-gcs-01)
    - TEST_GCS_HOST: (Optional) Hardcoded IP address as fallback
    - TEST_GCS_SSH_USER: (Optional) SSH user (default: ubuntu)

Test Strategy:
    1. Setup GCS endpoint using globus_gcs module (resource_type: endpoint)
    2. Create storage gateway (resource_type: storage_gateway)
    3. Create collection (resource_type: collection)
    4. Manage roles (resource_type: role)
    5. Each test cleans up its own resources
"""

import os

import pytest

# Marker for GCS tests - requires deployed GCS infrastructure
pytestmark = pytest.mark.gcs


@pytest.fixture(scope="module")
def gcs_host(aws_gcs_instance_discovery):
    """
    Get GCS test host dynamically or from environment.

    First attempts to discover the test instance via AWS EC2 API
    (works with OIDC credentials), then falls back to TEST_GCS_HOST
    environment variable.

    Returns IP address or hostname of test GCS instance.
    """
    # Try dynamic discovery first
    instance_name = os.getenv("TEST_GCS_INSTANCE_NAME", "ansible-test-gcs-01")
    instance_info = aws_gcs_instance_discovery(instance_name)

    if instance_info and instance_info.get("public_ip"):
        print(
            f"✓ Discovered GCS instance: {instance_name} at {instance_info['public_ip']}"
        )
        return instance_info["public_ip"]

    # Fallback to environment variable
    host = os.getenv("TEST_GCS_HOST")
    if host:
        print(f"Using TEST_GCS_HOST: {host}")
        return host

    # No host found
    pytest.skip(
        "Could not discover GCS instance via AWS and TEST_GCS_HOST not set. "
        "Either set TEST_GCS_HOST or ensure AWS credentials are available."
    )


@pytest.fixture(scope="module")
def gcs_ssh_user():
    """Get SSH user for GCS test instance."""
    return os.getenv("TEST_GCS_SSH_USER", "ubuntu")


@pytest.fixture(scope="module")
def gcs_project_id():
    """Get Globus project ID for GCS endpoint."""
    project_id = os.getenv(
        "TEST_GCS_PROJECT_ID", "3551d9a3-2f77-454d-be7e-6dfdac20e76c"
    )
    return project_id


@pytest.fixture(scope="module")
def gcs_subscription_id():
    """Get GCS subscription ID."""
    subscription_id = os.getenv(
        "TEST_GCS_SUBSCRIPTION_ID", "923ac990-9914-11ed-af9f-c53a64a5b6b4"
    )
    return subscription_id


def test_gcs_endpoint_setup(
    gcs_host,
    gcs_project_id,
    gcs_subscription_id,
    create_playbook,
    run_playbook,
):
    """
    Test GCS endpoint setup.

    This test sets up a GCS endpoint using the globus_gcs module.
    Requires GCS_CLI_CLIENT_ID and GCS_CLI_CLIENT_SECRET environment variables.
    """
    # Get client credentials from environment
    client_id = os.getenv("GLOBUS_CLIENT_ID")
    client_secret = os.getenv("GLOBUS_CLIENT_SECRET")
    sdk_env = os.getenv("GLOBUS_SDK_ENVIRONMENT", "production")

    playbook_content = f"""
---
- hosts: {gcs_host}
  remote_user: ubuntu
  become: false
  gather_facts: true
  tasks:
    - name: Setup GCS endpoint
      m1yag1.globus.globus_gcs:
        resource_type: endpoint
        display_name: "Ansible Test GCS Endpoint"
        organization: "Test Organization"
        department: "Engineering"
        description: "Test endpoint for ansible-globus GCS module integration tests"
        contact_email: "test@example.com"
        project_id: "{gcs_project_id}"
        subscription_id: "{gcs_subscription_id}"
        state: present
      environment:
        GLOBUS_SDK_ENVIRONMENT: "{sdk_env}"
        GCS_CLI_CLIENT_ID: "{client_id}"
        GCS_CLI_CLIENT_SECRET: "{client_secret}"
      register: endpoint_result

    - name: Verify endpoint was created
      assert:
        that:
          - endpoint_result.changed
          - endpoint_result.endpoint_id is defined
          - endpoint_result.endpoint_domain is defined

    - name: Save endpoint info for other tests
      set_fact:
        test_endpoint_id: "{{{{ endpoint_result.endpoint_id }}}}"
        test_endpoint_domain: "{{{{ endpoint_result.endpoint_domain }}}}"

    - name: Display endpoint details
      debug:
        msg:
          - "Endpoint ID: {{{{ endpoint_result.endpoint_id }}}}"
          - "Endpoint Domain: {{{{ endpoint_result.endpoint_domain }}}}"
"""

    playbook_path = create_playbook(playbook_content, "test_gcs_endpoint.yml")
    result = run_playbook(playbook_path)

    assert result.returncode == 0, f"Playbook failed: {result.stderr}"


@pytest.mark.slow
@pytest.mark.gcs
def test_gcs_node_setup(
    gcs_host,
    create_playbook,
    run_playbook,
):
    """
    Test GCS node setup.

    This test sets up a GCS node which configures GridFTP, Apache, and certificates.
    Marked as slow because it takes several minutes and requires sudo.
    Requires an endpoint to already be configured.
    """
    client_id = os.getenv("GLOBUS_CLIENT_ID")
    client_secret = os.getenv("GLOBUS_CLIENT_SECRET")
    sdk_env = os.getenv("GLOBUS_SDK_ENVIRONMENT", "production")

    playbook_content = f"""
---
- hosts: {gcs_host}
  remote_user: ubuntu
  become: true
  gather_facts: true
  tasks:
    - name: Setup GCS node
      m1yag1.globus.globus_gcs:
        resource_type: node
        state: present
      environment:
        GLOBUS_SDK_ENVIRONMENT: "{sdk_env}"
        GCS_CLI_CLIENT_ID: "{client_id}"
        GCS_CLI_CLIENT_SECRET: "{client_secret}"
      register: node_result

    - name: Verify node was configured
      assert:
        that:
          - node_result.changed or node_result.msg == "Node already configured"

    - name: Display node setup result
      debug:
        msg: "Node setup: {{{{ node_result.msg }}}}"
"""

    playbook_path = create_playbook(playbook_content, "test_gcs_node.yml")
    result = run_playbook(playbook_path)

    assert result.returncode == 0, f"Playbook failed: {result.stderr}"


def test_gcs_storage_gateway_create(
    gcs_host,
    create_playbook,
    run_playbook,
):
    """
    Test creating a POSIX storage gateway.

    This test creates a storage gateway on the GCS endpoint using the
    globus_gcs_storage_gateway module.
    """
    client_id = os.getenv("GLOBUS_CLIENT_ID")
    client_secret = os.getenv("GLOBUS_CLIENT_SECRET")
    sdk_env = os.getenv("GLOBUS_SDK_ENVIRONMENT", "production")

    playbook_content = f"""
---
- hosts: {gcs_host}
  remote_user: ubuntu
  become: true
  gather_facts: true
  tasks:
    # Cleanup any existing gateway from previous runs
    - name: Delete existing test storage gateway
      m1yag1.globus.globus_gcs:
        resource_type: storage_gateway
        display_name: "Test POSIX Gateway"
        state: absent
      environment:
        GLOBUS_SDK_ENVIRONMENT: "{sdk_env}"
        GCS_CLI_CLIENT_ID: "{client_id}"
        GCS_CLI_CLIENT_SECRET: "{client_secret}"
      ignore_errors: true

    - name: Create test data directory
      file:
        path: /test-data
        state: directory
        mode: '0755'
        owner: root
        group: root

    - name: Create identity mapping file
      copy:
        content: |
          {{
            "DATA_TYPE": "expression_identity_mapping#1.0.0",
            "mappings": [
              {{
                "source": "{{username}}",
                "match": "art",
                "output": "ubuntu",
                "literal": true
              }},
              {{
                "source": "{{id}}",
                "match": "{client_id}",
                "output": "ubuntu",
                "literal": true
              }},
              {{
                "source": "{{username}}",
                "match": "(.*)",
                "output": "{{0}}"
              }}
            ]
          }}
        dest: /tmp/identity-mapping.json

    - name: Create POSIX storage gateway
      m1yag1.globus.globus_gcs:
        resource_type: storage_gateway
        display_name: "Test POSIX Gateway"
        storage_type: posix
        identity_mapping: /tmp/identity-mapping.json
        state: present
      environment:
        GLOBUS_SDK_ENVIRONMENT: "{sdk_env}"
        GCS_CLI_CLIENT_ID: "{client_id}"
        GCS_CLI_CLIENT_SECRET: "{client_secret}"
      register: gateway_result

    - name: Verify storage gateway was created
      assert:
        that:
          - gateway_result.changed
          - gateway_result.storage_gateway_id is defined
          - gateway_result.display_name == "Test POSIX Gateway"
          - gateway_result.storage_type is defined

    - name: Display gateway details
      debug:
        msg:
          - "Gateway ID: {{{{ gateway_result.storage_gateway_id }}}}"
          - "Display Name: {{{{ gateway_result.display_name }}}}"

    # Cleanup
    - name: Delete test storage gateway
      m1yag1.globus.globus_gcs:
        resource_type: storage_gateway
        display_name: "Test POSIX Gateway"
        state: absent
      environment:
        GLOBUS_SDK_ENVIRONMENT: "{sdk_env}"
        GCS_CLI_CLIENT_ID: "{client_id}"
        GCS_CLI_CLIENT_SECRET: "{client_secret}"
"""

    playbook_path = create_playbook(playbook_content, "test_storage_gateway.yml")
    result = run_playbook(playbook_path)

    assert result.returncode == 0, f"Playbook failed: {result.stderr}"


def test_gcs_storage_gateway_idempotency(
    gcs_host,
    create_playbook,
    run_playbook,
):
    """
    Test storage gateway idempotency.

    Creating the same gateway twice should not change anything.
    """
    client_id = os.getenv("GLOBUS_CLIENT_ID")
    client_secret = os.getenv("GLOBUS_CLIENT_SECRET")
    sdk_env = os.getenv("GLOBUS_SDK_ENVIRONMENT", "production")

    playbook_content = f"""
---
- hosts: {gcs_host}
  remote_user: ubuntu
  become: true
  gather_facts: true
  tasks:
    - name: Create identity mapping file
      copy:
        content: |
          {{
            "DATA_TYPE": "expression_identity_mapping#1.0.0",
            "mappings": [
              {{
                "source": "{{username}}",
                "match": "art",
                "output": "ubuntu",
                "literal": true
              }},
              {{
                "source": "{{username}}",
                "match": "(.*)",
                "output": "{{0}}"
              }}
            ]
          }}
        dest: /tmp/identity-mapping-idem.json

    - name: Create POSIX storage gateway (first time)
      m1yag1.globus.globus_gcs:
        resource_type: storage_gateway
        display_name: "Test Idempotent Gateway"
        storage_type: posix
        identity_mapping: /tmp/identity-mapping-idem.json
        state: present
      environment:
        GLOBUS_SDK_ENVIRONMENT: "{sdk_env}"
        GCS_CLI_CLIENT_ID: "{client_id}"
        GCS_CLI_CLIENT_SECRET: "{client_secret}"
      register: first_run

    - name: Create same storage gateway (second time)
      m1yag1.globus.globus_gcs:
        resource_type: storage_gateway
        display_name: "Test Idempotent Gateway"
        storage_type: posix
        identity_mapping: /tmp/identity-mapping-idem.json
        state: present
      environment:
        GLOBUS_SDK_ENVIRONMENT: "{sdk_env}"
        GCS_CLI_CLIENT_ID: "{client_id}"
        GCS_CLI_CLIENT_SECRET: "{client_secret}"
      register: second_run

    - name: Verify idempotency
      assert:
        that:
          - first_run.changed
          - not second_run.changed
          - first_run.storage_gateway_id == second_run.storage_gateway_id

    # Cleanup
    - name: Delete test storage gateway
      m1yag1.globus.globus_gcs:
        resource_type: storage_gateway
        display_name: "Test Idempotent Gateway"
        state: absent
      environment:
        GLOBUS_SDK_ENVIRONMENT: "{sdk_env}"
        GCS_CLI_CLIENT_ID: "{client_id}"
        GCS_CLI_CLIENT_SECRET: "{client_secret}"
"""

    playbook_path = create_playbook(playbook_content, "test_gateway_idempotency.yml")
    result = run_playbook(playbook_path)

    assert result.returncode == 0, f"Playbook failed: {result.stderr}"


def test_gcs_collection_create(
    gcs_host,
    create_playbook,
    run_playbook,
):
    """
    Test creating a mapped collection on a storage gateway.

    This test creates a collection using the globus_gcs_collection module.
    """
    client_id = os.getenv("GLOBUS_CLIENT_ID")
    client_secret = os.getenv("GLOBUS_CLIENT_SECRET")
    sdk_env = os.getenv("GLOBUS_SDK_ENVIRONMENT", "production")

    playbook_content = f"""
---
- hosts: {gcs_host}
  remote_user: ubuntu
  become: true
  gather_facts: true
  tasks:
    - name: Create identity mapping file
      copy:
        content: |
          {{
            "DATA_TYPE": "expression_identity_mapping#1.0.0",
            "mappings": [
              {{
                "source": "{{username}}",
                "match": "art",
                "output": "ubuntu",
                "literal": true
              }},
              {{
                "source": "{{username}}",
                "match": "(.*)",
                "output": "{{0}}"
              }}
            ]
          }}
        dest: /tmp/identity-mapping-collection.json

    - name: Create storage gateway for collection
      m1yag1.globus.globus_gcs:
        resource_type: storage_gateway
        display_name: "Gateway for Collection Test"
        storage_type: posix
        identity_mapping: /tmp/identity-mapping-collection.json
        state: present
      environment:
        GLOBUS_SDK_ENVIRONMENT: "{sdk_env}"
        GCS_CLI_CLIENT_ID: "{client_id}"
        GCS_CLI_CLIENT_SECRET: "{client_secret}"
      register: gateway_result

    - name: Create mapped collection
      m1yag1.globus.globus_gcs:
        resource_type: collection
        display_name: "Test Collection"
        storage_gateway_id: "{{{{ gateway_result.storage_gateway_id }}}}"
        collection_base_path: "/"
        description: "Test collection for integration tests"
        public: false
        delete_protection: false
        state: present
      environment:
        GLOBUS_SDK_ENVIRONMENT: "{sdk_env}"
        GCS_CLI_CLIENT_ID: "{client_id}"
        GCS_CLI_CLIENT_SECRET: "{client_secret}"
      register: collection_result

    - name: Verify collection was created
      assert:
        that:
          - collection_result.changed
          - collection_result.collection_id is defined
          - collection_result.display_name == "Test Collection"

    - name: Display collection details
      debug:
        msg:
          - "Collection ID: {{{{ collection_result.collection_id }}}}"
          - "Display Name: {{{{ collection_result.display_name }}}}"

    # Cleanup
    - name: Delete test collection
      m1yag1.globus.globus_gcs:
        resource_type: collection
        display_name: "Test Collection"
        state: absent
      environment:
        GLOBUS_SDK_ENVIRONMENT: "{sdk_env}"
        GCS_CLI_CLIENT_ID: "{client_id}"
        GCS_CLI_CLIENT_SECRET: "{client_secret}"

    - name: Delete test storage gateway
      m1yag1.globus.globus_gcs:
        resource_type: storage_gateway
        display_name: "Gateway for Collection Test"
        state: absent
      environment:
        GLOBUS_SDK_ENVIRONMENT: "{sdk_env}"
        GCS_CLI_CLIENT_ID: "{client_id}"
        GCS_CLI_CLIENT_SECRET: "{client_secret}"
"""

    playbook_path = create_playbook(playbook_content, "test_collection.yml")
    result = run_playbook(playbook_path)

    assert result.returncode == 0, f"Playbook failed: {result.stderr}"


def test_gcs_collection_update(
    gcs_host,
    create_playbook,
    run_playbook,
):
    """
    Test updating a collection's metadata.
    """
    client_id = os.getenv("GLOBUS_CLIENT_ID")
    client_secret = os.getenv("GLOBUS_CLIENT_SECRET")
    sdk_env = os.getenv("GLOBUS_SDK_ENVIRONMENT", "production")

    playbook_content = f"""
---
- hosts: {gcs_host}
  remote_user: ubuntu
  become: true
  gather_facts: true
  tasks:
    - name: Create identity mapping file
      copy:
        content: |
          {{
            "DATA_TYPE": "expression_identity_mapping#1.0.0",
            "mappings": [
              {{
                "source": "{{username}}",
                "match": "art",
                "output": "ubuntu",
                "literal": true
              }},
              {{
                "source": "{{username}}",
                "match": "(.*)",
                "output": "{{0}}"
              }}
            ]
          }}
        dest: /tmp/identity-mapping-collection-update.json

    - name: Create storage gateway
      m1yag1.globus.globus_gcs:
        resource_type: storage_gateway
        display_name: "Gateway for Update Test"
        storage_type: posix
        identity_mapping: /tmp/identity-mapping-collection-update.json
        state: present
      environment:
        GLOBUS_SDK_ENVIRONMENT: "{sdk_env}"
        GCS_CLI_CLIENT_ID: "{client_id}"
        GCS_CLI_CLIENT_SECRET: "{client_secret}"
      register: gateway_result

    - name: Create collection
      m1yag1.globus.globus_gcs:
        resource_type: collection
        display_name: "Collection to Update"
        storage_gateway_id: "{{{{ gateway_result.storage_gateway_id }}}}"
        collection_base_path: "/"
        description: "Original description"
        delete_protection: false
        state: present
      environment:
        GLOBUS_SDK_ENVIRONMENT: "{sdk_env}"
        GCS_CLI_CLIENT_ID: "{client_id}"
        GCS_CLI_CLIENT_SECRET: "{client_secret}"
      register: create_result

    - name: Update collection description
      m1yag1.globus.globus_gcs:
        resource_type: collection
        collection_id: "{{{{ create_result.collection_id }}}}"
        display_name: "Collection to Update"
        storage_gateway_id: "{{{{ gateway_result.storage_gateway_id }}}}"
        collection_base_path: "/"
        description: "Updated description"
        state: present
      environment:
        GLOBUS_SDK_ENVIRONMENT: "{sdk_env}"
        GCS_CLI_CLIENT_ID: "{client_id}"
        GCS_CLI_CLIENT_SECRET: "{client_secret}"
      register: update_result

    - name: Verify collection was updated
      assert:
        that:
          - update_result.changed
          - update_result.collection_id == create_result.collection_id
          - update_result.description == "Updated description"

    # Cleanup
    - name: Delete test collection
      m1yag1.globus.globus_gcs:
        resource_type: collection
        display_name: "Collection to Update"
        state: absent
      environment:
        GLOBUS_SDK_ENVIRONMENT: "{sdk_env}"
        GCS_CLI_CLIENT_ID: "{client_id}"
        GCS_CLI_CLIENT_SECRET: "{client_secret}"

    - name: Delete test storage gateway
      m1yag1.globus.globus_gcs:
        resource_type: storage_gateway
        display_name: "Gateway for Update Test"
        state: absent
      environment:
        GLOBUS_SDK_ENVIRONMENT: "{sdk_env}"
        GCS_CLI_CLIENT_ID: "{client_id}"
        GCS_CLI_CLIENT_SECRET: "{client_secret}"
"""

    playbook_path = create_playbook(playbook_content, "test_collection_update.yml")
    result = run_playbook(playbook_path)

    assert result.returncode == 0, f"Playbook failed: {result.stderr}"


def test_gcs_role_assignment(
    gcs_host,
    create_playbook,
    run_playbook,
):
    """
    Test assigning a role to a user on a collection.

    This test creates a collection and assigns an administrator role to art@globusid.org.
    """
    client_id = os.getenv("GLOBUS_CLIENT_ID")
    client_secret = os.getenv("GLOBUS_CLIENT_SECRET")
    sdk_env = os.getenv("GLOBUS_SDK_ENVIRONMENT", "production")

    playbook_content = f"""
---
- hosts: {gcs_host}
  remote_user: ubuntu
  become: true
  gather_facts: true
  tasks:
    - name: Create identity mapping file
      copy:
        content: |
          {{
            "DATA_TYPE": "expression_identity_mapping#1.0.0",
            "mappings": [
              {{
                "source": "{{username}}",
                "match": "art",
                "output": "ubuntu",
                "literal": true
              }},
              {{
                "source": "{{username}}",
                "match": "(.*)",
                "output": "{{0}}"
              }}
            ]
          }}
        dest: /tmp/identity-mapping-roles.json

    - name: Create storage gateway
      m1yag1.globus.globus_gcs:
        resource_type: storage_gateway
        display_name: "Gateway for Role Test"
        storage_type: posix
        identity_mapping: /tmp/identity-mapping-roles.json
        state: present
      environment:
        GLOBUS_SDK_ENVIRONMENT: "{sdk_env}"
        GCS_CLI_CLIENT_ID: "{client_id}"
        GCS_CLI_CLIENT_SECRET: "{client_secret}"
      register: gateway_result

    - name: Create collection
      m1yag1.globus.globus_gcs:
        resource_type: collection
        display_name: "Collection for Role Test"
        storage_gateway_id: "{{{{ gateway_result.storage_gateway_id }}}}"
        collection_base_path: "/"
        delete_protection: false
        state: present
      environment:
        GLOBUS_SDK_ENVIRONMENT: "{sdk_env}"
        GCS_CLI_CLIENT_ID: "{client_id}"
        GCS_CLI_CLIENT_SECRET: "{client_secret}"
      register: collection_result

    - name: Assign administrator role
      m1yag1.globus.globus_gcs:
        resource_type: role
        collection_id: "{{{{ collection_result.collection_id }}}}"
        principal: "art@globusid.org"
        role: administrator
        state: present
      environment:
        GLOBUS_SDK_ENVIRONMENT: "{sdk_env}"
        GCS_CLI_CLIENT_ID: "{client_id}"
        GCS_CLI_CLIENT_SECRET: "{client_secret}"
      register: role_result

    - name: Verify role was assigned
      assert:
        that:
          - role_result.changed
          - role_result.role == "administrator"

    - name: Display role details
      debug:
        msg:
          - "Role: {{{{ role_result.role }}}}"
          - "Principal: {{{{ role_result.principal }}}}"

    # Cleanup
    - name: Delete test collection
      m1yag1.globus.globus_gcs:
        resource_type: collection
        display_name: "Collection for Role Test"
        state: absent
      environment:
        GLOBUS_SDK_ENVIRONMENT: "{sdk_env}"
        GCS_CLI_CLIENT_ID: "{client_id}"
        GCS_CLI_CLIENT_SECRET: "{client_secret}"

    - name: Delete test storage gateway
      m1yag1.globus.globus_gcs:
        resource_type: storage_gateway
        display_name: "Gateway for Role Test"
        state: absent
      environment:
        GLOBUS_SDK_ENVIRONMENT: "{sdk_env}"
        GCS_CLI_CLIENT_ID: "{client_id}"
        GCS_CLI_CLIENT_SECRET: "{client_secret}"
"""

    playbook_path = create_playbook(playbook_content, "test_roles.yml")
    result = run_playbook(playbook_path)

    assert result.returncode == 0, f"Playbook failed: {result.stderr}"


def test_gcs_role_idempotency(
    gcs_host,
    create_playbook,
    run_playbook,
):
    """
    Test role assignment idempotency.

    Assigning the same role twice should not change anything.
    Uses art@globusid.org for role assignments.
    """
    client_id = os.getenv("GLOBUS_CLIENT_ID")
    client_secret = os.getenv("GLOBUS_CLIENT_SECRET")
    sdk_env = os.getenv("GLOBUS_SDK_ENVIRONMENT", "production")

    playbook_content = f"""
---
- hosts: {gcs_host}
  remote_user: ubuntu
  become: true
  gather_facts: true
  tasks:
    - name: Create identity mapping file
      copy:
        content: |
          {{
            "DATA_TYPE": "expression_identity_mapping#1.0.0",
            "mappings": [
              {{
                "source": "{{username}}",
                "match": "art",
                "output": "ubuntu",
                "literal": true
              }},
              {{
                "source": "{{username}}",
                "match": "(.*)",
                "output": "{{0}}"
              }}
            ]
          }}
        dest: /tmp/identity-mapping-roles-idem.json

    - name: Create storage gateway
      m1yag1.globus.globus_gcs:
        resource_type: storage_gateway
        display_name: "Gateway for Role Idempotency Test"
        storage_type: posix
        identity_mapping: /tmp/identity-mapping-roles-idem.json
        state: present
      environment:
        GLOBUS_SDK_ENVIRONMENT: "{sdk_env}"
        GCS_CLI_CLIENT_ID: "{client_id}"
        GCS_CLI_CLIENT_SECRET: "{client_secret}"
      register: gateway_result

    - name: Create collection
      m1yag1.globus.globus_gcs:
        resource_type: collection
        display_name: "Collection for Role Idempotency"
        storage_gateway_id: "{{{{ gateway_result.storage_gateway_id }}}}"
        collection_base_path: "/"
        delete_protection: false
        state: present
      environment:
        GLOBUS_SDK_ENVIRONMENT: "{sdk_env}"
        GCS_CLI_CLIENT_ID: "{client_id}"
        GCS_CLI_CLIENT_SECRET: "{client_secret}"
      register: collection_result

    - name: Assign administrator role (first time)
      m1yag1.globus.globus_gcs:
        resource_type: role
        collection_id: "{{{{ collection_result.collection_id }}}}"
        principal: "mike.a@globus.org"
        role: administrator
        state: present
      environment:
        GLOBUS_SDK_ENVIRONMENT: "{sdk_env}"
        GCS_CLI_CLIENT_ID: "{client_id}"
        GCS_CLI_CLIENT_SECRET: "{client_secret}"
      register: first_run

    - name: Assign same role (second time)
      m1yag1.globus.globus_gcs:
        resource_type: role
        collection_id: "{{{{ collection_result.collection_id }}}}"
        principal: "mike.a@globus.org"
        role: administrator
        state: present
      environment:
        GLOBUS_SDK_ENVIRONMENT: "{sdk_env}"
        GCS_CLI_CLIENT_ID: "{client_id}"
        GCS_CLI_CLIENT_SECRET: "{client_secret}"
      register: second_run

    - name: Verify idempotency
      assert:
        that:
          - first_run.changed
          - not second_run.changed

    # Cleanup
    - name: Delete test collection
      m1yag1.globus.globus_gcs:
        resource_type: collection
        display_name: "Collection for Role Idempotency"
        state: absent
      environment:
        GLOBUS_SDK_ENVIRONMENT: "{sdk_env}"
        GCS_CLI_CLIENT_ID: "{client_id}"
        GCS_CLI_CLIENT_SECRET: "{client_secret}"

    - name: Delete test storage gateway
      m1yag1.globus.globus_gcs:
        resource_type: storage_gateway
        display_name: "Gateway for Role Idempotency Test"
        state: absent
      environment:
        GLOBUS_SDK_ENVIRONMENT: "{sdk_env}"
        GCS_CLI_CLIENT_ID: "{client_id}"
        GCS_CLI_CLIENT_SECRET: "{client_secret}"
"""

    playbook_path = create_playbook(playbook_content, "test_role_idempotency.yml")
    result = run_playbook(playbook_path)

    assert result.returncode == 0, f"Playbook failed: {result.stderr}"


def test_gcs_ha_storage_gateway_and_collection(
    gcs_host,
    create_playbook,
    run_playbook,
):
    """
    Test creating HA storage gateway and collection.

    This test creates a high assurance storage gateway with authentication
    timeout and a collection that requires high assurance for transfers.
    Uses the HA subscription ID which is already configured for HA support.
    """
    client_id = os.getenv("GLOBUS_CLIENT_ID")
    client_secret = os.getenv("GLOBUS_CLIENT_SECRET")
    sdk_env = os.getenv("GLOBUS_SDK_ENVIRONMENT", "production")

    playbook_content = f"""
---
- hosts: {gcs_host}
  remote_user: ubuntu
  become: true
  gather_facts: true
  tasks:
    # Cleanup any existing HA gateway and collection from previous runs
    - name: Delete existing HA test collection
      m1yag1.globus.globus_gcs:
        resource_type: collection
        display_name: "HA Test Collection"
        state: absent
      environment:
        GLOBUS_SDK_ENVIRONMENT: "{sdk_env}"
        GCS_CLI_CLIENT_ID: "{client_id}"
        GCS_CLI_CLIENT_SECRET: "{client_secret}"
      ignore_errors: true

    - name: Delete existing HA test storage gateway
      m1yag1.globus.globus_gcs:
        resource_type: storage_gateway
        display_name: "HA Test Gateway"
        state: absent
      environment:
        GLOBUS_SDK_ENVIRONMENT: "{sdk_env}"
        GCS_CLI_CLIENT_ID: "{client_id}"
        GCS_CLI_CLIENT_SECRET: "{client_secret}"
      ignore_errors: true

    - name: Create identity mapping file for HA gateway
      copy:
        content: |
          {{
            "DATA_TYPE": "expression_identity_mapping#1.0.0",
            "mappings": [
              {{
                "source": "{{username}}",
                "match": "art",
                "output": "ubuntu",
                "literal": true
              }},
              {{
                "source": "{{id}}",
                "match": "{client_id}",
                "output": "ubuntu",
                "literal": true
              }},
              {{
                "source": "{{username}}",
                "match": "(.*)",
                "output": "{{0}}"
              }}
            ]
          }}
        dest: /tmp/ha-identity-mapping.json

    - name: Create HA storage gateway
      m1yag1.globus.globus_gcs:
        resource_type: storage_gateway
        display_name: "HA Test Gateway"
        storage_type: posix
        identity_mapping: /tmp/ha-identity-mapping.json
        high_assurance: true
        authentication_timeout_mins: 3
        require_mfa: false
        state: present
      environment:
        GLOBUS_SDK_ENVIRONMENT: "{sdk_env}"
        GCS_CLI_CLIENT_ID: "{client_id}"
        GCS_CLI_CLIENT_SECRET: "{client_secret}"
      register: ha_gateway_result

    - name: Verify HA storage gateway was created
      assert:
        that:
          - ha_gateway_result.changed
          - ha_gateway_result.storage_gateway_id is defined
          - ha_gateway_result.display_name == "HA Test Gateway"

    - name: Display HA gateway details
      debug:
        msg:
          - "HA Gateway ID: {{{{ ha_gateway_result.storage_gateway_id }}}}"
          - "Display Name: {{{{ ha_gateway_result.display_name }}}}"

    - name: Create HA collection
      m1yag1.globus.globus_gcs:
        resource_type: collection
        display_name: "HA Test Collection"
        storage_gateway_id: "{{{{ ha_gateway_result.storage_gateway_id }}}}"
        collection_base_path: "/"
        description: "High assurance collection for testing HA transfers"
        public: false
        delete_protection: false
        require_high_assurance: true
        state: present
      environment:
        GLOBUS_SDK_ENVIRONMENT: "{sdk_env}"
        GCS_CLI_CLIENT_ID: "{client_id}"
        GCS_CLI_CLIENT_SECRET: "{client_secret}"
      register: ha_collection_result

    - name: Verify HA collection was created
      assert:
        that:
          - ha_collection_result.changed
          - ha_collection_result.collection_id is defined
          - ha_collection_result.display_name == "HA Test Collection"

    - name: Display HA collection details
      debug:
        msg:
          - "HA Collection ID: {{{{ ha_collection_result.collection_id }}}}"
          - "Display Name: {{{{ ha_collection_result.display_name }}}}"

    # Cleanup
    - name: Delete HA test collection
      m1yag1.globus.globus_gcs:
        resource_type: collection
        display_name: "HA Test Collection"
        state: absent
      environment:
        GLOBUS_SDK_ENVIRONMENT: "{sdk_env}"
        GCS_CLI_CLIENT_ID: "{client_id}"
        GCS_CLI_CLIENT_SECRET: "{client_secret}"

    - name: Delete HA test storage gateway
      m1yag1.globus.globus_gcs:
        resource_type: storage_gateway
        display_name: "HA Test Gateway"
        state: absent
      environment:
        GLOBUS_SDK_ENVIRONMENT: "{sdk_env}"
        GCS_CLI_CLIENT_ID: "{client_id}"
        GCS_CLI_CLIENT_SECRET: "{client_secret}"
"""

    playbook_path = create_playbook(playbook_content, "test_ha_gateway_collection.yml")
    result = run_playbook(playbook_path)

    assert result.returncode == 0, f"Playbook failed: {result.stderr}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "gcs"])
