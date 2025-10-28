# Contributing to Ansible Globus Collection

Thank you for your interest in contributing to the Ansible Globus Collection! This document provides guidelines and information for contributors.

## 🚀 Getting Started

### Prerequisites

- Python 3.8.1 or higher
- Git
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- Basic understanding of Ansible modules and Globus services

### Development Setup

1. **Install uv** (recommended package manager)
   ```bash
   # On macOS/Linux
   curl -LsSf https://astral.sh/uv/install.sh | sh

   # Or with pip
   pip install uv

   # Or with homebrew
   brew install uv
   ```

2. **Fork and Clone**
   ```bash
   git fork https://github.com/your-org/ansible-globus.git
   git clone https://github.com/your-username/ansible-globus.git
   cd ansible-globus
   ```

3. **Install Dependencies**
   ```bash
   # With uv (recommended) - creates .venv automatically
   uv sync

   # Or with pip
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```

4. **Install Pre-commit Hooks**
   ```bash
   uv run pre-commit install
   uv run pre-commit install --hook-type commit-msg
   ```

5. **Verify Setup**
   ```bash
   uv run tox -e lint
   uv run pytest tests/unit/
   ```

### Project Structure

```
ansible-globus/
├── pyproject.toml          # Project config & dependencies
├── uv.lock                 # Locked dependencies
├── tox.ini                 # Test automation
├── .pre-commit-config.yaml # Git hooks
├── plugins/
│   ├── modules/           # Ansible modules
│   └── module_utils/      # Shared utilities
├── tests/
│   ├── unit/             # Unit tests
│   ├── integration/      # Integration tests
│   └── e2e/              # End-to-end tests
└── docs/examples/        # Example playbooks
```

## 💻 Development Workflow

### Quick Development Loop

```bash
# Make changes
vim plugins/modules/globus_endpoint.py

# Format and test
uv run tox -e format
uv run tox -e py312-ansible-latest

# Commit (pre-commit hooks run automatically)
git add .
git commit -m "feat: add endpoint option"
```

### Package Management with uv

Modern Python package management:

```bash
# Install dependencies
uv sync

# Add dependency
uv add requests

# Add dev dependency
uv add --dev pytest

# Update dependencies
uv sync --upgrade

# Run commands in venv
uv run pytest
uv run black .

# See what's installed
uv pip list
```

### Test Automation with tox

Testing across Python/Ansible versions:

```bash
# All environments
uv run tox

# Specific environment
uv run tox -e py311-ansible6

# Parallel execution
uv run tox -p

# List environments
uv run tox -l
```

### Available tox Environments

- `py312-ansible-latest` - Test environment with Python 3.12 and latest Ansible
- `lint` - Linting with ruff and ansible-lint
- `format` - Code formatting with ruff
- `security` - Security scanning with bandit and safety
- `type-check` - Type checking with mypy
- `e2e` - End-to-end tests

### Common Development Tasks

**Code Quality:**
```bash
# Format code
uv run black plugins/ tests/
uv run isort plugins/ tests/

# Or use tox
uv run tox -e format

# Check linting
uv run tox -e lint

# Type checking
uv run tox -e type-check
```

**Building & Distribution:**
```bash
# Build collection
ansible-galaxy collection build

# Install locally
ansible-galaxy collection install *.tar.gz --force

# Or use make
make build
make install
```

**Pre-commit Hooks:**
```bash
# Install hooks (run once)
uv run pre-commit install

# Run manually
uv run pre-commit run --all-files

# Update hooks
uv run pre-commit autoupdate
```

### Environment Variables

Create `.env` file for development:

```bash
# Globus credentials for testing
GLOBUS_CLIENT_ID=your-client-id
GLOBUS_CLIENT_SECRET=your-client-secret

# Globus environment: production, test, sandbox, preview
GLOBUS_SDK_ENVIRONMENT=test

# Development settings
PYTHONPATH=./plugins
ANSIBLE_DEBUG=1
```

**Globus Environments:**
- `production` - Production environment (default if not set)
- `test` - Test environment (recommended for development and CI)
- `sandbox` - Sandbox environment
- `preview` - Preview environment for upcoming features

### VS Code Integration

The project works well with VS Code:

```json
{
  "python.defaultInterpreterPath": "./.venv/bin/python",
  "python.testing.pytestEnabled": true,
  "python.formatting.provider": "black"
}
```

### Authentication Architecture

The collection uses **dynamic scope requesting** with the Globus SDK:

- **No pre-configuration**: Scopes are requested programmatically, not configured in the Developer Console
- **Least privilege**: Each module only requests scopes for services it actually uses
- **Efficient**: Avoids unnecessary token requests for unused services
- **Secure**: Minimizes the scope of access tokens

```python
# Example: Endpoint module only requests transfer scope
api = GlobusSDKClient(module, required_services=["transfer"])

# Example: Multi-service module requests multiple scopes
api = GlobusSDKClient(module, required_services=["transfer", "groups"])
```

### Why This Setup?

**uv Benefits:**
- ⚡ **Fast**: 10-100x faster than pip
- 🔒 **Reliable**: Consistent dependency resolution
- 🐍 **Modern**: Uses pyproject.toml standard
- 🔄 **Simple**: `uv sync` does everything

**tox Benefits:**
- 🧪 **Matrix Testing**: Multiple Python/Ansible versions
- 🏝️ **Isolation**: Clean environments per test
- 🤖 **Automation**: Same commands locally and CI
- 📊 **Coverage**: Built-in coverage reporting

**For Ansible Collections:**
- ✅ **Standard**: Follows Python packaging standards
- ✅ **Ansible Compatible**: Works with ansible-galaxy
- ✅ **CI Ready**: Same commands work everywhere
- ✅ **Team Friendly**: Reproducible environments

## 📋 Contribution Guidelines

### Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](https://www.contributor-covenant.org/version/2/1/code_of_conduct/). Please read and follow it in all interactions.

### Types of Contributions

We welcome various types of contributions:

- 🐛 **Bug Fixes**: Fix issues in existing modules
- ✨ **New Features**: Add new modules or enhance existing ones
- 📚 **Documentation**: Improve docs, examples, or comments
- 🧪 **Tests**: Add or improve test coverage
- 🎨 **Code Quality**: Refactoring, performance improvements
- 💡 **Ideas**: Feature requests and enhancement proposals

### Contribution Process

1. **Check Existing Issues**
   - Search [existing issues](https://github.com/your-org/ansible-globus/issues)
   - Comment on issues you'd like to work on
   - Create new issues for bugs or feature requests

2. **Create a Branch**
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b bugfix/issue-description
   ```

3. **Make Changes**
   - Follow the coding standards (see below)
   - Add tests for new functionality
   - Update documentation as needed

4. **Test Your Changes**
   ```bash
   # Run all quality checks
   uv run tox

   # Or run specific checks
   uv run tox -e lint
   uv run tox -e py311-ansible6
   ```

5. **Commit and Push**
   ```bash
   git add .
   git commit -m "feat: add new endpoint configuration option"
   git push origin feature/your-feature-name
   ```

6. **Create Pull Request**
   - Use the provided PR template
   - Describe your changes clearly
   - Link related issues
   - Ensure all CI checks pass

## 🏗️ Development Standards

### Code Style

We use modern Python tooling for consistent code quality:

- **Formatter**: `ruff format`
- **Linter**: `ruff check`
- **Type Checking**: `mypy`
- **Import Sorting**: Built into ruff

### Commit Messages

This project follows [Conventional Commits](https://www.conventionalcommits.org/) specification. All commit messages must follow this format:

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

#### Types

- `feat:` - A new feature
- `fix:` - A bug fix
- `docs:` - Documentation only changes
- `test:` - Adding missing tests or correcting existing tests
- `refactor:` - A code change that neither fixes a bug nor adds a feature
- `perf:` - A code change that improves performance
- `style:` - Changes that do not affect the meaning of the code
- `build:` - Changes that affect the build system or dependencies
- `ci:` - Changes to CI configuration files and scripts
- `chore:` - Other changes that don't modify src or test files

#### Scopes (Optional)

- `auth` - Authentication and authorization
- `endpoint` - Endpoint management
- `collection` - Collection management
- `flow` - Flow management
- `timer` - Timer functionality
- `group` - Group management
- `compute` - Compute functionality

#### Examples

```bash
# Simple commit
feat: add browser automation for CLI login

# With scope
feat(auth): add OAuth client creation support

# With body
fix(timer): handle non-existent flow error correctly

The backend was returning 500 UNKNOWN_SCOPE_ERROR instead of a proper
404 or 422 error. This fix adds better error handling.

# Breaking change
feat(api)!: change timer creation API signature

BREAKING CHANGE: The create_timer method now requires a TimerJob object
instead of separate parameters.
```

#### Enforcement

Commit messages are automatically validated by a pre-commit hook. Invalid messages will be rejected:

```bash
# This will be rejected
git commit -m "added a test file"

# Error: [Bad Commit message] >> added a test file
# Your commit message does not follow Conventional Commits formatting

# This will be accepted
git commit -m "test: add timer creation test"
```

#### Tips

- Use imperative mood ("add" not "added" or "adds")
- Keep description under 72 characters
- Don't end description with a period
- Use body to explain what and why, not how
- Reference issues in footer (e.g., `Fixes #123`)

### Python Code Guidelines

1. **Follow PEP 8** (enforced by ruff)
2. **Type Hints**: Use type annotations for function parameters and returns
3. **Docstrings**: Use reStructuredText docstrings for modules, classes, and functions (no type info since we use type hints)
4. **Error Handling**: Use appropriate exception handling
5. **Logging**: Use structured logging where appropriate

**Example:**
```python
def create_endpoint(
    self,
    name: str,
    display_name: Optional[str] = None,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a new Globus endpoint.

    Create a new endpoint with the specified configuration. The endpoint
    will be registered with the Globus service and made available for
    data transfer operations.

    :param name: Unique endpoint name
    :param display_name: Human-readable display name
    :param description: Optional endpoint description
    :return: Dictionary containing endpoint information
    :raises GlobusAPIError: If endpoint creation fails
    """
```

### Ansible Module Guidelines

1. **Module Structure**: Follow standard Ansible module patterns
2. **Documentation**: Include comprehensive module documentation
3. **Examples**: Provide practical usage examples
4. **Parameters**: Use appropriate parameter types and validation
5. **Idempotency**: Ensure modules are idempotent
6. **Error Handling**: Provide clear, actionable error messages

**Module Template:**
```python
DOCUMENTATION = '''
---
module: globus_example
short_description: Manage Globus example resources
description:
  - Create, update, and delete Globus example resources
  - Supports both CLI and client credentials authentication
author:
  - Your Name (@yourgithub)
options:
  name:
    description: Name of the resource
    type: str
    required: true
'''

EXAMPLES = '''
- name: Create example resource
  globus_example:
    name: my-resource
    state: present
'''
```

### Testing Guidelines

We use a comprehensive testing strategy:

1. **Unit Tests**: Test individual functions and classes
2. **Integration Tests**: Test module interactions with Globus APIs
3. **End-to-End Tests**: Test complete workflows

**Test Structure:**
```python
def create_mock_module(params=None):
    """Create a mock Ansible module with optional custom parameters."""
    mock_module = mock.MagicMock(spec=AnsibleModule)
    if params:
        mock_module.params.update(params)
    return mock_module


def test_create_endpoint_success():
    """Test successful endpoint creation."""
    mock_module = create_mock_module({"name": "test-endpoint"})
    # Test implementation here

def test_create_endpoint_missing_params():
    """Test endpoint creation with missing parameters."""
    mock_module = create_mock_module()
    # Test implementation here
```

**Testing Commands:**
```bash
# Unit tests
uv run pytest tests/unit/

# Integration tests (requires auth)
export GLOBUS_CLIENT_ID="your-id"
export GLOBUS_CLIENT_SECRET="your-secret"
uv run pytest tests/integration/

# All tests
uv run tox
```

## 📝 Documentation Standards

### Module Documentation

All modules must include:
- Clear description of purpose
- Complete parameter documentation
- Practical examples
- Return value documentation
- Author information

### README Updates

When adding new features:
- Update the main README.md with new examples
- Add to the module reference section
- Update any affected troubleshooting information

### Changelog

Update `CHANGELOG.md` with:
- Version number
- Release date
- List of changes categorized by type

## 🧪 Testing

### Running Tests

```bash
# All tests with tox
uv run tox

# Specific test suite
uv run tox -e py311-ansible6

# Parallel testing
uv run tox -p auto

# Unit tests only
uv run pytest tests/unit/

# With coverage
uv run pytest --cov=plugins/module_utils

# Integration tests (requires auth)
export GLOBUS_CLIENT_ID="your-client-id"
export GLOBUS_CLIENT_SECRET="your-client-secret"
uv run pytest tests/integration/

# E2E tests
uv run tox -e e2e

# Run only failed tests
uv run pytest --lf

# Verbose output
uv run pytest tests/unit/ -v -s

# Debug specific test
uv run pytest tests/unit/test_globus_common.py::TestGlobusModuleBase::test_init -v
```

### Test Requirements

1. **Coverage**: Maintain >90% test coverage
2. **Isolation**: Tests must not depend on external state
3. **Mocking**: Use appropriate mocking for external APIs
4. **Assertions**: Include meaningful assertions and error messages

### Authentication for Tests

For integration/e2e tests, you'll need:

1. **Globus Application** registered at https://developers.globus.org
2. **Required Scopes**:
   - `urn:globus:auth:scope:transfer.api.globus.org:all`
   - `urn:globus:auth:scope:groups.api.globus.org:all`
   - `urn:globus:auth:scope:compute.api.globus.org:all`
   - `urn:globus:auth:scope:flows.api.globus.org:all`

3. **Environment Variables**:
   ```bash
   export GLOBUS_CLIENT_ID="your-client-id"
   export GLOBUS_CLIENT_SECRET="your-client-secret"
   export GLOBUS_SDK_ENVIRONMENT="sandbox"  # Use sandbox for testing
   ```

4. **For GCS Integration Tests**:
   - Add your client application as an admin on your test Globus project
   - See [GCS Automated Deployment Guide](https://docs.globus.org/globus-connect-server/v5/automated-deployment/)
   - This is required for endpoint/collection creation tests to pass

### CI/CD Integration

GitHub Actions can use the same commands:

```yaml
- name: Install dependencies
  run: uv sync

- name: Run tests
  run: uv run tox

- name: Run E2E tests
  env:
    GLOBUS_CLIENT_ID: ${{ secrets.GLOBUS_CLIENT_ID }}
    GLOBUS_CLIENT_SECRET: ${{ secrets.GLOBUS_CLIENT_SECRET }}
  run: uv run tox -e e2e
```

### Troubleshooting Tests

**Common Issues:**

1. **Import errors**:
   ```bash
   # Ensure dependencies are installed
   uv sync

   # Check Python path
   uv run python -c "import sys; print(sys.path)"
   ```

2. **Test failures**:
   ```bash
   # Run with verbose output
   uv run pytest tests/unit/ -v -s

   # Debug specific test
   uv run pytest tests/unit/test_globus_common.py::TestGlobusModuleBase::test_init -v
   ```

3. **Linting errors**:
   ```bash
   # Auto-fix formatting
   uv run tox -e format

   # Check specific issues
   uv run flake8 plugins/
   ```

4. **Clear caches if needed**:
   ```bash
   # Recreate tox environment
   uv run tox -r

   # Clear uv cache
   uv cache clean
   ```

## 🔍 Code Review Process

### Pull Request Requirements

- All CI checks must pass
- At least one maintainer approval
- No unresolved review comments
- Up-to-date with main branch

### Review Checklist

**Code Quality:**
- [ ] Follows coding standards
- [ ] Includes appropriate tests
- [ ] Documentation is updated
- [ ] No security issues

**Ansible Specific:**
- [ ] Module is idempotent
- [ ] Error handling is appropriate
- [ ] Examples are practical and tested
- [ ] Return values are documented

**Functionality:**
- [ ] Feature works as documented
- [ ] Edge cases are handled
- [ ] Performance is acceptable
- [ ] No breaking changes (unless major version)

## 📦 Release Process

### Versioning

We follow [Semantic Versioning](https://semver.org/):
- `MAJOR.MINOR.PATCH`
- Major: Breaking changes
- Minor: New features (backward compatible)
- Patch: Bug fixes

### Release Steps

1. Update version in `pyproject.toml`
2. Update `CHANGELOG.md`
3. Create release PR
4. Tag release after merge
5. Build and publish to Galaxy

## 🆘 Getting Help

### Communication Channels

- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: General questions and ideas
- **Globus Slack**: [Join the community](https://globus.org/slack)

### Maintainer Contact

- Create an issue for bugs or feature requests
- Use discussions for general questions
- Tag maintainers for urgent issues: @maintainer1 @maintainer2

## 🙏 Recognition

Contributors are recognized in:
- `CHANGELOG.md` for each release
- GitHub contributors page
- Special mentions for significant contributions

### First-Time Contributors

We especially welcome first-time contributors! Look for issues labeled:
- `good first issue`: Perfect for newcomers
- `help wanted`: Community input needed
- `documentation`: Improve our docs

## 📄 License

By contributing, you agree that your contributions will be licensed under the Apache License 2.0, the same as the project.

---

Thank you for contributing to the Ansible Globus Collection! Your efforts help make research data management more accessible and reliable for the scientific community. 🚀
