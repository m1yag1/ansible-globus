# Integration Testing: Traditional GCS + Ansible Globus Collection

This guide shows how to test the new Ansible Globus Collection with your existing traditional GCS setup.

## Overview

Your hybrid approach:
1. **Traditional Role**: `globus-connect-server` role installs and configures GCS software on EC2
2. **New Collection**: `m1yag1.globus` manages Globus resources via API from your Mac

## Prerequisites

### 1. Environment Setup (Your Mac)

```bash
# Install the new collection
cd /Users/blackbird/Projects/01_personal/ansible-globus
uv run ansible-galaxy collection build
uv run ansible-galaxy collection install community-globus-1.0.0.tar.gz --force

# Set up environment variables (same as your existing setup)
export GLOBUS_CLIENT_ID="your-client-id"
export GLOBUS_CLIENT_SECRET="your-client-secret"
export GLOBUS_PROJECT_ID="your-project-id"
```

### 2. EC2 Infrastructure

Use your existing EC2 setup with proper tags:
- `Purpose: globus_connect_server`
- `GCS_HighAssurance: true/false` (as needed)

## Integration Testing Steps

### Step 1: Copy Integration Files

```bash
# Copy the integration playbook to your existing ansible directory
cp /Users/blackbird/Projects/01_personal/ansible-globus/examples/integration_with_traditional_gcs.yml \
   /Users/blackbird/Projects/00_globus/00_automate/setup-gcs-endpoint/ansible/

# Update your group_vars with new variables (merge with existing)
cp /Users/blackbird/Projects/01_personal/ansible-globus/examples/group_vars_integration_example.yml \
   /Users/blackbird/Projects/00_globus/00_automate/setup-gcs-endpoint/ansible/group_vars/integration_example.yml
```

### Step 2: Test Traditional GCS Setup (Your Existing Process)

```bash
cd /Users/blackbird/Projects/00_globus/00_automate/setup-gcs-endpoint/ansible

# Run your existing playbook first
ansible-playbook -i inventory/aws_ec2.yml configure-gcs-servers.yml
```

Verify GCS is installed and running on your EC2 instances.

### Step 3: Test Integrated Approach

```bash
# Run the integrated playbook that includes both traditional + API management
ansible-playbook -i inventory/aws_ec2.yml integration_with_traditional_gcs.yml -v
```

This will:
1. Run your existing `globus-connect-server` role
2. Wait for GCS to be operational
3. Use the new collection to manage endpoints, collections, and groups via API

### Step 4: Verify API Integration

Check that the new collection created resources:

```bash
# From your Mac, verify endpoint was created
globus endpoint search "Test GCS Endpoint for Collection Roles"

# Verify collections were created
globus collection search "Test Collection 1"

# Check group creation
globus group list --filter-name "Test-GCS-Endpoint-test-users"
```

## Testing Individual Modules

You can test individual modules from your existing playbook structure:

### Test Endpoint Management

Create a simple test playbook:

```yaml
# test_endpoint.yml
---
- hosts: localhost
  collections:
    - m1yag1.globus
  vars:
    globus_auth:
      client_id: "{{ lookup('env', 'GLOBUS_CLIENT_ID') }}"
      client_secret: "{{ lookup('env', 'GLOBUS_CLIENT_SECRET') }}"
  tasks:
    - name: Test endpoint creation
      m1yag1.globus.globus_endpoint:
        auth: "{{ globus_auth }}"
        display_name: "Test API Endpoint"
        description: "Testing the new collection"
        state: present
      register: result

    - name: Show result
      debug:
        var: result
```

Run it:
```bash
cd /Users/blackbird/Projects/00_globus/00_automate/setup-gcs-endpoint/ansible
ansible-playbook test_endpoint.yml
```

### Test Collection Management

```yaml
# test_collection.yml
---
- hosts: localhost
  collections:
    - m1yag1.globus
  vars:
    globus_auth:
      client_id: "{{ lookup('env', 'GLOBUS_CLIENT_ID') }}"
      client_secret: "{{ lookup('env', 'GLOBUS_CLIENT_SECRET') }}"
    # Replace with actual endpoint ID from previous test
    test_endpoint_id: "abc123-def456-..."
  tasks:
    - name: Test collection creation
      m1yag1.globus.globus_collection:
        auth: "{{ globus_auth }}"
        endpoint_id: "{{ test_endpoint_id }}"
        display_name: "Test API Collection"
        collection_base_path: "/tmp/test"
        state: present
      register: result

    - name: Show result
      debug:
        var: result
```

## Troubleshooting

### Common Issues

1. **"Module not found"**:
   ```bash
   # Ensure collection is installed
   ansible-galaxy collection list | grep globus
   ```

2. **"Authentication failed"**:
   - Verify environment variables are set
   - Check that your client app is added as admin to the Globus project
   - Ensure client has proper scopes (they're requested automatically)

3. **"Endpoint not ready"**:
   - Traditional GCS installation may take time
   - Check GCS service status on EC2: `sudo systemctl status globus-connect-server`
   - Verify HTTPS port 443 is accessible

4. **"API timeouts"**:
   - Your EC2 instances need internet access for Globus API calls
   - Check security group settings

### Debug Mode

Enable debug output:

```bash
ansible-playbook integration_with_traditional_gcs.yml -vvv
```

Or add to your group_vars:
```yaml
globus_api_config:
  debug_mode: true
```

## Integration with Your Existing Workflow

To integrate with your regular testing workflow:

1. **Modify your existing `configure-gcs-servers.yml`**:
   ```yaml
   # Add this at the end of your existing playbook
   - import_playbook: integration_with_traditional_gcs.yml
   ```

2. **Or create a new combined playbook**:
   ```yaml
   # combined_gcs_setup.yml
   ---
   - import_playbook: configure-gcs-servers.yml
   - import_playbook: integration_with_traditional_gcs.yml
   ```

This gives you a single command that does both traditional GCS setup and API resource management:

```bash
ansible-playbook -i inventory/aws_ec2.yml combined_gcs_setup.yml
```

## Next Steps

Once basic integration works:

1. **Add the new collection to your requirements**:
   ```yaml
   # requirements.yml
   collections:
     - name: m1yag1.globus
       source: /path/to/built/collection
   ```

2. **Extend with additional resources**:
   - Add compute endpoint management
   - Add flow deployment
   - Add group membership management

3. **Create idempotent workflows**:
   - The collection modules are idempotent, so repeated runs are safe
   - Perfect for CI/CD pipelines and infrastructure updates
