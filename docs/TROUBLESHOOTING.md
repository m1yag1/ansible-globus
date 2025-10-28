# Troubleshooting Guide

This comprehensive guide helps you diagnose and resolve common issues with the Ansible Globus Collection.

## 🚨 Quick Fixes

### Authentication Issues

**Error**: `Not authenticated with Globus CLI`
```bash
# Solution 1: Re-authenticate with CLI
globus logout
globus login

# Solution 2: Verify client credentials
echo $GLOBUS_CLIENT_ID
echo $GLOBUS_CLIENT_SECRET
```

**Error**: `Invalid client credentials`
```yaml
# Check your client application at https://developers.globus.org
# Verify the application is a "Confidential Client"
# No scope configuration needed - scopes are requested dynamically:
# - urn:globus:auth:scope:transfer.api.globus.org:all
# - urn:globus:auth:scope:groups.api.globus.org:all
# - urn:globus:auth:scope:compute.api.globus.org:all
# - urn:globus:auth:scope:flows.api.globus.org:all
```

### Module Import Errors

**Error**: `Module globus_endpoint not found`
```bash
# Verify collection is installed
ansible-galaxy collection list | grep globus

# Reinstall if needed
ansible-galaxy collection install community.globus --force

# Check PYTHONPATH
export PYTHONPATH=$PWD/plugins:$PYTHONPATH
```

## 🔧 Detailed Troubleshooting

### 1. Authentication Problems

#### CLI Authentication Issues

**Problem**: CLI authentication fails or expires
```bash
# Check current authentication status
globus whoami

# If expired, logout and re-login
globus logout
globus login

# For headless systems, use device flow
globus login --no-local-server
```

**Problem**: Multiple Globus CLI installations
```bash
# Find all globus installations
which -a globus

# Check version consistency
globus --version

# Uninstall conflicting versions
pip uninstall globus-cli
# Then reinstall with your preferred method
```

#### Client Credentials Issues

**Problem**: Client credentials not working
```yaml
# Verify your application configuration
- name: Debug client credentials
  debug:
    msg: "Client ID: {{ globus_client_id[:8] }}..."
  vars:
    globus_client_id: "{{ vault_globus_client_id }}"

# Test credentials manually
- name: Test authentication
  uri:
    url: https://auth.globus.org/v2/oauth2/token
    method: POST
    headers:
      Authorization: "Basic {{ (client_id + ':' + client_secret) | b64encode }}"
      Content-Type: "application/x-www-form-urlencoded"
    body: "grant_type=client_credentials&scope=urn:globus:auth:scope:transfer.api.globus.org:all"
  register: auth_test
```

**Problem**: Token expires during long-running playbooks
```yaml
# Use shorter playbook segments with re-authentication
- name: Refresh authentication
  include_tasks: auth_refresh.yml
  when: ansible_date_time.epoch | int > (auth_timestamp | int + 3000)
```

### 2. API and Network Issues

#### Rate Limiting

**Problem**: API rate limit exceeded
```yaml
# Add throttling to your tasks
- name: Create endpoints with rate limiting
  globus_endpoint:
    name: "endpoint-{{ item }}"
    state: present
  loop: "{{ range(1, 50) | list }}"
  throttle: 5  # Only 5 concurrent operations
  delay: 1     # 1 second delay between operations
```

#### Network Connectivity

**Problem**: API requests timing out
```bash
# Test connectivity to Globus APIs
curl -I https://transfer.api.globus.org/v0.10/endpoint_list
curl -I https://auth.globus.org/v2/api/identities
curl -I https://groups.api.globus.org/v2/groups

# Check firewall/proxy settings
export HTTP_PROXY=http://proxy.example.com:8080
export HTTPS_PROXY=http://proxy.example.com:8080
```

**Problem**: SSL certificate issues
```yaml
# Temporarily disable SSL verification (not recommended for production)
- name: Create endpoint with SSL bypass
  globus_endpoint:
    name: "test-endpoint"
    state: present
  environment:
    PYTHONHTTPSVERIFY: 0
```

### 3. Module-Specific Issues

#### Endpoint Management

**Problem**: Endpoint creation fails with permission denied
```bash
# Verify GCS is properly configured
sudo globus-connect-server node list

# Check local permissions
ls -la /var/lib/globus-connect-server/
sudo systemctl status globus-connect-server
```

**Problem**: `403 Forbidden` when creating endpoints or collections
```yaml
# This usually means your client application lacks admin privileges
# Solution: Add your client ID as an admin on your Globus project

# 1. Go to https://app.globus.org/settings/developers
# 2. Select your project
# 3. Go to "Administrators" tab
# 4. Add your client application UUID as an admin
# 5. See: https://docs.globus.org/globus-connect-server/v5/automated-deployment/

# Verify your project admin status
- name: Debug project permissions
  uri:
    url: "https://transfer.api.globus.org/v0.10/endpoint_manager/administrator_list"
    headers:
      Authorization: "Bearer {{ access_token }}"
  register: admin_check

- debug:
    msg: "Your client has admin access to projects: {{ admin_check.json.DATA }}"
```

**Problem**: Endpoint not visible after creation
```yaml
- name: Wait for endpoint to be active
  globus_endpoint:
    name: "{{ endpoint_name }}"
    state: present
  register: endpoint_result
  retries: 5
  delay: 10
  until: endpoint_result.changed == false
```

#### Collection Management

**Problem**: Collection path permissions
```bash
# Verify path exists and is accessible
ls -la /data/research/
sudo -u globus ls -la /data/research/

# Fix permissions if needed
sudo chmod 755 /data/research/
sudo chown globus:globus /data/research/
```

**Problem**: Guest collection creation fails
```yaml
# Ensure the user has proper permissions
- name: Verify user identity
  globus_group:
    name: "test-group"
    members: ["{{ user_identity }}"]
    state: present
  register: user_check

- debug:
    msg: "User identity verified: {{ user_check.members }}"
```

#### Group Management

**Problem**: Group membership not updating
```yaml
# Force group refresh
- name: Update group membership
  globus_group:
    name: "{{ group_name }}"
    members: "{{ new_member_list }}"
    state: present
  register: group_update

- name: Verify membership update
  assert:
    that:
      - group_update.changed == true
    fail_msg: "Group membership failed to update"
```

#### Compute Endpoints

**Problem**: Compute endpoint registration fails
```bash
# Check Globus Compute installation
globus-compute-endpoint list

# Verify endpoint configuration
cat ~/.globus_compute/{{ endpoint_name }}/config.py

# Check logs
tail -f ~/.globus_compute/{{ endpoint_name }}/endpoint.log
```

#### Flow Management

**Problem**: Flow deployment fails
```yaml
# Validate flow definition syntax
- name: Validate flow definition
  assert:
    that:
      - flow_definition.Comment is defined
      - flow_definition.StartAt is defined
      - flow_definition.States is defined
    fail_msg: "Invalid flow definition structure"

# Check flow syntax with external tool
- name: Validate flow syntax
  command: python -c "import json; json.loads('{{ flow_definition | to_json }}')"
```

### 4. Performance Issues

#### Slow Operations

**Problem**: Large dataset transfers are slow
```yaml
# Enable parallel transfers
- name: Configure high-performance endpoint
  globus_endpoint:
    name: "{{ endpoint_name }}"
    network_use: aggressive
    preferred_concurrency: 8
    preferred_parallelism: 4
    state: present
```

**Problem**: Many small files causing timeouts
```yaml
# Use batch operations
- name: Create collections in batches
  globus_collection:
    name: "{{ item.name }}"
    endpoint_id: "{{ endpoint_id }}"
    path: "{{ item.path }}"
    state: present
  loop: "{{ collections | batch(10) | list }}"
  loop_control:
    label: "{{ item | length }} collections"
```

### 5. Development and Testing Issues

#### Unit Test Failures

**Problem**: Tests fail with import errors
```bash
# Ensure test environment is set up
uv sync
uv run pytest tests/unit/ -v

# Check Python path
uv run python -c "import sys; print('\n'.join(sys.path))"

# Run specific failing test
uv run pytest tests/unit/test_globus_endpoint.py::TestEndpoint::test_create -v -s
```

**Problem**: Integration tests fail with auth errors
```bash
# Set up test credentials
export GLOBUS_CLIENT_ID="your-test-client-id"
export GLOBUS_CLIENT_SECRET="your-test-client-secret"
export GLOBUS_SDK_ENVIRONMENT="sandbox"

# Use sandbox environment for testing
uv run pytest tests/integration/ -v --tb=short
```

#### Mock Issues in Tests

**Problem**: Mock objects not behaving correctly
```python
# Debug mock calls
def test_endpoint_creation(self, mock_api):
    mock_api.return_value.create.return_value = {"id": "test-id"}

    # Debug what was actually called
    result = create_endpoint("test")
    print(f"Mock called with: {mock_api.return_value.create.call_args}")

    # Use more specific assertions
    mock_api.return_value.create.assert_called_once_with(
        name="test",
        description=None
    )
```

### 6. Production Issues

#### Deployment Problems

**Problem**: Playbook fails in production but works in development
```yaml
# Add comprehensive error handling
- name: Create production endpoint
  globus_endpoint:
    name: "{{ production_endpoint_name }}"
    state: present
  register: endpoint_result
  failed_when: false  # Don't fail immediately

- name: Handle endpoint creation failure
  fail:
    msg: "Endpoint creation failed: {{ endpoint_result.msg }}"
  when:
    - endpoint_result.failed
    - "'already exists' not in (endpoint_result.msg | default(''))"

# Log deployment details
- name: Log deployment status
  debug:
    msg:
      - "Endpoint ID: {{ endpoint_result.endpoint_id | default('N/A') }}"
      - "Changed: {{ endpoint_result.changed | default(false) }}"
      - "Error: {{ endpoint_result.msg | default('None') }}"
```

**Problem**: Idempotency issues
```yaml
# Verify idempotent behavior
- name: Create endpoint (first run)
  globus_endpoint:
    name: "test-endpoint"
    state: present
  register: first_run

- name: Create endpoint (second run)
  globus_endpoint:
    name: "test-endpoint"
    state: present
  register: second_run

- name: Verify idempotency
  assert:
    that:
      - first_run.changed == true
      - second_run.changed == false
    fail_msg: "Module is not idempotent"
```

### 7. Security Issues

#### Credential Exposure

**Problem**: Credentials appearing in logs
```yaml
# Use Ansible Vault for sensitive data
# Create vault file: ansible-vault create group_vars/all/vault.yml
vault_globus_client_id: "your-client-id"
vault_globus_client_secret: "your-client-secret"

# Use in playbook
- name: Secure endpoint creation
  globus_endpoint:
    name: "secure-endpoint"
    auth_method: client_credentials
    client_id: "{{ vault_globus_client_id }}"
    client_secret: "{{ vault_globus_client_secret }}"
    state: present
  no_log: true  # Prevent logging of task details
```

**Problem**: Overprivileged applications
```bash
# Review application scopes at https://developers.globus.org
# Use principle of least privilege
# Create separate applications for different use cases
```

## 🔍 Debugging Techniques

### Enable Verbose Output

```bash
# Ansible verbose modes
ansible-playbook playbook.yml -v    # Basic
ansible-playbook playbook.yml -vv   # More details
ansible-playbook playbook.yml -vvv  # Debug level

# Enable debug in tasks
- debug:
    var: endpoint_result
    verbosity: 2
```

### API Response Debugging

```yaml
- name: Debug API responses
  globus_endpoint:
    name: "debug-endpoint"
    state: present
  register: api_result

- debug:
    msg: "API Response: {{ api_result }}"
    verbosity: 1
```

### Network Debugging

```bash
# Monitor API calls
export GLOBUS_SDK_HTTP_TIMEOUT=60
export GLOBUS_SDK_LOG_LEVEL=DEBUG

# Use tcpdump to monitor traffic
sudo tcpdump -i any -n host auth.globus.org

# Check DNS resolution
nslookup transfer.api.globus.org
dig auth.globus.org
```

### Module Development Debugging

```python
# Add debugging to custom modules
from ansible.module_utils._text import to_text

def debug_log(module, message):
    module.log(f"DEBUG: {to_text(message)}")

# In your module
debug_log(module, f"Creating endpoint with params: {params}")
```

## 📞 Getting Help

### Before Asking for Help

1. **Check this troubleshooting guide**
2. **Search existing issues**: https://github.com/your-org/ansible-globus/issues
3. **Review Globus documentation**: https://docs.globus.org
4. **Test with minimal example**
5. **Gather debug information**

### Information to Include

When reporting issues, provide:

```bash
# System information
ansible --version
python --version
globus --version

# Collection information
ansible-galaxy collection list | grep globus

# Error output
ansible-playbook playbook.yml -vvv 2>&1 | tee debug.log

# Minimal reproduction case
cat > minimal_test.yml << 'EOF'
- hosts: localhost
  tasks:
    - name: Test basic functionality
      globus_endpoint:
        name: "test-endpoint"
        state: present
      register: result

    - debug: var=result
EOF
```

### Community Support

- **GitHub Issues**: https://github.com/your-org/ansible-globus/issues
- **GitHub Discussions**: https://github.com/your-org/ansible-globus/discussions
- **Globus Community**: https://discuss.globus.org
- **Slack**: https://globus.org/slack

### Professional Support

For production deployments, consider:
- Globus Premium Support
- Professional services for large deployments
- Custom module development

## 🛡️ Prevention Tips

### Best Practices

1. **Test in sandbox first**: Use Globus sandbox environment
2. **Use version control**: Track your playbooks and configurations
3. **Monitor resources**: Set up monitoring for endpoints and transfers
4. **Regular updates**: Keep the collection updated
5. **Backup configurations**: Save endpoint and collection configurations

### Health Checks

```yaml
# Regular health check playbook
- name: Globus Infrastructure Health Check
  hosts: localhost
  tasks:
    - name: Check endpoint status
      globus_endpoint:
        name: "{{ item }}"
        state: present
      register: endpoint_check
      loop: "{{ managed_endpoints }}"

    - name: Verify collections are accessible
      uri:
        url: "https://transfer.api.globus.org/v0.10/collection/{{ item }}/ls"
        headers:
          Authorization: "Bearer {{ access_token }}"
      loop: "{{ managed_collections }}"
```

### Monitoring and Alerting

```yaml
# Set up monitoring
- name: Monitor transfer rates
  uri:
    url: "https://transfer.api.globus.org/v0.10/endpoint/{{ endpoint_id }}/server_list"
  register: server_status

- name: Alert on performance issues
  mail:
    subject: "Globus Performance Alert"
    body: "Endpoint {{ endpoint_id }} performance degraded"
  when: server_status.json.bandwidth < expected_bandwidth
```

---

This troubleshooting guide is continuously updated. If you encounter issues not covered here, please contribute by opening an issue or pull request!
