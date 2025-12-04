#!/usr/bin/python

"""
Ansible module for managing Globus Connect Server v5 resources.

This module runs globus-connect-server CLI commands on the target host
to manage endpoints, storage gateways, collections, and roles.
"""

import json
import os
import sys
import tempfile
import time
import traceback

from ansible.module_utils.basic import AnsibleModule

DOCUMENTATION = r"""
---
module: globus_gcs
short_description: Manage Globus Connect Server v5 resources
description:
    - Setup and configure GCS v5 endpoints
    - Manage storage gateways (POSIX, S3, etc.)
    - Create and manage mapped collections
    - Assign and manage collection roles
    - All operations run globus-connect-server CLI on target host
version_added: "1.0.0"
author:
    - Ansible Globus Module Contributors
options:
    resource_type:
        description: Type of GCS resource to manage
        required: true
        type: str
        choices: ['endpoint', 'node', 'storage_gateway', 'collection', 'role']
    display_name:
        description: Display name (endpoint, storage_gateway, collection)
        required: false
        type: str
    endpoint_id:
        description: Endpoint ID (required for node setup and some operations)
        required: false
        type: str
    description:
        description: Description of the resource
        required: false
        type: str
    # Endpoint options
    organization:
        description: Organization name (endpoint only)
        required: false
        type: str
    department:
        description: Department name (endpoint only)
        required: false
        type: str
    contact_email:
        description: Contact email (endpoint only)
        required: false
        type: str
    project_id:
        description: Globus project ID (endpoint only)
        required: false
        type: str
    subscription_id:
        description: GCS subscription ID (endpoint only)
        required: false
        type: str
    owner:
        description: Endpoint owner identity (endpoint only)
        required: false
        type: str
    # Storage gateway options
    storage_type:
        description: Type of storage gateway
        required: false
        type: str
        choices: ['posix', 'blackpearl', 's3', 'google_cloud_storage', 'azure_blob']
        default: 'posix'
    allowed_domains:
        description: List of allowed authentication domains for the storage gateway
        required: false
        type: list
        elements: str
        default: ['globus.org', 'globusid.org', 'clients.auth.globus.org']
    identity_mapping:
        description:
            - Identity mapping configuration for the storage gateway
            - Can be a file path (string), a dict with full mapping structure, or a list of mapping rules
            - "Example inline: [{source: '{username}', match: 'art', output: 'ubuntu', literal: true}]"
            - "Example file: '/path/to/identity-mapping.json'"
        required: false
        type: raw
    root_path:
        description: Root path for POSIX storage (storage_gateway only)
        required: false
        type: str
    # Collection options
    storage_gateway_id:
        description: ID of the storage gateway (collection only)
        required: false
        type: str
    collection_base_path:
        description: Base path within storage gateway (collection only)
        required: false
        type: str
        default: '/'
    public:
        description: Whether collection is public (collection only)
        required: false
        type: bool
        default: false
    delete_protection:
        description: |
            Whether to enable delete protection on the collection (collection only).
            Default is true to prevent accidental deletion in production.
            For testing, explicitly set to false to allow easy cleanup.
        required: false
        type: bool
        default: true
    collection_id:
        description: Existing collection ID (for updates/role management)
        required: false
        type: str
    # Role options
    principal:
        description: Principal URN for role assignment (role only)
        required: false
        type: str
    role:
        description: Role to assign (role only)
        required: false
        type: str
        choices: ['administrator', 'access_manager', 'activity_manager', 'activity_monitor']
    # Common
    state:
        description: Desired state of the resource
        required: false
        type: str
        choices: ['present', 'absent']
        default: 'present'
    force:
        description: |
            Force update of resources even when no change is detected.
            For storage_gateway: Always update identity mapping if provided, even if gateway already exists.
            Default is false (idempotent behavior).
        required: false
        type: bool
        default: false
"""

EXAMPLES = r"""
# Setup GCS endpoint
- name: Setup GCS endpoint
  globus_gcs:
    resource_type: endpoint
    display_name: "My GCS Endpoint"
    organization: "University"
    contact_email: "admin@university.edu"
    project_id: "{{ project_id }}"
    subscription_id: "{{ subscription_id }}"
    state: present

# Create POSIX storage gateway
- name: Create POSIX storage gateway
  globus_gcs:
    resource_type: storage_gateway
    display_name: "My POSIX Gateway"
    storage_type: posix
    root_path: "/data"
    description: "Main data storage"
    state: present

# Create mapped collection
- name: Create mapped collection
  globus_gcs:
    resource_type: collection
    display_name: "My Collection"
    storage_gateway_id: "{{ gateway_id }}"
    collection_base_path: "/"
    description: "Research data collection"
    public: false
    state: present

# Assign administrator role
- name: Assign administrator role
  globus_gcs:
    resource_type: role
    collection_id: "{{ collection_id }}"
    principal: "urn:globus:auth:identity:12345"
    role: administrator
    state: present
"""

RETURN = r"""
endpoint_id:
    description: ID of the endpoint
    type: str
    returned: when resource_type=endpoint and state=present
endpoint_domain:
    description: Domain name of the endpoint
    type: str
    returned: when resource_type=endpoint and state=present
storage_gateway_id:
    description: ID of the storage gateway
    type: str
    returned: when resource_type=storage_gateway and state=present
collection_id:
    description: ID of the collection
    type: str
    returned: when resource_type=collection and state=present
role:
    description: Role assigned
    type: str
    returned: when resource_type=role and state=present
principal:
    description: Principal URN
    type: str
    returned: when resource_type=role
changed:
    description: Whether the resource was changed
    type: bool
    returned: always
"""


# =======================
# Endpoint functions
# =======================


def check_endpoint_configured(module):
    """Check if endpoint is already configured."""
    rc, stdout, stderr = module.run_command(
        ["globus-connect-server", "endpoint", "show"], check_rc=False
    )
    if rc == 0:
        return True, stdout if stdout else ""
    return False, None


def setup_endpoint(module, params):
    """Setup GCS endpoint.

    Requires environment variables:
    - GCS_CLI_CLIENT_ID
    - GCS_CLI_CLIENT_SECRET

    These allow non-interactive authentication with the Globus API.
    """
    # Check for required environment variables
    client_id = os.environ.get("GCS_CLI_CLIENT_ID")
    if not client_id:
        module.fail_json(
            msg="GCS_CLI_CLIENT_ID environment variable must be set for endpoint setup"
        )

    cmd = [
        "globus-connect-server",
        "endpoint",
        "setup",
        params["display_name"],
        "--contact-email",
        params["contact_email"],
        "--agree-to-letsencrypt-tos",
        "--dont-set-advertised-owner",  # Required for client credentials auth
    ]

    # Required organization
    if params.get("organization"):
        cmd.extend(["--organization", params["organization"]])
    else:
        # Organization is required by CLI
        cmd.extend(["--organization", "Test Organization"])

    # Owner - use client identity format
    if params.get("owner"):
        cmd.extend(["--owner", params["owner"]])
    else:
        # Default to client identity
        cmd.extend(["--owner", f"{client_id}@clients.auth.globus.org"])

    # Optional parameters
    if params.get("department"):
        cmd.extend(["--department", params["department"]])
    if params.get("description"):
        cmd.extend(["--description", params["description"]])
    if params.get("project_id"):
        cmd.extend(["--project-id", params["project_id"]])
    # Note: subscription_id is set via a separate command after endpoint setup

    rc, stdout, stderr = module.run_command(cmd, check_rc=False)
    if rc != 0:
        module.fail_json(
            msg=f"Failed to setup GCS endpoint: {stderr}",
            rc=rc,
            stdout=stdout,
            stderr=stderr,
        )

    # Set subscription ID if provided
    # This requires GCS_CLI_ENDPOINT_ID to be set, so we get it first
    subscription_id = params.get("subscription_id")
    if subscription_id:
        # Get the endpoint ID from the configuration file
        endpoint_id = get_endpoint_id(module)
        if not endpoint_id:
            module.fail_json(msg="Failed to get endpoint ID after setup")

        # Set the endpoint ID in environment for the subscription command
        os.environ["GCS_CLI_ENDPOINT_ID"] = endpoint_id

        sub_cmd = [
            "globus-connect-server",
            "endpoint",
            "set-subscription-id",
            subscription_id,
        ]
        rc, sub_stdout, sub_stderr = module.run_command(sub_cmd, check_rc=False)
        if rc != 0:
            module.fail_json(
                msg=f"Failed to set subscription ID: {sub_stderr}",
                rc=rc,
                stdout=sub_stdout,
                stderr=sub_stderr,
            )

    return True, stdout


def parse_endpoint_info(output):
    """Parse endpoint info from globus-connect-server endpoint show output."""
    if output is None or not output:
        return {}

    if not isinstance(output, str):
        return {}

    info = {}
    for line in output.split("\n"):
        if ":" in line:
            key, value = line.split(":", 1)
            key = key.strip().lower().replace(" ", "_")
            value = value.strip()
            info[key] = value
    return info


# =======================
# Node functions
# =======================


def check_node_configured(module):
    """Check if node is already configured."""
    rc, stdout, stderr = module.run_command(
        ["globus-connect-server", "node", "list", "--format", "json"], check_rc=False
    )
    if rc == 0 and stdout:
        try:
            result = json.loads(stdout)
            nodes = result.get("data", [])
            return len(nodes) > 0, nodes
        except (json.JSONDecodeError, KeyError):
            pass
    return False, None


def setup_node(module):
    """Setup GCS node (requires sudo)."""
    cmd = ["globus-connect-server", "node", "setup"]

    rc, stdout, stderr = module.run_command(cmd, check_rc=False)
    if rc != 0:
        module.fail_json(
            msg=f"Failed to setup GCS node: {stderr}",
            rc=rc,
            stdout=stdout,
            stderr=stderr,
        )
    return True, stdout


# =======================
# Storage gateway functions
# =======================


def list_storage_gateways(module):
    """List all storage gateways."""
    rc, stdout, stderr = module.run_command(
        ["globus-connect-server", "storage-gateway", "list", "--format", "json"],
        check_rc=False,
    )
    if rc != 0:
        return []
    try:
        result = json.loads(stdout)
        # GCS CLI returns a list with one result dict: [{...}]
        if isinstance(result, list) and len(result) > 0:
            return result[0].get("data", [])
        return []
    except (json.JSONDecodeError, KeyError):
        return []


def find_storage_gateway(module, display_name=None, storage_gateway_id=None):
    """Find storage gateway by display name or ID."""
    gateways = list_storage_gateways(module)
    for gw in gateways:
        if storage_gateway_id and gw.get("id") == storage_gateway_id:
            return gw
        if display_name and gw.get("display_name") == display_name:
            return gw
    return None


def get_endpoint_id(module, max_retries=3, retry_delay=1):
    """Get the endpoint ID from GCS configuration.

    Includes retry logic to handle transient file read failures that can occur
    when multiple operations are running in parallel.

    Args:
        module: Ansible module instance
        max_retries: Maximum number of attempts (default: 3)
        retry_delay: Seconds to wait between retries (default: 1)

    Returns:
        Endpoint ID string or None if not configured
    """
    for attempt in range(max_retries):
        try:
            # The info.json file is only readable by root, so we need sudo
            rc, stdout, stderr = module.run_command(
                ["sudo", "cat", "/var/lib/globus-connect-server/info.json"],
                check_rc=False,
            )
            if rc == 0 and stdout:
                info = json.loads(stdout)
                # Make sure we got a dict, not a list
                if isinstance(info, dict):
                    endpoint_id = info.get("endpoint_id")
                    if endpoint_id:
                        return endpoint_id
        except json.JSONDecodeError:
            # Invalid JSON - endpoint likely not configured, no point retrying
            return None
        except Exception:  # nosec B110
            # Transient failure - retry
            pass

        # Wait before retry (except on last attempt)
        if attempt < max_retries - 1:
            time.sleep(retry_delay)

    return None


def create_storage_gateway(module, params):
    """Create a new storage gateway.

    Note: Storage gateways in GCS v5 are policy containers and don't have a root path.
    The path mapping is specified when creating collections on the storage gateway.
    Storage gateways also don't support a description parameter.
    Storage gateways require at least one allowed domain for security.
    If more than one domain is specified, identity mapping is required.
    """
    cmd = [
        "globus-connect-server",
        "storage-gateway",
        "create",
        params["storage_type"],
        params["display_name"],
        "--format",
        "json",
    ]

    # Storage gateways require at least one allowed domain
    # Use the allowed_domains parameter (defaults to globus.org, globusid.org, clients.auth.globus.org)
    allowed_domains = params.get(
        "allowed_domains", ["globus.org", "globusid.org", "clients.auth.globus.org"]
    )
    for domain in allowed_domains:
        cmd.extend(["--domain", domain])

    # If identity mapping is provided, add it to the create command
    # This is required when more than one domain is specified
    identity_mapping = params.get("identity_mapping")

    if identity_mapping:
        # Check if it's a file path or inline definition
        if isinstance(identity_mapping, str):
            # File path - read the file
            if not os.path.exists(identity_mapping):
                module.fail_json(
                    msg=f"Identity mapping file not found: {identity_mapping}"
                )
            with open(identity_mapping) as f:
                mapping_json = f.read()
        else:
            # Inline definition - convert to JSON string
            if isinstance(identity_mapping, list):
                mapping_data = {
                    "DATA_TYPE": "expression_identity_mapping#1.0.0",
                    "mappings": identity_mapping,
                }
            elif isinstance(identity_mapping, dict):
                if "DATA_TYPE" not in identity_mapping:
                    identity_mapping["DATA_TYPE"] = "expression_identity_mapping#1.0.0"
                mapping_data = identity_mapping
            else:
                module.fail_json(
                    msg="identity_mapping must be a dict, list, or file path"
                )

            mapping_json = json.dumps(mapping_data)

        # Add identity mapping JSON content to command
        cmd.extend(["--identity-mapping", mapping_json])

    # High Assurance parameters
    if params.get("high_assurance"):
        cmd.append("--high-assurance")

    if params.get("authentication_timeout_mins"):
        cmd.extend(
            [
                "--authentication-timeout-mins",
                str(params["authentication_timeout_mins"]),
            ]
        )

    if params.get("require_mfa"):
        cmd.append("--mfa")
    elif params.get("high_assurance"):  # Only add --no-mfa if HA is enabled
        cmd.append("--no-mfa")

    rc, stdout, stderr = module.run_command(cmd, check_rc=False)
    if rc != 0:
        # Try to parse error message from GCS JSON output
        error_msg = stderr
        if stdout:
            try:
                error_data = json.loads(stdout)
                # Extract the message from GCS error response
                if isinstance(error_data, dict) and "message" in error_data:
                    error_msg = error_data["message"]
            except json.JSONDecodeError:
                # If not JSON, use stderr or stdout as-is
                error_msg = stderr or stdout

        module.fail_json(
            msg=f"Failed to create storage gateway: {error_msg}",
            rc=rc,
            stdout=stdout,
            stderr=stderr,
        )
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        module.fail_json(msg=f"Failed to parse storage gateway output: {stdout}")


def update_storage_gateway_identity_mapping(
    module, gateway_id, storage_type, identity_mapping
):
    """Update storage gateway identity mapping.

    :param module: Ansible module
    :param gateway_id: Storage gateway ID
    :param storage_type: Storage type (e.g., 'posix', 's3', 'azure-blob')
    :param identity_mapping: Identity mapping as dict, list, or file path string
    """
    mapping_file = None
    cleanup_temp_file = False

    # Check if identity_mapping is a file path (string)
    if isinstance(identity_mapping, str):
        # Treat as file path
        if not os.path.exists(identity_mapping):
            module.fail_json(msg=f"Identity mapping file not found: {identity_mapping}")
        mapping_file = identity_mapping
    else:
        # Inline definition - create temp file
        # Ensure proper structure
        if isinstance(identity_mapping, list):
            mapping_data = {
                "DATA_TYPE": "expression_identity_mapping#1.0.0",
                "mappings": identity_mapping,
            }
        elif isinstance(identity_mapping, dict):
            # Assume it's already in the correct format
            if "DATA_TYPE" not in identity_mapping:
                identity_mapping["DATA_TYPE"] = "expression_identity_mapping#1.0.0"
            mapping_data = identity_mapping
        else:
            module.fail_json(
                msg="identity_mapping must be a dict, list, or file path string"
            )

        # Write to temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(mapping_data, f, indent=2)
            mapping_file = f.name
            cleanup_temp_file = True

    try:
        # GCS CLI requires: storage-gateway update <storage_type> --identity-mapping file:<path> <gateway_id>
        # Note: gateway_id must come LAST as a positional argument after all options
        cmd = [
            "globus-connect-server",
            "storage-gateway",
            "update",
            storage_type,
            "--identity-mapping",
            f"file:{mapping_file}",
            gateway_id,
        ]
        rc, stdout, stderr = module.run_command(cmd, check_rc=False)
        if rc != 0:
            module.fail_json(
                msg=f"Failed to update storage gateway identity mapping: {stderr}",
                rc=rc,
                stdout=stdout,
                stderr=stderr,
            )
        return True
    finally:
        # Clean up temp file if we created one
        if cleanup_temp_file and mapping_file and os.path.exists(mapping_file):
            os.unlink(mapping_file)


def delete_storage_gateway(module, gateway_id):
    """Delete a storage gateway."""
    cmd = ["globus-connect-server", "storage-gateway", "delete", gateway_id]
    rc, stdout, stderr = module.run_command(cmd, check_rc=False)
    if rc != 0:
        module.fail_json(
            msg=f"Failed to delete storage gateway: {stderr}",
            rc=rc,
            stdout=stdout,
            stderr=stderr,
        )
    return True


# =======================
# Collection functions
# =======================


def list_collections(module):
    """List all collections."""
    rc, stdout, stderr = module.run_command(
        ["globus-connect-server", "collection", "list", "--format", "json"],
        check_rc=False,
    )
    if rc != 0:
        return []
    try:
        result = json.loads(stdout)
        # GCS CLI returns a list of collection objects directly
        if isinstance(result, list):
            return result
        return []
    except (json.JSONDecodeError, KeyError):
        return []


def find_collection(module, display_name=None, collection_id=None, retries=3):
    """Find collection by display name or ID with retry support for eventual consistency.

    Args:
        module: Ansible module
        display_name: Collection display name to search for
        collection_id: Collection ID to search for (takes precedence)
        retries: Number of times to retry finding by display_name (default: 3)

    Returns:
        Collection dict if found, None otherwise
    """
    # If searching by ID, no need to retry - IDs are immediately consistent
    if collection_id:
        collections = list_collections(module)
        for coll in collections:
            if coll.get("id") == collection_id:
                return coll
        return None

    # When searching by display_name, retry to handle eventual consistency
    if display_name:
        for attempt in range(retries):
            collections = list_collections(module)
            for coll in collections:
                if coll.get("display_name") == display_name:
                    return coll

            # If not found and we have retries left, wait before trying again
            if attempt < retries - 1:
                time.sleep(2**attempt)  # Exponential backoff: 1s, 2s, 4s

    return None


def create_collection(module, params):
    """Create a new mapped collection."""
    cmd = [
        "globus-connect-server",
        "collection",
        "create",
        params["storage_gateway_id"],
        params["collection_base_path"],
        params["display_name"],
        "--format",
        "json",
    ]

    if params.get("description"):
        cmd.extend(["--description", params["description"]])
    if params.get("public"):
        cmd.append("--public")
    # Handle delete protection flag (only --delete-protected on create)
    # GCS CLI defaults to --delete-protected enabled for mapped collections
    # Note: --no-delete-protected is only available on collection update, not create
    if params.get("delete_protection") is True:
        cmd.append("--delete-protected")
    if params.get("require_high_assurance"):
        # Restrict all transfers to high assurance if this flag is set
        cmd.extend(["--restrict-transfers-to-high-assurance", "all"])

    rc, stdout, stderr = module.run_command(cmd, check_rc=False)
    if rc != 0:
        module.fail_json(
            msg=f"Failed to create collection: {stderr}",
            rc=rc,
            stdout=stdout,
            stderr=stderr,
        )
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        module.fail_json(msg=f"Failed to parse collection output: {stdout}")


def update_collection(module, collection_id, params):
    """Update an existing collection."""
    cmd = [
        "globus-connect-server",
        "collection",
        "update",
        collection_id,
        "--format",
        "json",
    ]

    if params.get("description") is not None:
        cmd.extend(["--description", params["description"]])
    if params.get("display_name"):
        cmd.extend(["--display-name", params["display_name"]])

    rc, stdout, stderr = module.run_command(cmd, check_rc=False)
    if rc != 0:
        module.fail_json(
            msg=f"Failed to update collection: {stderr}",
            rc=rc,
            stdout=stdout,
            stderr=stderr,
        )
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        module.fail_json(msg=f"Failed to parse collection update output: {stdout}")


def delete_collection(module, collection_id):
    """Delete a collection."""
    cmd = ["globus-connect-server", "collection", "delete", collection_id]
    rc, stdout, stderr = module.run_command(cmd, check_rc=False)
    if rc != 0:
        module.fail_json(
            msg=f"Failed to delete collection: {stderr}",
            rc=rc,
            stdout=stdout,
            stderr=stderr,
        )
    return True


# =======================
# Role functions
# =======================


def list_roles(module, collection_id):
    """List all roles for a collection."""
    rc, stdout, stderr = module.run_command(
        [
            "globus-connect-server",
            "collection",
            "role",
            "list",
            collection_id,
            "--format",
            "json",
        ],
        check_rc=False,
    )
    if rc != 0:
        return []
    try:
        result = json.loads(stdout)
        # GCS CLI returns a result wrapper: [{"data": [...]}]
        if isinstance(result, list) and len(result) > 0:
            return result[0].get("data", [])
        return []
    except (json.JSONDecodeError, KeyError):
        return []


def find_role(module, collection_id, principal, role, retries=30):
    """Check if a role assignment exists with retry support for eventual consistency.

    The GCS CLI accepts principal identifiers in multiple formats (email addresses, URNs),
    but always returns URNs when listing roles. This function handles the format mismatch
    by normalizing both inputs and API responses before comparison.

    Args:
        module: Ansible module
        collection_id: Collection ID to search roles in
        principal: Principal (user/group) to search for (can be email or URN)
        role: Role name to search for
        retries: Number of times to retry (default: 30)

    Returns:
        Role dict if found, None otherwise
    """

    # Normalize the input principal to just the username part for comparison
    # Examples:
    #   "art@globusid.org" -> "art@globusid.org"
    #   "urn:globus:auth:identity:abc-def:art@globusid.org" -> "art@globusid.org"
    def normalize_principal(p):
        if not p:
            return p
        # If it's a URN, extract the part after the last colon
        if p.startswith("urn:globus:"):
            parts = p.split(":")
            if len(parts) >= 2:
                return parts[-1]
        return p

    normalized_input = normalize_principal(principal)

    for attempt in range(retries):
        roles = list_roles(module, collection_id)
        for r in roles:
            api_principal = r.get("principal")
            normalized_api = normalize_principal(api_principal)

            # Match if either:
            # 1. Exact match (handles URN-to-URN comparison)
            # 2. Normalized match (handles email-to-URN comparison)
            if r.get("role") == role and (
                api_principal == principal or normalized_api == normalized_input
            ):
                return r

        # If not found and we have retries left, wait before trying again
        if attempt < retries - 1:
            time.sleep(2)  # Constant 2s delay between attempts

    return None


def create_role(module, collection_id, principal, role):
    """Assign a role to a principal."""
    cmd = [
        "globus-connect-server",
        "collection",
        "role",
        "create",
        collection_id,
        role,
        principal,
        "--format",
        "json",
    ]

    rc, stdout, stderr = module.run_command(cmd, check_rc=False)

    # Extract JSON from stdout (skip non-JSON lines from globus-env.sh)
    def extract_json(output):
        """Extract JSON from output that may contain non-JSON lines."""
        if not output:
            return None
        lines = output.strip().split("\n")
        json_lines = []
        in_json = False

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("{") or stripped.startswith("["):
                in_json = True
            if in_json:
                json_lines.append(line)

        if json_lines:
            try:
                return json.loads("\n".join(json_lines))
            except json.JSONDecodeError:
                return None
        return None

    # Parse JSON from both stdout and stderr - CLI may output errors to either
    result = extract_json(stdout)
    error_result = extract_json(stderr)

    # CLI returns JSON array like [{"code": "exists", ...}] - unwrap it
    if isinstance(result, list) and len(result) > 0:
        result = result[0]
    if isinstance(error_result, list) and len(error_result) > 0:
        error_result = error_result[0]

    # Check for "already exists" error in stdout (idempotency)
    # CLI returns {"code": "exists", "is_error": true, "http_status": 409} for duplicates
    if isinstance(result, dict) and result.get("code") == "exists":
        return {"principal": principal, "role": role, "already_exists": True}

    # Check for "already exists" error in stderr (some CLI versions output here)
    if isinstance(error_result, dict) and error_result.get("code") == "exists":
        return {"principal": principal, "role": role, "already_exists": True}

    # Handle actual failures (rc != 0)
    if rc != 0:
        # Check text patterns in stderr
        if (
            "already exists" in stderr.lower()
            or "already been assigned" in stderr.lower()
        ):
            return {"principal": principal, "role": role, "already_exists": True}

        # For other errors, fail
        module.fail_json(
            msg=f"Failed to create role: {stderr or stdout}",
            rc=rc,
            stdout=stdout,
            stderr=stderr,
        )

    # Success case - return the parsed result or fallback
    if result:
        return result
    else:
        return {"principal": principal, "role": role}


def delete_role(module, collection_id, principal, role):
    """Remove a role from a principal."""
    cmd = [
        "globus-connect-server",
        "collection",
        "role",
        "delete",
        collection_id,
        role,
        principal,
    ]

    rc, stdout, stderr = module.run_command(cmd, check_rc=False)
    if rc != 0:
        module.fail_json(
            msg=f"Failed to delete role: {stderr}",
            rc=rc,
            stdout=stdout,
            stderr=stderr,
        )
    return True


# =======================
# Main module
# =======================


def main():
    module = AnsibleModule(
        argument_spec={
            "resource_type": {
                "type": "str",
                "required": True,
                "choices": [
                    "endpoint",
                    "node",
                    "storage_gateway",
                    "collection",
                    "role",
                ],
            },
            "display_name": {"type": "str"},
            "description": {"type": "str"},
            "endpoint_id": {"type": "str"},
            # Endpoint
            "organization": {"type": "str"},
            "department": {"type": "str"},
            "contact_email": {"type": "str"},
            "project_id": {"type": "str"},
            "subscription_id": {"type": "str"},
            "owner": {"type": "str"},
            # Storage gateway
            "storage_type": {
                "type": "str",
                "default": "posix",
                "choices": [
                    "posix",
                    "blackpearl",
                    "s3",
                    "google_cloud_storage",
                    "azure_blob",
                ],
            },
            "allowed_domains": {
                "type": "list",
                "elements": "str",
                "default": ["globus.org", "globusid.org", "clients.auth.globus.org"],
            },
            "identity_mapping": {
                "type": "raw",  # Can be dict or list
            },
            "root_path": {"type": "str"},
            # High Assurance (storage gateway)
            "high_assurance": {"type": "bool", "default": False},
            "authentication_timeout_mins": {"type": "int"},
            "require_mfa": {"type": "bool", "default": False},
            # Collection
            "storage_gateway_id": {"type": "str"},
            "collection_base_path": {"type": "str"},
            "public": {"type": "bool", "default": False},
            "delete_protection": {"type": "bool", "default": True},
            "require_high_assurance": {"type": "bool", "default": False},
            "collection_id": {"type": "str"},
            # Role
            "principal": {"type": "str"},
            "role": {
                "type": "str",
                "choices": [
                    "administrator",
                    "access_manager",
                    "activity_manager",
                    "activity_monitor",
                ],
            },
            # Common
            "state": {
                "type": "str",
                "default": "present",
                "choices": ["present", "absent"],
            },
            "force": {
                "type": "bool",
                "default": False,
            },
        },
        required_if=[
            (
                "resource_type",
                "endpoint",
                ("display_name", "contact_email", "project_id"),
            ),
            ("resource_type", "storage_gateway", ("display_name",)),
            ("resource_type", "collection", ("display_name",)),
            ("resource_type", "role", ("collection_id", "principal", "role")),
            ("state", "present", ["resource_type"]),
        ],
        supports_check_mode=True,
    )

    resource_type = module.params["resource_type"]
    state = module.params["state"]

    # For storage gateway, collection, and role operations, we need the endpoint ID
    # Get it from the GCS configuration and set it as an environment variable
    if resource_type in ["storage_gateway", "collection", "role"]:
        endpoint_id = get_endpoint_id(module)
        if endpoint_id:
            os.environ["GCS_CLI_ENDPOINT_ID"] = endpoint_id
        elif resource_type != "endpoint":
            # Only fail if we're not setting up the endpoint
            module.fail_json(
                msg="Endpoint not configured. Please run endpoint setup first."
            )

    # Manual validation for storage gateway
    # Note: Storage gateways in GCS v5 don't require a root_path
    # The path is specified when creating collections on the storage gateway
    if resource_type == "storage_gateway":
        pass  # No additional validation needed

    # Manual validation for collection
    if resource_type == "collection" and state == "present":
        if not module.params.get("storage_gateway_id"):
            module.fail_json(msg="storage_gateway_id is required for collections")
        # Set default for collection_base_path if not provided
        if not module.params.get("collection_base_path"):
            module.params["collection_base_path"] = "/"

    # =======================
    # Endpoint management
    # =======================
    if resource_type == "endpoint":
        is_configured, endpoint_info_raw = check_endpoint_configured(module)

        if state == "present":
            if is_configured:
                endpoint_info = parse_endpoint_info(endpoint_info_raw)
                module.exit_json(
                    changed=False,
                    endpoint_id=endpoint_info.get("endpoint_id", ""),
                    endpoint_domain=endpoint_info.get("endpoint_domain", ""),
                    resource_type="endpoint",
                    msg="Endpoint already configured",
                )
            else:
                if module.check_mode:
                    module.exit_json(changed=True, msg="Would setup endpoint")

                setup_endpoint(module, module.params)
                is_configured_after, endpoint_info_raw = check_endpoint_configured(
                    module
                )

                if not is_configured_after or not endpoint_info_raw:
                    module.fail_json(
                        msg="Endpoint setup completed but endpoint information could not be retrieved"
                    )

                endpoint_info = parse_endpoint_info(endpoint_info_raw)

                module.exit_json(
                    changed=True,
                    endpoint_id=endpoint_info.get("endpoint_id", ""),
                    endpoint_domain=endpoint_info.get("endpoint_domain", ""),
                    resource_type="endpoint",
                    msg="Endpoint setup complete",
                )

        elif state == "absent":
            if not is_configured:
                module.exit_json(changed=False, msg="Endpoint not configured")
            module.fail_json(msg="Endpoint deletion not yet implemented")

    # =======================
    # Node management
    # =======================
    elif resource_type == "node":
        is_configured, nodes = check_node_configured(module)

        if state == "present":
            if is_configured:
                module.exit_json(
                    changed=False,
                    node_count=len(nodes) if nodes else 0,
                    resource_type="node",
                    msg="Node already configured",
                )
            else:
                if module.check_mode:
                    module.exit_json(changed=True, msg="Would setup node")

                setup_node(module)

                module.exit_json(
                    changed=True,
                    resource_type="node",
                    msg="Node setup complete",
                )

        elif state == "absent":
            if not is_configured:
                module.exit_json(changed=False, msg="Node not configured")
            module.fail_json(msg="Node deletion not yet implemented")

    # =======================
    # Storage gateway management
    # =======================
    elif resource_type == "storage_gateway":
        display_name = module.params["display_name"]
        storage_gateway_id = module.params.get("storage_gateway_id")

        # Find by ID if provided, otherwise by display name
        existing_gateway = find_storage_gateway(
            module,
            display_name=display_name if not storage_gateway_id else None,
            storage_gateway_id=storage_gateway_id,
        )

        if state == "present":
            if existing_gateway:
                # Check if we need to update the gateway
                force = module.params.get("force", False)
                identity_mapping = module.params.get("identity_mapping")

                # Determine if an update is needed:
                # - If force=True and identity_mapping is provided, always update
                # - Otherwise, maintain idempotent behavior (no update)
                needs_update = force and identity_mapping is not None

                if needs_update:
                    if module.check_mode:
                        module.exit_json(
                            changed=True, msg="Would update storage gateway"
                        )

                    # Update identity mapping
                    storage_type = module.params.get("storage_type")
                    if not storage_type:
                        module.fail_json(
                            msg="storage_type parameter required for updating storage gateway"
                        )
                    update_storage_gateway_identity_mapping(
                        module, existing_gateway["id"], storage_type, identity_mapping
                    )

                    module.exit_json(
                        changed=True,
                        storage_gateway_id=existing_gateway.get("id"),
                        display_name=existing_gateway.get("display_name"),
                        storage_type=existing_gateway.get("connector_id"),
                        resource_type="storage_gateway",
                        msg="Storage gateway updated",
                    )
                else:
                    module.exit_json(
                        changed=False,
                        storage_gateway_id=existing_gateway.get("id"),
                        display_name=existing_gateway.get("display_name"),
                        storage_type=existing_gateway.get("connector_id"),
                        resource_type="storage_gateway",
                        msg="Storage gateway already exists",
                    )
            else:
                if module.check_mode:
                    module.exit_json(changed=True, msg="Would create storage gateway")

                result = create_storage_gateway(module, module.params)

                module.exit_json(
                    changed=True,
                    storage_gateway_id=result.get("id"),
                    display_name=result.get("display_name"),
                    storage_type=result.get("connector_id"),
                    resource_type="storage_gateway",
                    msg="Storage gateway created",
                )

        elif state == "absent":
            if not existing_gateway:
                module.exit_json(changed=False, msg="Storage gateway does not exist")

            if module.check_mode:
                module.exit_json(changed=True, msg="Would delete storage gateway")

            # Delete all collections on this gateway first
            # GCS requires collections to be deleted before the gateway can be deleted
            collections = list_collections(module)
            gateway_id = existing_gateway["id"]
            deleted_collections = []

            for collection in collections:
                if collection.get("storage_gateway_id") == gateway_id:
                    delete_collection(module, collection["id"])
                    deleted_collections.append(
                        collection.get("display_name", collection["id"])
                    )

            # Now delete the gateway
            delete_storage_gateway(module, gateway_id)

            if deleted_collections:
                module.exit_json(
                    changed=True,
                    msg=f"Storage gateway deleted (also deleted {len(deleted_collections)} collections: {', '.join(deleted_collections)})",
                )
            else:
                module.exit_json(changed=True, msg="Storage gateway deleted")

    # =======================
    # Collection management
    # =======================
    elif resource_type == "collection":
        display_name = module.params["display_name"]
        existing_collection = find_collection(
            module,
            display_name=display_name,
            collection_id=module.params.get("collection_id"),
        )

        if state == "present":
            # Require storage_gateway_id for creation
            if not existing_collection and not module.params.get("storage_gateway_id"):
                module.fail_json(
                    msg="storage_gateway_id is required to create a collection"
                )

            if existing_collection:
                needs_update = False

                # Check if description changed
                # Handle both None and empty string cases
                existing_desc = existing_collection.get("description") or ""
                new_desc = module.params.get("description") or ""
                if new_desc and new_desc != existing_desc:
                    needs_update = True

                # Check if display_name changed
                if module.params.get("display_name") and module.params[
                    "display_name"
                ] != existing_collection.get("display_name"):
                    needs_update = True

                if needs_update:
                    if module.check_mode:
                        module.exit_json(changed=True, msg="Would update collection")

                    result = update_collection(
                        module, existing_collection["id"], module.params
                    )
                    # Use the requested values from params as fallback since the CLI
                    # may not return all fields in the update response
                    module.exit_json(
                        changed=True,
                        collection_id=result.get("id") or existing_collection.get("id"),
                        display_name=result.get("display_name")
                        or module.params.get("display_name"),
                        description=result.get("description")
                        or module.params.get("description"),
                        resource_type="collection",
                        msg="Collection updated",
                    )
                else:
                    module.exit_json(
                        changed=False,
                        collection_id=existing_collection.get("id"),
                        display_name=existing_collection.get("display_name"),
                        description=existing_collection.get("description"),
                        resource_type="collection",
                        msg="Collection already exists",
                    )
            else:
                if module.check_mode:
                    module.exit_json(changed=True, msg="Would create collection")

                result = create_collection(module, module.params)
                collection_id = result.get("id")

                # If delete_protection is explicitly false, we need to update
                # the collection to disable it (not supported on create command)
                if module.params.get("delete_protection") is False and collection_id:
                    update_cmd = [
                        "globus-connect-server",
                        "collection",
                        "update",
                        collection_id,
                        "--no-delete-protected",
                        "--format",
                        "json",
                    ]
                    rc, stdout, stderr = module.run_command(update_cmd, check_rc=False)
                    if rc != 0:
                        module.fail_json(
                            msg=f"Collection created but failed to disable delete protection: {stderr}",
                            rc=rc,
                            stdout=stdout,
                            stderr=stderr,
                        )

                module.exit_json(
                    changed=True,
                    collection_id=collection_id,
                    display_name=result.get("display_name"),
                    description=result.get("description"),
                    resource_type="collection",
                    msg="Collection created",
                )

        elif state == "absent":
            if not existing_collection:
                module.exit_json(changed=False, msg="Collection does not exist")

            if module.check_mode:
                module.exit_json(changed=True, msg="Would delete collection")

            delete_collection(module, existing_collection["id"])
            module.exit_json(changed=True, msg="Collection deleted")

    # =======================
    # Role management
    # =======================
    elif resource_type == "role":
        collection_id = module.params["collection_id"]
        principal = module.params["principal"]
        role = module.params["role"]

        if state == "present":
            if module.check_mode:
                module.exit_json(changed=True, msg="Would assign role")

            # Try to create the role directly - the API handles idempotency
            # If the role already exists, the CLI returns rc=1 with "code": "exists"
            # which create_role() detects and returns {"already_exists": True}
            result = create_role(module, collection_id, principal, role)

            # Check if the role already existed (409 response from API)
            already_existed = isinstance(result, dict) and result.get(
                "already_exists", False
            )

            # Extract the resolved principal from the create response
            # The GCS CLI resolves principals like "user@globusid.org" to URNs
            resolved_principal = (
                result.get("principal", principal)
                if isinstance(result, dict)
                else principal
            )

            module.exit_json(
                changed=not already_existed,
                role=role,
                principal=resolved_principal,
                resource_type="role",
                msg="Role already assigned" if already_existed else "Role assigned",
            )

        elif state == "absent":
            # For deletion, we need to check if the role exists first
            # Note: find_role() may not find the role if there's a principal format mismatch,
            # but that's okay - delete_role() will fail gracefully if the role doesn't exist
            existing_role = find_role(module, collection_id, principal, role, retries=1)

            if not existing_role:
                module.exit_json(changed=False, msg="Role not assigned")

            if module.check_mode:
                module.exit_json(changed=True, msg="Would remove role")

            delete_role(module, collection_id, principal, role)
            module.exit_json(changed=True, msg="Role removed")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # Print error as JSON for Ansible to parse
        error_output = {
            "failed": True,
            "msg": f"Module execution failed: {str(e)}",
            "exception": traceback.format_exc(),
            "error_type": type(e).__name__,
        }
        print(json.dumps(error_output))
        sys.exit(1)
