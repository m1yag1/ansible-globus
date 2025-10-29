#!/usr/bin/python

DOCUMENTATION = r"""
---
module: globus_auth
short_description: Manage Globus Auth resources (projects, clients, and policies)
description:
    - Create and update Globus Auth projects and OAuth clients
    - Manage authentication policies for projects
    - Configure project membership and access controls
    - Requires manage_projects scope
    - "NOTE: Deletion of projects and OAuth clients requires high-assurance authentication (MFA within 30 minutes) and must be done manually via https://app.globus.org/settings/developers"
version_added: "1.0.0"
author:
    - Ansible Globus Module Contributors
options:
    resource_type:
        description: Type of auth resource to manage
        required: true
        type: str
        choices: ['project', 'policy', 'client']
    name:
        description: Name/identifier for the resource (display_name for projects, display_name for policies)
        required: true
        type: str
    resource_id:
        description: ID of existing resource (project_id or policy_id for updates)
        required: false
        type: str
    project_id:
        description: Project ID (required for policy resources)
        required: false
        type: str
    contact_email:
        description: Contact email (project only)
        required: false
        type: str
    description:
        description: Description of the resource
        required: false
        type: str
    admin_ids:
        description: List of Globus identity IDs for project administrators (project only)
        required: false
        type: list
        elements: str
    admin_group_ids:
        description: List of Globus group IDs for project administrators (project only)
        required: false
        type: list
        elements: str
    client_type:
        description: Type of OAuth client to create (client only)
        required: false
        type: str
        choices:
            - 'confidential_client'
            - 'public_installed_client'
            - 'client_identity'
            - 'resource_server'
            - 'globus_connect_server'
            - 'hybrid_confidential_client_resource_server'
    redirect_uris:
        description: List of OAuth redirect URIs (client only)
        required: false
        type: list
        elements: str
    visibility:
        description: Client visibility (client only)
        required: false
        type: str
        choices: ['public', 'private']
        default: 'private'
    terms_and_conditions:
        description: URL to terms and conditions (client only)
        required: false
        type: str
    privacy_policy:
        description: URL to privacy policy (client only)
        required: false
        type: str
    required_idp:
        description: Required identity provider UUID (client only)
        required: false
        type: str
    preselect_idp:
        description: Pre-selected identity provider UUID (client only)
        required: false
        type: str
    credential_output_file:
        description: Path to save client credentials JSON file (client only)
        required: false
        type: path
    high_assurance:
        description: Require high assurance authentication (policy only)
        required: false
        type: bool
        default: false
    authentication_assurance_timeout:
        description: Timeout in seconds for authentication assurance (policy only)
        required: false
        type: int
    domain_constraints_include:
        description: List of allowed authentication domains (policy only)
        required: false
        type: list
        elements: str
    domain_constraints_exclude:
        description: List of prohibited authentication domains (policy only)
        required: false
        type: list
        elements: str
    state:
        description: Desired state of the resource
        required: false
        type: str
        choices: ['present', 'absent']
        default: 'present'
extends_documentation_fragment:
    - globus_auth
"""

EXAMPLES = r"""
# Project Management
- name: Create a Globus Auth project
  globus_auth:
    resource_type: project
    name: "Research Data Project"
    contact_email: "admin@example.org"
    description: "Project for managing research data transfers"
    admin_ids:
      - "ae341a98-d274-11e5-b888-dbae3a8ba545"
    state: present

- name: Update project administrators
  globus_auth:
    resource_type: project
    name: "Research Data Project"
    admin_ids:
      - "ae341a98-d274-11e5-b888-dbae3a8ba545"
      - "b1234567-d274-11e5-b888-dbae3a8ba545"
    admin_group_ids:
      - "c7890abc-d274-11e5-b888-dbae3a8ba545"
    state: present

# NOTE: Project deletion requires high-assurance authentication (MFA within 30 min)
# and must be done manually at https://app.globus.org/settings/developers
# state: absent is not supported for projects

# Policy Management
- name: Create high assurance policy for project
  globus_auth:
    resource_type: policy
    project_id: "abc123-def456-ghi789"
    name: "High Security Policy"
    description: "Requires high assurance authentication"
    high_assurance: true
    authentication_assurance_timeout: 3600
    state: present

- name: Create domain-restricted policy
  globus_auth:
    resource_type: policy
    project_id: "abc123-def456-ghi789"
    name: "University Only Policy"
    description: "Only allow university domains"
    domain_constraints_include:
      - "university.edu"
      - "research.org"
    domain_constraints_exclude:
      - "gmail.com"
    state: present

- name: Delete a policy
  globus_auth:
    resource_type: policy
    project_id: "abc123-def456-ghi789"
    name: "Old Policy"
    state: absent

# Client Management
- name: Create service account (confidential client)
  globus_auth:
    resource_type: client
    name: "Automation Service Account"
    project_id: "abc123-def456-ghi789"
    client_type: "confidential_client"
    redirect_uris:
      - "https://myapp.example.com/callback"
    visibility: "private"
    state: present
  register: service_account
  no_log: true  # Important: credentials contain secrets

- name: Display client credentials (WARNING: Contains secrets!)
  debug:
    msg:
      - "Client ID: {{ service_account.client_id }}"
      - "Client Secret: {{ service_account.client_secret }}"
      - "SAVE THESE CREDENTIALS NOW - Secret cannot be retrieved later!"

- name: Create service account with credential file output
  globus_auth:
    resource_type: client
    name: "Automation Service Account"
    project_id: "abc123-def456-ghi789"
    client_type: "confidential_client"
    redirect_uris:
      - "https://myapp.example.com/callback"
    credential_output_file: "/secure/path/client-credentials.json"
    state: present
  register: service_account

- name: Create thick client (public installed client)
  globus_auth:
    resource_type: client
    name: "Desktop Application"
    project_id: "abc123-def456-ghi789"
    client_type: "public_installed_client"
    redirect_uris:
      - "https://auth.globus.org/v2/web/auth-code"
    visibility: "public"
    state: present

- name: Create client identity for automation
  globus_auth:
    resource_type: client
    name: "CI/CD Pipeline"
    project_id: "abc123-def456-ghi789"
    client_type: "client_identity"
    state: present

# NOTE: Client deletion requires high-assurance authentication (MFA within 30 min)
# and must be done manually at https://app.globus.org/settings/developers
# state: absent is not supported for OAuth clients

# Combined workflow
- name: Create project with policy
  block:
    - name: Create project
      globus_auth:
        resource_type: project
        name: "Secure Research Project"
        contact_email: "admin@university.edu"
        description: "High-security research collaboration"
        admin_ids:
          - "ae341a98-d274-11e5-b888-dbae3a8ba545"
        state: present
      register: project

    - name: Create security policy for project
      globus_auth:
        resource_type: policy
        project_id: "{{ project.resource_id }}"
        name: "Strict Security Policy"
        description: "High assurance with domain restrictions"
        high_assurance: true
        authentication_assurance_timeout: 1800
        domain_constraints_include:
          - "university.edu"
        state: present
"""

RETURN = r"""
resource_id:
    description: ID of the created/managed resource
    type: str
    returned: when state=present
resource_type:
    description: Type of resource (project, policy, or client)
    type: str
    returned: always
name:
    description: Name of the resource
    type: str
    returned: always
project_id:
    description: Associated project ID (for policies and clients)
    type: str
    returned: when resource_type in [policy, client]
client_id:
    description: OAuth client ID (for clients)
    type: str
    returned: when resource_type=client and state=present
client_secret:
    description: OAuth client secret (for confidential clients)
    type: str
    returned: when resource_type=client and state=present and client has secret
client_credentials:
    description: Complete client credentials in multiple formats
    type: dict
    returned: when resource_type=client and state=present
    contains:
        client_id:
            description: OAuth client ID
            type: str
        client_secret:
            description: OAuth client secret (if applicable)
            type: str
        ansible_env:
            description: Ansible environment variable format
            type: str
        shell_export:
            description: Shell export command format
            type: str
        json_file:
            description: Path to saved JSON file (if credential_output_file was specified)
            type: str
warning:
    description: Important warnings about credential management
    type: str
    returned: when resource_type=client and state=present
changed:
    description: Whether the resource was changed
    type: bool
    returned: always
"""

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.community.globus.plugins.module_utils.globus_common import (
    globus_argument_spec,
)
from ansible_collections.community.globus.plugins.module_utils.globus_sdk_client import (
    GlobusSDKClient,
)


# Project functions
def find_project_by_name(api, name):
    """Find a project by display name using SDK."""
    try:
        response = api.auth_client.get_projects()
        projects = (
            response.data.get("projects", [])
            if hasattr(response, "data")
            else response.get("projects", [])
        )

        for project in projects:
            if project.get("display_name") == name:
                project_id = project["id"]
                full_project = api.auth_client.get_project(project_id)
                result = (
                    full_project.data if hasattr(full_project, "data") else full_project
                )
                # Extract the project from the nested structure if present
                if isinstance(result, dict) and "project" in result:
                    return result["project"]
                return result
        return None
    except Exception as e:
        api.handle_api_error(e, f"searching for project '{name}'")


def create_project(api, params):
    """Create a new project using SDK."""
    try:
        project_data = {
            "display_name": params["name"],
        }

        if params.get("contact_email"):
            project_data["contact_email"] = params["contact_email"]

        if params.get("description"):
            project_data["description"] = params["description"]

        response = api.auth_client.create_project(
            display_name=project_data["display_name"],
            contact_email=project_data.get("contact_email"),
            **{"admin_ids": params.get("admin_ids", [])}
            if params.get("admin_ids")
            else {},
        )

        project = response.data if hasattr(response, "data") else response
        project_id = project["project"]["id"]

        if params.get("admin_group_ids"):
            for group_id in params["admin_group_ids"]:
                try:
                    api.auth_client.add_project_admin_group(project_id, group_id)
                except Exception as e:
                    api.module.warn(f"Failed to add admin group {group_id}: {e}")

        return project["project"]

    except Exception as e:
        api.handle_api_error(e, "creating project")


def update_project(api, project_id, params):
    """Update an existing project using SDK."""
    try:
        changed = False
        update_data = {}

        if params.get("name"):
            update_data["display_name"] = params["name"]

        if params.get("contact_email"):
            update_data["contact_email"] = params["contact_email"]

        # SDK v3 doesn't support description in update_project
        # Only add it if we're using SDK v4
        if params.get("description"):
            # Try to update with description (SDK v4)
            # If it fails, update without it (SDK v3)
            try:
                update_with_desc = update_data.copy()
                update_with_desc["description"] = params["description"]
                api.auth_client.update_project(project_id, **update_with_desc)
                changed = True
                update_data = {}  # Clear to avoid duplicate update
            except TypeError:
                # SDK v3 doesn't support description parameter
                pass

        if update_data:
            api.auth_client.update_project(project_id, **update_data)
            changed = True

        if params.get("admin_ids") is not None:
            for admin_id in params["admin_ids"]:
                try:
                    api.auth_client.add_project_admin(project_id, admin_id)
                    changed = True
                except Exception:
                    pass

        if params.get("admin_group_ids") is not None:
            for group_id in params["admin_group_ids"]:
                try:
                    api.auth_client.add_project_admin_group(project_id, group_id)
                    changed = True
                except Exception:
                    pass

        return changed

    except Exception as e:
        # Check if this is a high-assurance auth error (403 FORBIDDEN)
        error_str = str(e)
        if (
            "403" in error_str
            and "FORBIDDEN" in error_str
            and (
                "30 minutes" in error_str or "admin privileges in session" in error_str
            )
        ):
            # High-assurance authentication required - can't update without recent MFA
            # Treat as unchanged rather than failing
            api.module.warn(
                f"Cannot update project {project_id}: requires high-assurance "
                "authentication (MFA within 30 min). Project exists but may not "
                "have latest settings."
            )
            return False
        # For other errors, handle normally
        api.handle_api_error(e, f"updating project {project_id}")


# Project deletion function removed - requires high-assurance auth
# Users must delete projects manually at https://app.globus.org/settings/developers


# Policy functions
def find_policy_by_name(api, project_id, name):
    """Find a policy by display name using SDK."""
    try:
        response = api.auth_client.get_project_policies(project_id)
        policies = (
            response.data.get("policies", [])
            if hasattr(response, "data")
            else response.get("policies", [])
        )

        for policy in policies:
            if policy.get("display_name") == name:
                return policy
        return None
    except Exception as e:
        api.handle_api_error(
            e, f"searching for policy '{name}' in project {project_id}"
        )


def create_policy(api, params):
    """Create a new auth policy using SDK."""
    try:
        policy_data = {
            "project_id": params["project_id"],
        }

        if params.get("name"):
            policy_data["display_name"] = params["name"]

        if params.get("description"):
            policy_data["description"] = params["description"]

        if params.get("high_assurance") is not None:
            policy_data["high_assurance"] = params["high_assurance"]

        if params.get("authentication_assurance_timeout") is not None:
            policy_data["authentication_assurance_timeout"] = params[
                "authentication_assurance_timeout"
            ]

        domain_constraints = {}
        if params.get("domain_constraints_include"):
            domain_constraints["include"] = params["domain_constraints_include"]

        if params.get("domain_constraints_exclude"):
            domain_constraints["exclude"] = params["domain_constraints_exclude"]

        if domain_constraints:
            policy_data["domain_constraints"] = domain_constraints

        response = api.auth_client.create_policy(**policy_data)
        return response.data if hasattr(response, "data") else response

    except Exception as e:
        api.handle_api_error(e, "creating auth policy")


def update_policy(api, policy_id, params):
    """Update an existing auth policy using SDK."""
    try:
        update_data = {}

        if params.get("name"):
            update_data["display_name"] = params["name"]

        if params.get("description"):
            update_data["description"] = params["description"]

        if params.get("high_assurance") is not None:
            update_data["high_assurance"] = params["high_assurance"]

        if params.get("authentication_assurance_timeout") is not None:
            update_data["authentication_assurance_timeout"] = params[
                "authentication_assurance_timeout"
            ]

        domain_constraints = {}
        if params.get("domain_constraints_include") is not None:
            domain_constraints["include"] = params["domain_constraints_include"]

        if params.get("domain_constraints_exclude") is not None:
            domain_constraints["exclude"] = params["domain_constraints_exclude"]

        if domain_constraints:
            update_data["domain_constraints"] = domain_constraints

        if update_data:
            api.auth_client.update_policy(policy_id, **update_data)
            return True

        return False

    except Exception as e:
        api.handle_api_error(e, f"updating auth policy {policy_id}")


def delete_policy(api, policy_id):
    """Delete an auth policy using SDK."""
    try:
        api.auth_client.delete_policy(policy_id)
        return True
    except Exception as e:
        api.handle_api_error(e, f"deleting auth policy {policy_id}")


# Client functions
def find_client_by_name(api, project_id, name):
    """Find a client by name in a project using SDK."""
    try:
        # Check if get_project_clients method exists (SDK v4+)
        if not hasattr(api.auth_client, "get_project_clients"):
            # SDK v3 doesn't have this method
            # We cannot find clients by name efficiently, so return None
            # This means clients must be created with unique names or provide client_id for updates
            return None

        response = api.auth_client.get_project_clients(project_id)
        clients = (
            response.data.get("clients", [])
            if hasattr(response, "data")
            else response.get("clients", [])
        )

        for client in clients:
            if client.get("name") == name:
                client_id = client["id"]
                full_client = api.auth_client.get_client(client_id)
                result = (
                    full_client.data if hasattr(full_client, "data") else full_client
                )
                # Extract the client from nested structure if present
                if isinstance(result, dict) and "client" in result:
                    return result["client"]
                return result
        return None
    except Exception as e:
        api.handle_api_error(
            e, f"searching for client '{name}' in project {project_id}"
        )


def create_client(api, params):
    """Create a new OAuth client using SDK."""
    try:
        import json

        client_data = {
            "project": params["project_id"],
            "name": params["name"],
        }

        # Add client type
        if params.get("client_type"):
            client_data["client_type"] = params["client_type"]

        # Add optional fields
        if params.get("redirect_uris"):
            client_data["redirect_uris"] = params["redirect_uris"]

        # Note: SDK v3 uses client_type to determine public/private
        # SDK v4 uses separate public_client parameter
        # Only set public_client if client_type is not set (SDK v4 style)
        if params.get("visibility") and not params.get("client_type"):
            client_data["public_client"] = params["visibility"] == "public"

        if params.get("terms_and_conditions"):
            client_data["links"] = client_data.get("links", {})
            client_data["links"]["terms_and_conditions"] = params[
                "terms_and_conditions"
            ]

        if params.get("privacy_policy"):
            client_data["links"] = client_data.get("links", {})
            client_data["links"]["privacy_policy"] = params["privacy_policy"]

        if params.get("required_idp"):
            client_data["required_idp"] = params["required_idp"]

        if params.get("preselect_idp"):
            client_data["preselect_idp"] = params["preselect_idp"]

        # Create the client - SDK v3 uses **kwargs, SDK v4 uses data parameter
        try:
            # Try SDK v4 style first
            response = api.auth_client.create_client(data=client_data)
        except TypeError:
            # Fall back to SDK v3 style
            response = api.auth_client.create_client(**client_data)

        client = response.data if hasattr(response, "data") else response

        # Create client credentials (secret) if this is a confidential client type
        client_secret = None
        client_type = params.get("client_type", "confidential_client")

        if client_type in [
            "confidential_client",
            "client_identity",
            "resource_server",
            "globus_connect_server",
            "hybrid_confidential_client_resource_server",
        ]:
            try:
                cred_response = api.auth_client.create_client_credential(
                    client["client"]["id"]
                )
                cred_data = (
                    cred_response.data
                    if hasattr(cred_response, "data")
                    else cred_response
                )
                client_secret = cred_data.get("secret")
            except Exception as e:
                api.module.warn(f"Failed to create client credential: {e}")

        # Format output according to Option 5
        result = {
            "client": client["client"],
            "client_secret": client_secret,
        }

        # Save credentials to file if requested
        if params.get("credential_output_file") and client_secret:
            try:
                output_file = params["credential_output_file"]
                credentials = {
                    "client_id": client["client"]["id"],
                    "client_secret": client_secret,
                    "name": params["name"],
                    "project_id": params["project_id"],
                    "client_type": client_type,
                    "created_at": client["client"].get("created", ""),
                }

                with open(output_file, "w") as f:
                    json.dump(credentials, f, indent=2)

                result["credential_file"] = output_file
            except Exception as e:
                api.module.warn(f"Failed to save credentials to file: {e}")

        return result

    except Exception as e:
        api.handle_api_error(e, "creating client")


def update_client(api, client_id, params):
    """Update an existing OAuth client using SDK."""
    try:
        changed = False
        update_data = {}

        if params.get("name"):
            update_data["name"] = params["name"]

        if params.get("redirect_uris") is not None:
            update_data["redirect_uris"] = params["redirect_uris"]
            changed = True

        if params.get("visibility"):
            update_data["public_client"] = params["visibility"] == "public"
            changed = True

        if params.get("terms_and_conditions") or params.get("privacy_policy"):
            update_data["links"] = {}
            if params.get("terms_and_conditions"):
                update_data["links"]["terms_and_conditions"] = params[
                    "terms_and_conditions"
                ]
            if params.get("privacy_policy"):
                update_data["links"]["privacy_policy"] = params["privacy_policy"]
            changed = True

        if update_data:
            # SDK v3 uses **kwargs, SDK v4 uses data parameter
            try:
                api.auth_client.update_client(client_id, data=update_data)
            except TypeError:
                api.auth_client.update_client(client_id, **update_data)
            return True

        return changed

    except Exception as e:
        api.handle_api_error(e, f"updating client {client_id}")


# Client deletion function removed - requires high-assurance auth
# Users must delete OAuth clients manually at https://app.globus.org/settings/developers


def main():
    argument_spec = globus_argument_spec()
    argument_spec.update(
        resource_type={
            "type": "str",
            "required": True,
            "choices": ["project", "policy", "client"],
        },
        name={"type": "str", "required": True},
        resource_id={"type": "str"},
        project_id={"type": "str"},
        # Project-specific parameters
        contact_email={"type": "str"},
        description={"type": "str"},
        admin_ids={"type": "list", "elements": "str"},
        admin_group_ids={"type": "list", "elements": "str"},
        # Policy-specific parameters
        high_assurance={"type": "bool", "default": False},
        authentication_assurance_timeout={"type": "int"},
        domain_constraints_include={"type": "list", "elements": "str"},
        domain_constraints_exclude={"type": "list", "elements": "str"},
        # Client-specific parameters
        client_type={
            "type": "str",
            "choices": [
                "confidential_client",
                "public_installed_client",
                "client_identity",
                "resource_server",
                "globus_connect_server",
                "hybrid_confidential_client_resource_server",
            ],
        },
        redirect_uris={"type": "list", "elements": "str"},
        visibility={
            "type": "str",
            "choices": ["public", "private"],
            "default": "private",
        },
        terms_and_conditions={"type": "str"},
        privacy_policy={"type": "str"},
        required_idp={"type": "str"},
        preselect_idp={"type": "str"},
        credential_output_file={"type": "path"},
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_if=[
            ("resource_type", "policy", ("project_id",)),
            ("resource_type", "client", ("project_id", "client_type")),
        ],
    )

    api = GlobusSDKClient(module, required_services=["auth"])

    resource_type = module.params["resource_type"]
    name = module.params["name"]
    state = module.params["state"]
    resource_id = module.params.get("resource_id")

    # Handle projects
    if resource_type == "project":
        # Find existing project
        if resource_id:
            try:
                response = api.auth_client.get_project(resource_id)
                existing = response.data if hasattr(response, "data") else response
            except Exception:
                existing = None
        else:
            existing = find_project_by_name(api, name)

        if state == "present":
            if existing:
                if module.check_mode:
                    module.exit_json(changed=False, resource_type="project", name=name)

                resource_id = existing["id"]
                changed = update_project(api, resource_id, module.params)

                module.exit_json(
                    changed=changed,
                    resource_id=resource_id,
                    resource_type="project",
                    name=name,
                )
            else:
                if module.check_mode:
                    module.exit_json(changed=True, resource_type="project", name=name)

                project = create_project(api, module.params)
                module.exit_json(
                    changed=True,
                    resource_id=project["id"],
                    resource_type="project",
                    name=name,
                )

        elif state == "absent":
            module.fail_json(
                msg=(
                    "Deleting projects requires high-assurance authentication (MFA within 30 minutes) "
                    "and is not supported via Ansible. Please delete this project manually:\n"
                    "1. Go to https://app.globus.org/settings/developers\n"
                    "2. Select your project\n"
                    "3. Use the 'Delete Project' option\n\n"
                    f"Project name: {name}\n"
                    f"Project ID: {existing['id'] if existing else 'not found'}"
                )
            )

    # Handle policies
    elif resource_type == "policy":
        project_id = module.params["project_id"]

        # Find existing policy
        if resource_id:
            try:
                response = api.auth_client.get_policy(resource_id)
                existing = response.data if hasattr(response, "data") else response
            except Exception:
                existing = None
        else:
            existing = find_policy_by_name(api, project_id, name)

        if state == "present":
            if existing:
                if module.check_mode:
                    module.exit_json(
                        changed=False,
                        resource_type="policy",
                        name=name,
                        project_id=project_id,
                    )

                resource_id = existing["id"]
                changed = update_policy(api, resource_id, module.params)

                module.exit_json(
                    changed=changed,
                    resource_id=resource_id,
                    resource_type="policy",
                    name=name,
                    project_id=project_id,
                )
            else:
                if module.check_mode:
                    module.exit_json(
                        changed=True,
                        resource_type="policy",
                        name=name,
                        project_id=project_id,
                    )

                policy = create_policy(api, module.params)
                module.exit_json(
                    changed=True,
                    resource_id=policy["id"],
                    resource_type="policy",
                    name=name,
                    project_id=project_id,
                )

        elif state == "absent":
            if existing:
                if module.check_mode:
                    module.exit_json(
                        changed=True,
                        resource_type="policy",
                        name=name,
                        project_id=project_id,
                    )

                delete_policy(api, existing["id"])
                module.exit_json(
                    changed=True,
                    resource_type="policy",
                    name=name,
                    project_id=project_id,
                )
            else:
                module.exit_json(
                    changed=False,
                    resource_type="policy",
                    name=name,
                    project_id=project_id,
                )

    # Handle clients
    elif resource_type == "client":
        project_id = module.params["project_id"]

        # Find existing client
        if resource_id:
            try:
                response = api.auth_client.get_client(resource_id)
                existing = response.data if hasattr(response, "data") else response
            except Exception:
                existing = None
        else:
            existing = find_client_by_name(api, project_id, name)

        if state == "present":
            if existing:
                # Update existing client
                if module.check_mode:
                    module.exit_json(
                        changed=False,
                        resource_type="client",
                        name=name,
                        project_id=project_id,
                    )

                resource_id = existing["id"]
                changed = update_client(api, resource_id, module.params)

                module.exit_json(
                    changed=changed,
                    resource_id=resource_id,
                    client_id=resource_id,
                    resource_type="client",
                    name=name,
                    project_id=project_id,
                )
            else:
                # Create new client
                if module.check_mode:
                    module.exit_json(
                        changed=True,
                        resource_type="client",
                        name=name,
                        project_id=project_id,
                    )

                result = create_client(api, module.params)
                client = result["client"]
                client_secret = result.get("client_secret")

                # Prepare Option 5 output format
                response = {
                    "changed": True,
                    "resource_id": client["id"],
                    "client_id": client["id"],
                    "resource_type": "client",
                    "name": name,
                    "project_id": project_id,
                }

                # Add client credentials in multiple formats
                if client_secret:
                    response["client_secret"] = client_secret
                    response["client_credentials"] = {
                        "client_id": client["id"],
                        "client_secret": client_secret,
                        "ansible_env": f"GLOBUS_CLIENT_ID={client['id']}\nGLOBUS_CLIENT_SECRET={client_secret}",
                        "shell_export": f"export GLOBUS_CLIENT_ID={client['id']}\nexport GLOBUS_CLIENT_SECRET={client_secret}",
                    }

                    # Add file path if credentials were saved
                    if result.get("credential_file"):
                        response["client_credentials"]["json_file"] = result[
                            "credential_file"
                        ]

                    # Add warning about one-time secret retrieval
                    response["warning"] = (
                        "IMPORTANT: The client_secret can only be retrieved once. "
                        "Save these credentials immediately in a secure location. "
                        "If you lose the secret, you will need to delete this client and create a new one."
                    )

                module.exit_json(**response)

        elif state == "absent":
            module.fail_json(
                msg=(
                    "Deleting OAuth clients requires high-assurance authentication (MFA within 30 minutes) "
                    "and is not supported via Ansible. Please delete this client manually:\n"
                    "1. Go to https://app.globus.org/settings/developers\n"
                    "2. Select your project\n"
                    "3. Navigate to the 'Apps' tab\n"
                    "4. Select your client and choose 'Delete'\n\n"
                    f"Client name: {name}\n"
                    f"Client ID: {existing['id'] if existing else 'not found'}\n"
                    f"Project ID: {project_id}"
                )
            )


if __name__ == "__main__":
    main()
