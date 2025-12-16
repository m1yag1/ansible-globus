#!/usr/bin/python

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.m1yag1.globus.plugins.module_utils.globus_common import (
    globus_argument_spec,
)
from ansible_collections.m1yag1.globus.plugins.module_utils.globus_sdk_client import (
    GlobusSDKClient,
)

DOCUMENTATION = r"""
---
module: globus_endpoint
short_description: Manage Globus Endpoints
description:
    - Create, update, or delete Globus Endpoints
    - Configure endpoint settings and authentication
version_added: "1.0.0"
author:
    - m1yag1
options:
    name:
        description: Display name of the endpoint
        required: true
        type: str
    description:
        description: Description of the endpoint
        required: false
        type: str
    organization:
        description: Organization name
        required: false
        type: str
    contact_email:
        description: Contact email for the endpoint
        required: false
        type: str
    endpoint_type:
        description: Type of endpoint
        required: false
        type: str
        choices: ['personal', 'shared', 'server']
        default: 'personal'
    public:
        description: Whether the endpoint should be public
        required: false
        type: bool
        default: false
    subscription_id:
        description: Subscription ID for managed endpoints
        required: false
        type: str
    network_use:
        description: Network usage setting
        required: false
        type: str
        choices: ['normal', 'minimal', 'aggressive']
        default: 'normal'
    state:
        description: Desired state of the endpoint
        required: false
        type: str
        choices: ['present', 'absent']
        default: 'present'
extends_documentation_fragment:
    - m1yag1.globus.globus_auth
"""

EXAMPLES = r"""
# Basic endpoint creation
- name: Create a Globus endpoint
  globus_endpoint:
    name: "My Research Endpoint"
    description: "Data endpoint for research project"
    organization: "University Research Lab"
    contact_email: "admin@university.edu"
    endpoint_type: "server"
    public: true
    state: present

# High-performance research endpoint
- name: Create high-performance research data endpoint
  globus_endpoint:
    name: "Research Data Server"
    description: "High-performance data transfer endpoint for genomics research"
    organization: "University Research Computing"
    contact_email: "admin@university.edu"
    endpoint_type: server
    hostname: "data.university.edu"
    public: true
    network_use: aggressive
    state: present

# Personal endpoint for individual researchers
- name: Create personal research endpoint
  globus_endpoint:
    name: "{{ ansible_user }}-personal"
    description: "Personal endpoint for {{ ansible_user }}"
    organization: "University"
    contact_email: "{{ ansible_user }}@university.edu"
    endpoint_type: personal
    public: false
    state: present

# Multi-institutional collaboration endpoint
- name: Create collaboration endpoint
  globus_endpoint:
    name: "Multi-Inst-Collab"
    description: "Multi-institutional genomics collaboration endpoint"
    organization: "Research Consortium"
    contact_email: "consortium-admin@universities.org"
    endpoint_type: server
    public: false  # Private for consortium members only
    network_use: aggressive
    state: present
  register: collab_endpoint

# Using service credentials
- name: Create endpoint with service credentials
  globus_endpoint:
    name: "Production Endpoint"
    description: "Production data transfer endpoint"
    organization: "Research Computing"
    contact_email: "support@university.edu"
    endpoint_type: server
    public: true
    client_id: "{{ vault_globus_client_id }}"
    client_secret: "{{ vault_globus_client_secret }}"
    state: present

# GCS deployment automation
- name: Create GCS endpoint with dynamic naming
  globus_endpoint:
    name: "{{ ansible_hostname }}-gcs"
    description: "GCS endpoint for {{ ansible_hostname }}"
    organization: "{{ organization_name }}"
    contact_email: "{{ admin_email }}"
    endpoint_type: server
    hostname: "{{ ansible_fqdn }}"
    public: true
    network_use: normal
    state: present
  delegate_to: localhost

# Delete an endpoint
- name: Delete an endpoint
  globus_endpoint:
    name: "Old Endpoint"
    state: absent
"""

RETURN = r"""
endpoint_id:
    description: ID of the created/managed endpoint
    type: str
    returned: when state=present
name:
    description: Name of the endpoint
    type: str
    returned: always
changed:
    description: Whether the endpoint was changed
    type: bool
    returned: always
"""


def find_endpoint_by_name(api, name):
    """Find an endpoint by name."""
    try:
        endpoints = api.get("endpoint_search", params={"filter_fulltext": name})
        for endpoint in endpoints.get("DATA", []):
            if endpoint["display_name"] == name:
                return endpoint
        return None
    except Exception:
        return None


def create_endpoint(api, params):
    """Create a new endpoint."""
    endpoint_data = {
        "display_name": params["name"],
        "description": params.get("description", ""),
        "organization": params.get("organization", ""),
        "contact_email": params.get("contact_email", ""),
        "public": params.get("public", False),
        "network_use": params.get("network_use", "normal"),
    }

    # Remove empty values
    endpoint_data = {k: v for k, v in endpoint_data.items() if v}

    result = api.post("endpoint", endpoint_data)
    return result


def update_endpoint(api, endpoint_id, params):
    """Update an existing endpoint."""
    endpoint_data = {}

    if params.get("description") is not None:
        endpoint_data["description"] = params["description"]
    if params.get("organization") is not None:
        endpoint_data["organization"] = params["organization"]
    if params.get("contact_email") is not None:
        endpoint_data["contact_email"] = params["contact_email"]
    if params.get("public") is not None:
        endpoint_data["public"] = params["public"]
    if params.get("network_use") is not None:
        endpoint_data["network_use"] = params["network_use"]

    if endpoint_data:
        result = api.put(f"endpoint/{endpoint_id}", endpoint_data)
        return result
    return None


def delete_endpoint(api, endpoint_id):
    """Delete an endpoint."""
    api.delete(f"endpoint/{endpoint_id}")
    return True


def setup_gcs_endpoint(api, endpoint_id, params):
    """Setup Globus Connect Server endpoint configuration."""
    if params.get("endpoint_type") == "server":
        # Configure server-specific settings
        server_config = {
            "DATA_TYPE": "server",
            "hostname": params.get("hostname"),
            "port": params.get("port", 2811),
            "scheme": params.get("scheme", "gsiftp"),
        }

        # Remove None values
        server_config = {k: v for k, v in server_config.items() if v is not None}

        if len(server_config) > 1:  # More than just DATA_TYPE
            api.post(f"endpoint/{endpoint_id}/server", server_config)

    return True


def main():
    argument_spec = globus_argument_spec()
    argument_spec.update(
        name={"type": "str", "required": True},
        description={"type": "str"},
        organization={"type": "str"},
        contact_email={"type": "str"},
        endpoint_type={
            "type": "str",
            "choices": ["personal", "shared", "server"],
            "default": "personal",
        },
        public={"type": "bool", "default": False},
        subscription_id={"type": "str"},
        network_use={
            "type": "str",
            "choices": ["normal", "minimal", "aggressive"],
            "default": "normal",
        },
        hostname={"type": "str"},
        port={"type": "int", "default": 2811},
        scheme={
            "type": "str",
            "choices": ["gsiftp", "ftp", "ssh"],
            "default": "gsiftp",
        },
    )

    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)

    # Only request transfer scope since this module only manages endpoints
    api = GlobusSDKClient(module, required_services=["transfer"])

    name = module.params["name"]
    state = module.params["state"]

    existing_endpoint = find_endpoint_by_name(api, name)

    if state == "present":
        if existing_endpoint:
            # Update existing endpoint
            changed = False
            endpoint_id = existing_endpoint["id"]

            # Update endpoint properties
            update_result = update_endpoint(api, endpoint_id, module.params)
            if update_result:
                changed = True

            # Setup GCS configuration if needed
            if module.params.get("endpoint_type") == "server":
                setup_gcs_endpoint(api, endpoint_id, module.params)
                changed = True

            module.exit_json(changed=changed, endpoint_id=endpoint_id, name=name)
        else:
            # Create new endpoint
            if module.check_mode:
                module.exit_json(changed=True, name=name)

            endpoint = create_endpoint(api, module.params)
            endpoint_id = endpoint["id"]

            # Setup GCS configuration if needed
            setup_gcs_endpoint(api, endpoint_id, module.params)

            module.exit_json(changed=True, endpoint_id=endpoint_id, name=name)

    elif state == "absent":
        if existing_endpoint:
            if module.check_mode:
                module.exit_json(changed=True, name=name)

            delete_endpoint(api, existing_endpoint["id"])
            module.exit_json(changed=True, name=name)
        else:
            module.exit_json(changed=False, name=name)


if __name__ == "__main__":
    main()
