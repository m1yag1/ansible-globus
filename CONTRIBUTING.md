# Contributing to Ansible Globus Collection

Thank you for your interest in contributing to the Ansible Globus Collection.

## Prerequisites

- Python 3.9 or higher
- Git
- [uv](https://github.com/astral-sh/uv) for dependency management
- [tox](https://tox.wiki/) installed globally (`pipx install tox`)
- [pre-commit](https://pre-commit.com/) installed globally (`pipx install pre-commit`)
- Basic understanding of Ansible modules and Globus services

## Development Setup

1. **Clone and install dependencies**
   ```bash
   git clone https://github.com/m1yag1/ansible-globus.git
   cd ansible-globus
   uv sync
   ```

2. **Install pre-commit hooks**
   ```bash
   pre-commit install
   pre-commit install --hook-type commit-msg
   ```

3. **Verify setup**
   ```bash
   tox -e lint
   ```

## Project Structure

```
ansible-globus/
├── pyproject.toml          # Project config & dependencies
├── tox.ini                 # Test automation
├── plugins/
│   ├── modules/            # Ansible modules
│   └── module_utils/       # Shared utilities
├── tests/
│   ├── unit/               # Unit tests
│   └── integration/        # Integration tests
└── docs/                   # Documentation
```

## Development Workflow

### Quick Loop

```bash
# Make changes, then lint
tox -e lint

# Run unit tests
tox -e py312-sdk4 -- tests/unit/

# Commit (pre-commit hooks run automatically)
git commit -m "feat: add endpoint option"
```

### Before Opening a PR

Run integration tests locally:
```bash
tox -e py312-sdk4 -- tests/integration/ -m "not high_assurance"
```

### Available tox Environments

```bash
tox -l                    # List all environments
tox -e lint               # Linting (ruff, ansible-lint)
tox -e format             # Auto-format code
tox -e py312-sdk4         # Tests with Python 3.12, SDK v4
tox -e docs               # Build documentation
tox -e docs-serve         # Serve docs locally with hot-reload
```

## CI Pipeline

```
PR Opened       → Lint + Unit tests (fast feedback)
Merge to main   → Full test matrix (sequential integration tests)
Release         → Build + publish to Ansible Galaxy
```

Integration tests run sequentially on main (`max-parallel: 1`) to avoid race conditions on shared test infrastructure.

## Code Style

- **Formatter/Linter**: ruff
- **Type Checking**: mypy
- **Ansible Linting**: ansible-lint

Run `tox -e format` to auto-fix formatting issues.

## Commit Messages

This project uses [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>[optional scope]: <description>
```

Types: `feat`, `fix`, `docs`, `test`, `refactor`, `build`, `ci`, `chore`

Examples:
```bash
feat: add browser automation for CLI login
fix(timer): handle non-existent flow error
docs: update authentication examples
```

Commit messages are validated by a pre-commit hook.

## Testing

### Unit Tests

```bash
tox -e py312-sdk4 -- tests/unit/
```

### Integration Tests

Requires Globus credentials:
```bash
export GLOBUS_CLIENT_ID="your-client-id"
export GLOBUS_CLIENT_SECRET="your-client-secret"
export GLOBUS_SDK_ENVIRONMENT="test"

tox -e py312-sdk4 -- tests/integration/
```

### Test Markers

- `high_assurance` - Requires recent MFA (skipped in CI)
- `compute` - Requires compute endpoint

## Ansible Module Guidelines

1. Follow standard Ansible module patterns
2. Ensure modules are idempotent
3. Include comprehensive documentation and examples
4. Provide clear, actionable error messages
5. Add tests for new functionality

## Pull Request Requirements

- All CI checks pass
- Tests added for new functionality
- Documentation updated as needed
- Follows conventional commit format

## Release Process

See [RELEASING.md](RELEASING.md).

## Getting Help

- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: Questions and ideas

## License

By contributing, you agree that your contributions will be licensed under the GPL-3.0 License.
