#!/usr/bin/python

DOCUMENTATION = r"""
---
module: globus_compute
short_description: Manage Globus Compute Endpoints
description:
    - Create, update, or delete Globus Compute Endpoints
    - Configure compute endpoint settings and executors
version_added: "1.0.0"
author:
    - Ansible Globus Module Contributors
options:
    name:
        description: Name of the compute endpoint
        required: true
        type: str
    endpoint_id:
        description: UUID of the endpoint (for updates)
        required: false
        type: str
    description:
        description: Description of the compute endpoint
        required: false
        type: str
    public:
        description: Whether the endpoint should be public
        required: false
        type: bool
        default: false
    executor_type:
        description: Type of executor to use
        required: false
        type: str
        choices: ['HighThroughputExecutor', 'ThreadPoolExecutor', 'ProcessPoolExecutor']
        default: 'HighThroughputExecutor'
    max_workers:
        description: Maximum number of workers
        required: false
        type: int
        default: 1
    worker_init:
        description: Worker initialization script
        required: false
        type: str
    conda_env:
        description: Conda environment to use
        required: false
        type: str
    provider:
        description: Provider configuration
        required: false
        type: dict
    state:
        description: Desired state of the compute endpoint
        required: false
        type: str
        choices: ['present', 'absent']
        default: 'present'
extends_documentation_fragment:
    - globus_auth
"""

EXAMPLES = r"""
- name: Create a Globus Compute endpoint
  globus_compute:
    name: "research-cluster"
    description: "Research cluster compute endpoint"
    public: false
    executor_type: "HighThroughputExecutor"
    max_workers: 4
    conda_env: "my-env"
    provider:
      type: "LocalProvider"
      init_blocks: 1
      max_blocks: 2
    state: present

- name: Delete a compute endpoint
  globus_compute:
    name: "old-endpoint"
    state: absent
"""

RETURN = r"""
endpoint_id:
    description: ID of the created/managed compute endpoint
    type: str
    returned: when state=present
name:
    description: Name of the compute endpoint
    type: str
    returned: always
changed:
    description: Whether the endpoint was changed
    type: bool
    returned: always
"""

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.m1yag1.globus.plugins.module_utils.globus_api import (
    GlobusAPI,
)
from ansible_collections.m1yag1.globus.plugins.module_utils.globus_common import (
    globus_argument_spec,
)


def find_compute_endpoint_by_name(api, name):
    """Find a compute endpoint by name."""
    try:
        endpoints = api.get("endpoints")
        for endpoint in endpoints.get("endpoints", []):
            if endpoint["name"] == name:
                return endpoint
        return None
    except Exception:
        return None


def generate_endpoint_config(params):
    """Generate endpoint configuration from parameters."""
    config = {
        "engine": {
            "type": "GlobusComputeEngine",
            "max_workers_per_node": params.get("max_workers", 1),
            "worker_init": params.get("worker_init", ""),
        },
        "executors": [
            {
                "label": "default",
                "type": params.get("executor_type", "HighThroughputExecutor"),
                "max_workers": params.get("max_workers", 1),
            }
        ],
    }

    # Add conda environment if specified
    if params.get("conda_env"):
        config["engine"]["conda_env"] = params["conda_env"]

    # Add provider configuration if specified
    if params.get("provider"):
        config["executors"][0]["provider"] = params["provider"]

    return config


def create_compute_endpoint(api, params):
    """Create a new compute endpoint."""
    config = generate_endpoint_config(params)

    endpoint_data = {
        "endpoint_name": params["name"],
        "description": params.get("description", ""),
        "public": params.get("public", False),
        "config": config,
    }

    result = api.post("endpoints", endpoint_data)
    return result


def update_compute_endpoint(api, endpoint_id, params):
    """Update an existing compute endpoint."""
    endpoint_data = {}

    if params.get("description") is not None:
        endpoint_data["description"] = params["description"]
    if params.get("public") is not None:
        endpoint_data["public"] = params["public"]

    # Update configuration if any compute-related params are provided
    compute_params = [
        "executor_type",
        "max_workers",
        "worker_init",
        "conda_env",
        "provider",
    ]
    if any(params.get(p) is not None for p in compute_params):
        endpoint_data["config"] = generate_endpoint_config(params)

    if endpoint_data:
        result = api.put(f"endpoints/{endpoint_id}", endpoint_data)
        return result
    return None


def delete_compute_endpoint(api, endpoint_id):
    """Delete a compute endpoint."""
    api.delete(f"endpoints/{endpoint_id}")
    return True


def start_endpoint(api, endpoint_id):
    """Start a compute endpoint."""
    result = api.post(f"endpoints/{endpoint_id}/start")
    return result


def stop_endpoint(api, endpoint_id):
    """Stop a compute endpoint."""
    result = api.post(f"endpoints/{endpoint_id}/stop")
    return result


def main():
    argument_spec = globus_argument_spec()
    argument_spec.update(
        name={"type": "str", "required": True},
        endpoint_id={"type": "str"},
        description={"type": "str"},
        public={"type": "bool", "default": False},
        executor_type={
            "type": "str",
            "choices": [
                "HighThroughputExecutor",
                "ThreadPoolExecutor",
                "ProcessPoolExecutor",
            ],
            "default": "HighThroughputExecutor",
        },
        max_workers={"type": "int", "default": 1},
        worker_init={"type": "str"},
        conda_env={"type": "str"},
        provider={"type": "dict"},
        endpoint_state={"type": "str", "choices": ["started", "stopped"]},
    )

    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)

    api = GlobusAPI(module, service="compute")

    name = module.params["name"]
    state = module.params["state"]
    endpoint_state = module.params.get("endpoint_state")

    existing_endpoint = find_compute_endpoint_by_name(api, name)

    if state == "present":
        if existing_endpoint:
            # Update existing endpoint
            changed = False
            endpoint_id = existing_endpoint["uuid"]

            # Update endpoint properties
            update_result = update_compute_endpoint(api, endpoint_id, module.params)
            if update_result:
                changed = True

            # Handle endpoint state changes
            if endpoint_state:
                current_state = existing_endpoint.get("status", "stopped").lower()
                if endpoint_state == "started" and current_state != "online":
                    start_endpoint(api, endpoint_id)
                    changed = True
                elif endpoint_state == "stopped" and current_state == "online":
                    stop_endpoint(api, endpoint_id)
                    changed = True

            module.exit_json(changed=changed, endpoint_id=endpoint_id, name=name)
        else:
            # Create new endpoint
            if module.check_mode:
                module.exit_json(changed=True, name=name)

            endpoint = create_compute_endpoint(api, module.params)
            endpoint_id = endpoint["endpoint_id"]

            # Start endpoint if requested
            if endpoint_state == "started":
                start_endpoint(api, endpoint_id)

            module.exit_json(changed=True, endpoint_id=endpoint_id, name=name)

    elif state == "absent":
        if existing_endpoint:
            if module.check_mode:
                module.exit_json(changed=True, name=name)

            # Stop endpoint before deletion
            endpoint_id = existing_endpoint["uuid"]
            if existing_endpoint.get("status", "").lower() == "online":
                stop_endpoint(api, endpoint_id)

            delete_compute_endpoint(api, endpoint_id)
            module.exit_json(changed=True, name=name)
        else:
            module.exit_json(changed=False, name=name)


if __name__ == "__main__":
    main()
