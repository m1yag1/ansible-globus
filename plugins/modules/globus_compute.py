#!/usr/bin/python

DOCUMENTATION = r"""
---
module: globus_compute
short_description: Manage Globus Compute Endpoints and Functions
description:
    - Create, update, or delete Globus Compute Endpoints
    - Register and manage Globus Compute Functions
    - Configure compute endpoint settings and executors
    - Support for High Assurance endpoints and functions
    - System-level multi-user endpoint management (setup/teardown)
version_added: "1.0.0"
author:
    - Ansible Globus Module Contributors
options:
    resource_type:
        description: Type of resource to manage
        required: false
        type: str
        choices: ['endpoint', 'function']
        default: 'endpoint'
    name:
        description: Name of the compute endpoint or function
        required: true
        type: str
    endpoint_id:
        description: UUID of the endpoint (for updates or function registration)
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
    subscription_id:
        description: Globus subscription ID for HA endpoints
        required: false
        type: str
    high_assurance:
        description: Enable high assurance for this endpoint
        required: false
        type: bool
        default: false
    authentication_policy_id:
        description: Authentication policy ID for HA endpoints
        required: false
        type: str
    function_code:
        description: Python function code as a string (for resource_type=function)
        required: false
        type: str
    function_file:
        description: Path to Python file containing the function (for resource_type=function)
        required: false
        type: str
    function_id:
        description: UUID of the function (for updates/deletes)
        required: false
        type: str
    manage_system:
        description: Manage system-level multi-user endpoint (not just API registration)
        required: false
        type: bool
        default: false
    globus_venv_path:
        description: Path to Globus virtualenv (for system-level management)
        required: false
        type: str
        default: '/opt/globus-venv'
    endpoint_root:
        description: Root directory for endpoint configurations (for system-level management)
        required: false
        type: str
        default: '/root/.globus_compute'
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

- name: Create a High Assurance Compute endpoint
  globus_compute:
    resource_type: endpoint
    name: "ha-endpoint"
    description: "High assurance compute endpoint"
    public: false
    subscription_id: "923ac990-9914-11ed-af9f-c53a64a5b6b4"
    high_assurance: true
    authentication_policy_id: "{{ auth_policy_id }}"
    executor_type: "HighThroughputExecutor"
    max_workers: 2
    state: present

- name: Register a function on HA endpoint
  globus_compute:
    resource_type: function
    name: "my_test_function"
    endpoint_id: "{{ ha_endpoint_id }}"
    description: "Test function for HA endpoint"
    function_code: |
      def my_test_function(x):
          return x * 2
    state: present

- name: Register function from file
  globus_compute:
    resource_type: function
    name: "data_processor"
    endpoint_id: "{{ endpoint_id }}"
    function_file: "/path/to/function.py"
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
    returned: when state=present and resource_type=endpoint
function_id:
    description: ID of the registered function
    type: str
    returned: when state=present and resource_type=function
name:
    description: Name of the compute endpoint or function
    type: str
    returned: always
changed:
    description: Whether the resource was changed
    type: bool
    returned: always
"""

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.m1yag1.globus.plugins.module_utils.globus_common import (
    globus_argument_spec,
)
from ansible_collections.m1yag1.globus.plugins.module_utils.globus_sdk_client import (
    GlobusSDKClient,
)


def find_compute_endpoint_by_name(api, name):
    """Find a compute endpoint by name."""
    try:
        response = api.compute_client.list_endpoints()
        endpoints_data = response.data if hasattr(response, "data") else response
        for endpoint in endpoints_data.get("endpoints", []):
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

    # Add HA configuration if specified
    if params.get("subscription_id"):
        config["subscription_id"] = params["subscription_id"]

    if params.get("high_assurance"):
        config["high_assurance"] = True

    if params.get("authentication_policy_id"):
        config["authentication_policy"] = params["authentication_policy_id"]

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


def find_function_by_name(api, name):
    """Find a function by name."""
    try:
        response = api.compute_client.list_functions()
        functions_data = response.data if hasattr(response, "data") else response
        for function in functions_data.get("functions", []):
            if function.get("function_name") == name:
                return function
        return None
    except Exception:
        return None


def register_function(api, params):
    """Register a Globus Compute function."""
    import base64

    # Get function code from either function_code or function_file
    function_code = params.get("function_code")
    if not function_code and params.get("function_file"):
        with open(params["function_file"]) as f:
            function_code = f.read()

    if not function_code:
        raise ValueError("Either function_code or function_file must be provided")

    # Encode function code
    encoded_function = base64.b64encode(function_code.encode()).decode()

    function_data = {
        "function_name": params["name"],
        "function_code": encoded_function,
        "description": params.get("description", ""),
        "public": params.get("public", False),
    }

    # For HA endpoints, the endpoint_id becomes the ha_endpoint_id
    if params.get("endpoint_id"):
        # Check if endpoint is HA by looking at subscription_id or high_assurance params
        if params.get("high_assurance") or params.get("subscription_id"):
            function_data["ha_endpoint_id"] = params["endpoint_id"]
        else:
            function_data["endpoint_id"] = params["endpoint_id"]

    response = api.compute_client.register_function(function_data)
    result_data = response.data if hasattr(response, "data") else response
    return result_data


def delete_function(api, function_id):
    """Delete a Globus Compute function."""
    api.delete(f"functions/{function_id}")
    return True


def setup_system_endpoint(module, params):
    """Setup system-level multi-user endpoint."""
    import json
    import os
    import subprocess

    name = params["name"]
    endpoint_root = params["endpoint_root"]
    globus_venv_path = params["globus_venv_path"]
    display_name = params.get("display_name", name)
    subscription_id = params.get("subscription_id")
    client_id = params.get("client_id") or os.environ.get("GLOBUS_COMPUTE_CLIENT_ID")
    client_secret = params.get("client_secret") or os.environ.get(
        "GLOBUS_COMPUTE_CLIENT_SECRET"
    )
    globus_sdk_environment = params.get("globus_sdk_environment") or os.environ.get(
        "GLOBUS_SDK_ENVIRONMENT", "production"
    )

    changed = False
    endpoint_dir = os.path.join(endpoint_root, name)
    config_file = os.path.join(endpoint_dir, "config.yaml")
    service_name = f"globus-compute-endpoint-{name}"
    service_file = f"/etc/systemd/system/{service_name}.service"

    # Validate required parameters
    if not subscription_id:
        module.fail_json(
            msg="subscription_id is required for system-level endpoint setup"
        )
    if not client_id or not client_secret:
        module.fail_json(
            msg="client_id and client_secret are required (set via params or GLOBUS_COMPUTE_CLIENT_ID/GLOBUS_COMPUTE_CLIENT_SECRET)"
        )

    # Create virtualenv if it doesn't exist
    if not os.path.exists(os.path.join(globus_venv_path, "bin", "python")):
        try:
            subprocess.run(
                ["python3", "-m", "venv", globus_venv_path],
                check=True,
                capture_output=True,
                text=True,
            )
            changed = True
        except subprocess.CalledProcessError as e:
            module.fail_json(msg=f"Failed to create virtualenv: {e.stderr}")

    # Install globus-compute-endpoint in virtualenv
    pip_path = os.path.join(globus_venv_path, "bin", "pip")
    try:
        result = subprocess.run(
            [pip_path, "show", "globus-compute-endpoint"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            # Not installed, install it
            subprocess.run(
                [pip_path, "install", "globus-compute-endpoint"],
                check=True,
                capture_output=True,
                text=True,
            )
            changed = True
    except subprocess.CalledProcessError as e:
        module.fail_json(msg=f"Failed to install globus-compute-endpoint: {e.stderr}")

    # Ensure art user exists for identity mapping
    try:
        import pwd

        try:
            pwd.getpwnam("art")
        except KeyError:
            # User doesn't exist, create it
            subprocess.run(
                ["useradd", "-m", "-s", "/bin/bash", "art"],
                check=True,
                capture_output=True,
                text=True,
            )
            changed = True
    except subprocess.CalledProcessError as e:
        module.fail_json(msg=f"Failed to create art user: {e.stderr}")

    if not os.path.exists(config_file):
        # Before creating a new endpoint, check if any endpoints with this display name exist
        # in the API and delete them to ensure uniqueness
        try:
            api = GlobusSDKClient(module, required_services=["compute"])
            # Find any existing endpoints with the same display name
            existing_endpoint = find_compute_endpoint_by_name(api, display_name)
            if existing_endpoint:
                endpoint_id = existing_endpoint["uuid"]
                module.warn(
                    f"Found existing endpoint '{display_name}' ({endpoint_id}) in API. Deleting before creating new one."
                )
                delete_compute_endpoint(api, endpoint_id)
        except Exception as e:
            module.warn(f"Could not check for existing endpoints: {e}")

        gce_path = os.path.join(globus_venv_path, "bin", "globus-compute-endpoint")
        try:
            subprocess.run(
                [
                    gce_path,
                    "configure",
                    name,
                    "--multi-user=true",
                    f"--subscription-id={subscription_id}",
                    f"--display-name={display_name}",
                ],
                check=True,
                capture_output=True,
                text=True,
                cwd=endpoint_root,
            )
            changed = True
        except subprocess.CalledProcessError as e:
            module.fail_json(msg=f"Failed to configure endpoint: {e.stderr}")

    identity_mapping_file = os.path.join(endpoint_dir, "identity_mapping.json")
    identity_mapping = [
        {
            "DATA_TYPE": "expression_identity_mapping#1.0.0",
            "mappings": [
                {
                    "source": "{username}",
                    "match": "art@globusid\\.org",
                    "output": "art",
                },
                {"source": "{id}", "match": client_id, "output": "ubuntu"},
                {"source": "{username}", "match": "(.*@.*", "output": "{0}"},
            ],
        }
    ]

    # Write identity mapping file
    try:
        with open(identity_mapping_file, "w") as f:
            json.dump(identity_mapping, f, indent=2)
        changed = True
    except OSError as e:
        module.fail_json(msg=f"Failed to write identity mapping file: {str(e)}")

    try:
        with open(config_file) as f:
            config_content = f.read()

        if (
            "identity_mapping_config_path:" not in config_content
            or identity_mapping_file not in config_content
        ):
            # Update the path
            import re

            config_content = re.sub(
                r"identity_mapping_config_path:.*",
                f"identity_mapping_config_path: {identity_mapping_file}",
                config_content,
            )

            with open(config_file, "w") as f:
                f.write(config_content)
            changed = True
    except OSError as e:
        module.fail_json(msg=f"Failed to update config file: {str(e)}")

    try:
        with open(config_file) as f:
            config_content = f.read()

        if "admins:" not in config_content:
            # Add admins section
            admin_config = "\nadmins:\n  # art@globusid.org\n  - 6f7853a0-6ba7-425f-ba1b-000c209e15b1\n"
            config_content += admin_config

            with open(config_file, "w") as f:
                f.write(config_content)
            changed = True
    except OSError as e:
        module.fail_json(msg=f"Failed to add admins to config: {str(e)}")

    service_content = f"""[Unit]
Description=Globus Compute Endpoint - {name}
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory={endpoint_root}
Environment="GLOBUS_COMPUTE_CLIENT_ID={client_id}"
Environment="GLOBUS_COMPUTE_CLIENT_SECRET={client_secret}"
Environment="GLOBUS_SDK_ENVIRONMENT={globus_sdk_environment}"
ExecStart={globus_venv_path}/bin/globus-compute-endpoint start {name}
Restart=on-failure

[Install]
WantedBy=multi-user.target
"""

    try:
        # Check if service file exists and has same content
        service_needs_update = True
        if os.path.exists(service_file):
            with open(service_file) as f:
                existing_content = f.read()
            service_needs_update = existing_content != service_content

        if service_needs_update:
            with open(service_file, "w") as f:
                f.write(service_content)
            changed = True

            # Reload systemd daemon
            subprocess.run(
                ["systemctl", "daemon-reload"],
                check=True,
                capture_output=True,
                text=True,
            )
    except OSError as e:
        module.fail_json(msg=f"Failed to write service file: {str(e)}")
    except subprocess.CalledProcessError as e:
        module.fail_json(msg=f"Failed to reload systemd: {e.stderr}")

    try:
        # Check if service is enabled
        result = subprocess.run(
            ["systemctl", "is-enabled", service_name], capture_output=True, text=True
        )
        if result.returncode != 0 or result.stdout.strip() != "enabled":
            subprocess.run(
                ["systemctl", "enable", service_name],
                check=True,
                capture_output=True,
                text=True,
            )
            changed = True

        # Check if service is running
        result = subprocess.run(
            ["systemctl", "is-active", service_name], capture_output=True, text=True
        )
        if result.returncode != 0 or result.stdout.strip() != "active":
            subprocess.run(
                ["systemctl", "start", service_name],
                check=True,
                capture_output=True,
                text=True,
            )
            changed = True
    except subprocess.CalledProcessError as e:
        module.fail_json(msg=f"Failed to enable/start service: {e.stderr}")

    endpoint_json_file = os.path.join(endpoint_dir, "endpoint.json")
    endpoint_id = None
    if os.path.exists(endpoint_json_file):
        try:
            with open(endpoint_json_file) as f:
                endpoint_data = json.load(f)
            endpoint_id = endpoint_data.get("endpoint_id")
        except (OSError, json.JSONDecodeError):
            # Not fatal, just won't return endpoint_id
            pass

    return changed, endpoint_id


def teardown_system_endpoint(module, name, endpoint_root):
    """Teardown system-level multi-user endpoint."""
    import os
    import subprocess

    changed = False
    service_name = f"globus-compute-endpoint-{name}"
    service_file = f"/etc/systemd/system/{service_name}.service"
    endpoint_dir = os.path.join(endpoint_root, name)

    # Check if systemd service exists
    service_exists = os.path.exists(service_file)

    if service_exists:
        # Stop systemd service
        try:
            subprocess.run(
                ["systemctl", "stop", service_name],
                check=True,
                capture_output=True,
                text=True,
            )
            changed = True
        except subprocess.CalledProcessError:
            # Service might already be stopped or doesn't exist
            pass

        # Disable systemd service
        try:
            subprocess.run(
                ["systemctl", "disable", service_name],
                check=True,
                capture_output=True,
                text=True,
            )
            changed = True
        except subprocess.CalledProcessError:
            # Service might already be disabled
            pass

        # Remove systemd service file
        try:
            os.remove(service_file)
            changed = True
        except OSError as e:
            if e.errno != 2:  # Ignore "No such file or directory"
                module.fail_json(msg=f"Failed to remove service file: {str(e)}")

        # Reload systemd daemon
        try:
            subprocess.run(
                ["systemctl", "daemon-reload"],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            module.fail_json(msg=f"Failed to reload systemd: {e.stderr}")

    # Check if endpoint directory exists
    endpoint_exists = os.path.exists(endpoint_dir)

    if endpoint_exists:
        # Remove endpoint directory
        import shutil

        try:
            shutil.rmtree(endpoint_dir)
            changed = True
        except OSError as e:
            module.fail_json(msg=f"Failed to remove endpoint directory: {str(e)}")

    return changed, service_exists, endpoint_exists


def main():
    argument_spec = globus_argument_spec()
    argument_spec.update(
        resource_type={
            "type": "str",
            "choices": ["endpoint", "function"],
            "default": "endpoint",
        },
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
        subscription_id={"type": "str"},
        high_assurance={"type": "bool", "default": False},
        authentication_policy_id={"type": "str"},
        function_code={"type": "str"},
        function_file={"type": "str"},
        function_id={"type": "str"},
        endpoint_state={"type": "str", "choices": ["started", "stopped"]},
        manage_system={"type": "bool", "default": False},
        globus_venv_path={"type": "str", "default": "/opt/globus-venv"},
        endpoint_root={"type": "str", "default": "/root/.globus_compute"},
        display_name={"type": "str"},
        client_id={"type": "str", "no_log": True},
        client_secret={"type": "str", "no_log": True},
        globus_sdk_environment={
            "type": "str",
            "choices": ["production", "test", "sandbox", "preview"],
        },
    )

    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)

    resource_type = module.params["resource_type"]
    name = module.params["name"]
    state = module.params["state"]

    # Check if we're doing system-level management (which doesn't need globus_sdk)
    manage_system = (
        module.params.get("manage_system", False)
        if resource_type == "endpoint"
        else False
    )

    # Only create API client if NOT doing system-level management
    api = None
    if not manage_system:
        api = GlobusSDKClient(module, required_services=["compute"])

    # Handle endpoint resource type
    if resource_type == "endpoint":
        endpoint_state = module.params.get("endpoint_state")
        endpoint_root = module.params.get("endpoint_root")

        # System-level management takes precedence
        if manage_system:
            if state == "absent":
                # System-level teardown with API deletion
                if module.check_mode:
                    module.exit_json(changed=True, name=name)

                # First, try to get the endpoint ID from local endpoint.json
                endpoint_id = None
                endpoint_json_path = f"{endpoint_root}/{name}/endpoint.json"
                try:
                    import json
                    import os

                    if os.path.exists(endpoint_json_path):
                        with open(endpoint_json_path) as f:
                            endpoint_data = json.load(f)
                            endpoint_id = endpoint_data.get("endpoint_id")
                except Exception as e:
                    # If we can't read the endpoint ID, we'll still clean up local files
                    module.warn(
                        f"Could not read endpoint ID from {endpoint_json_path}: {e}"
                    )

                # If we have an endpoint ID, delete it from the API
                api_deleted = False
                if endpoint_id:
                    # Need to create API client for deletion
                    try:
                        api = GlobusSDKClient(module, required_services=["compute"])
                        delete_compute_endpoint(api, endpoint_id)
                        api_deleted = True
                    except Exception as e:
                        module.warn(
                            f"Failed to delete endpoint {endpoint_id} from API: {e}"
                        )

                # Then clean up local system files
                changed, service_found, endpoint_found = teardown_system_endpoint(
                    module, name, endpoint_root
                )

                module.exit_json(
                    changed=changed,
                    name=name,
                    service_removed=service_found,
                    endpoint_removed=endpoint_found,
                    api_deleted=api_deleted,
                    endpoint_id=endpoint_id if endpoint_id else None,
                )
            elif state == "present":
                # System-level setup
                if module.check_mode:
                    module.exit_json(changed=True, name=name)

                changed, endpoint_id = setup_system_endpoint(module, module.params)

                result = {
                    "changed": changed,
                    "name": name,
                }
                if endpoint_id:
                    result["endpoint_id"] = endpoint_id

                module.exit_json(**result)
        else:
            # API-based management (original behavior)
            existing_endpoint = find_compute_endpoint_by_name(api, name)

            if state == "present":
                if existing_endpoint:
                    # Update existing endpoint
                    changed = False
                    endpoint_id = existing_endpoint["uuid"]

                    # Update endpoint properties
                    update_result = update_compute_endpoint(
                        api, endpoint_id, module.params
                    )
                    if update_result:
                        changed = True

                    # Handle endpoint state changes
                    if endpoint_state:
                        current_state = existing_endpoint.get(
                            "status", "stopped"
                        ).lower()
                        if endpoint_state == "started" and current_state != "online":
                            start_endpoint(api, endpoint_id)
                            changed = True
                        elif endpoint_state == "stopped" and current_state == "online":
                            stop_endpoint(api, endpoint_id)
                            changed = True

                    module.exit_json(
                        changed=changed, endpoint_id=endpoint_id, name=name
                    )
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

    # Handle function resource type
    elif resource_type == "function":
        existing_function = find_function_by_name(api, name)

        if state == "present":
            # Require endpoint_id for function registration
            if not module.params.get("endpoint_id"):
                module.fail_json(
                    msg="endpoint_id is required when registering a function"
                )

            if existing_function:
                # Functions are immutable - return existing function
                function_id = existing_function.get("function_uuid")
                module.exit_json(changed=False, function_id=function_id, name=name)
            else:
                # Register new function
                if module.check_mode:
                    module.exit_json(changed=True, name=name)

                try:
                    result = register_function(api, module.params)
                    function_id = result.get("function_uuid")
                    module.exit_json(changed=True, function_id=function_id, name=name)
                except ValueError as e:
                    module.fail_json(msg=str(e))

        elif state == "absent":
            if existing_function:
                if module.check_mode:
                    module.exit_json(changed=True, name=name)

                function_id = existing_function.get("function_uuid")
                delete_function(api, function_id)
                module.exit_json(changed=True, name=name)
            else:
                module.exit_json(changed=False, name=name)


if __name__ == "__main__":
    main()
