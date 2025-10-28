# End-to-End Testing Guide

This directory contains comprehensive end-to-end tests for the Ansible Globus collection.

## Test Types

### 1. Unit Tests (`tests/unit/`)
- Test individual module functions in isolation
- Mock external dependencies
- Fast execution, no external services required

### 2. Integration Tests (`tests/integration/`)
- Test modules against live Globus services
- Require valid authentication
- Test real API interactions

### 3. End-to-End Tests (`tests/e2e/`)
- Test complete deployment scenarios
- Test full workflows from start to finish
- Validate cleanup and error handling

## Running E2E Tests

### Prerequisites

1. **Globus Application Registration**:
   ```bash
   # Register a confidential client at https://developers.globus.org
   # Note down your client ID and secret
   ```

2. **Environment Setup**:
   ```bash
   export GLOBUS_CLIENT_ID="your-client-id"
   export GLOBUS_CLIENT_SECRET="your-client-secret"
   ```

### Running Tests

```bash
# Install test dependencies
pip install -r tests/requirements.txt

# Run all E2E tests
pytest tests/e2e/ -v -m e2e

# Run specific test
pytest tests/e2e/test_e2e_full_deployment.py::TestE2EGlobusDeployment::test_complete_research_infrastructure -v

# Run with detailed output
pytest tests/e2e/ -v -s --tb=long
```

## Test Scenarios

### 1. Complete Infrastructure Deployment
- Creates research group, endpoint, collection, compute endpoint, and flow
- Verifies all components work together
- Tests cleanup procedures

### 2. Idempotency Verification
- Runs same operations twice
- Verifies no changes on second run
- Confirms resource IDs remain consistent

### 3. Error Handling
- Tests invalid operations
- Verifies proper error messages
- Ensures graceful failure handling

### 4. Check Mode
- Tests Ansible check mode functionality
- Verifies no actual changes are made
- Confirms change detection works

## Test Environment

### Globus Sandbox vs Production

For E2E testing, you can use:

1. **Globus Sandbox** (Recommended for CI):
   ```bash
   export GLOBUS_SDK_ENVIRONMENT="sandbox"
   ```

2. **Globus Production** (For final validation):
   ```bash
   export GLOBUS_SDK_ENVIRONMENT="production"
   ```

### CI/CD Integration

```yaml
# Example GitHub Actions workflow
- name: Run E2E Tests
  env:
    GLOBUS_CLIENT_ID: ${{ secrets.GLOBUS_CLIENT_ID }}
    GLOBUS_CLIENT_SECRET: ${{ secrets.GLOBUS_CLIENT_SECRET }}
    GLOBUS_SDK_ENVIRONMENT: "sandbox"
  run: |
    pytest tests/e2e/ -v -m e2e
```

## Test Data Management

### Naming Convention
All test resources use unique identifiers:
- Format: `e2e-{resource-type}-{test-id}`
- Example: `e2e-research-group-abc123`

### Cleanup Strategy
- Each test includes cleanup steps
- Uses `ignore_errors: true` for cleanup tasks
- Implements cleanup delay for eventual consistency
- Provides manual cleanup scripts for failures

### Manual Cleanup

If tests fail and leave resources behind:

```bash
# List test resources
python tests/e2e/cleanup_test_resources.py --list

# Clean specific test run
python tests/e2e/cleanup_test_resources.py --test-id abc123

# Clean all test resources (dangerous!)
python tests/e2e/cleanup_test_resources.py --all
```

## Debugging Tests

### Enable Debug Logging
```bash
export ANSIBLE_DEBUG=1
export GLOBUS_SDK_LOGGING_LEVEL=DEBUG
pytest tests/e2e/ -v -s
```

### Test Artifacts
Failed tests save artifacts to `/tmp/globus-e2e-artifacts/`:
- Ansible playbook outputs
- API response logs
- Resource state snapshots

### Common Issues

1. **Authentication Failures**:
   - Verify client credentials are correct
   - Check scope permissions
   - Confirm environment (sandbox vs production)

2. **Resource Creation Failures**:
   - Check quota limits
   - Verify permissions
   - Review naming conflicts

3. **Cleanup Failures**:
   - Some resources may have dependencies
   - Wait for eventual consistency
   - Check for active transfers/jobs

## Performance Testing

### Load Testing
```bash
# Test concurrent operations
pytest tests/e2e/test_performance.py::test_concurrent_operations -v

# Test large deployments
pytest tests/e2e/test_performance.py::test_large_scale_deployment -v
```

### Metrics Collection
Tests can collect performance metrics:
- Resource creation time
- API response times
- Cleanup duration
- Memory usage

## Best Practices

1. **Test Isolation**:
   - Each test uses unique resource names
   - No dependencies between tests
   - Proper cleanup in teardown

2. **Error Resilience**:
   - Tests handle transient failures
   - Retry mechanisms for flaky operations
   - Graceful degradation when services unavailable

3. **Resource Management**:
   - Minimize resource creation
   - Use smallest viable configurations
   - Clean up promptly after tests

4. **Documentation**:
   - Clear test descriptions
   - Expected behavior documentation
   - Troubleshooting guides
