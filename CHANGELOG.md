# Changelog

All notable changes to the Ansible Globus Collection will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2025-11-05

### Added

- Add Ansible Galaxy publishing support via tox
- **changelog**: Add automated changelog generation with git-cliff
- **release**: Add automated release workflow

### Changed

- Use tox for CI test environment management
- Make test paths explicit in tox, remove duplicate -v flags
- Improve CI/CD workflows for testing and releases

### Documentation

- Clarify deletion limitation is due to temporary Globus Auth bug
- Add comprehensive release process guide

### Fixed

- Register high_assurance and e2e markers in pytest.ini
- Add tests directory to Python path for s3_token_storage import
- Install test dependencies before SDK to prevent conflicts
- Use editable install in tox to access test support files
- Use single pytest command in tox to prevent duplicate runs
- Explicitly set PYTHONPATH in tox for test module imports
- Use _build directory for Galaxy builds and fix glob expansion
- Correct GitHub repository URLs in README
- Ensure clean _build directory in Galaxy tox environments
- **hooks**: Disable ansible-lint in pre-commit
- **hooks**: Run ansible-lint via tox in pre-commit
- **tests**: Add tests directory to Python path for s3_token_storage import
- **tests**: Fail integration tests in CI when imports fail
- **tests**: Fail CI when tokens are expired or missing
- Make token errors fail consistently and add refresh script
- Correct pytest.ini section header for marker registration
- Support globus-sdk v4 by making StorageAdapter optional
- Correct safety check output flag syntax

---

## Release Notes Format

Each release will include:

### Added
- New features and modules
- New configuration options
- New documentation

### Changed
- Updates to existing functionality
- API changes (with migration notes)
- Documentation improvements

### Deprecated
- Features planned for removal
- Migration instructions

### Removed
- Removed features (breaking changes)
- Dropped support notices

### Fixed
- Bug fixes
- Security patches
- Performance improvements

### Security
- Security-related changes
- Vulnerability fixes

---

## Contributing to Changelog

When contributing, please:

1. **Use conventional commits** (feat:, fix:, docs:, etc.)
2. **Include scope** for clarity (e.g., `feat(auth): add OAuth support`)
3. **Reference issue numbers** where applicable
4. **Follow semantic versioning** for release planning

### Conventional Commit Types

- `feat`: New features → Minor version bump
- `fix`: Bug fixes → Patch version bump
- `docs`: Documentation changes → No version bump
- `refactor`: Code refactoring → Patch version bump
- `test`: Test changes → No version bump
- `chore`: Maintenance tasks → No version bump
- `BREAKING CHANGE`: Breaking changes → Major version bump

---

## Compatibility Matrix

### Supported Versions

| Component | Version Range | Status |
|-----------|---------------|---------|
| Python | 3.12+ | ✅ Supported |
| Ansible Core | 2.16+ | ✅ Supported |
| Globus SDK | 3.0+ | ✅ Supported |

### Testing Matrix

The collection is tested against:
- Python: 3.12
- Ansible: ansible-core 2.16+

### Deprecation Policy

- **Minor versions**: May deprecate features with 6-month notice
- **Major versions**: May remove deprecated features
- **Security**: Critical fixes may require immediate breaking changes

---

*This changelog helps track the evolution of the Ansible Globus Collection and ensures users can understand the impact of updates on their infrastructure.*
