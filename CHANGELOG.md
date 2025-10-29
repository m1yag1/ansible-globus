# Changelog

All notable changes to the Ansible Globus Collection will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Nothing yet

### Changed
- Nothing yet

### Fixed
- Nothing yet

## [0.1.0] - TBD

### Added
- Initial Ansible collection for Globus infrastructure management
- Core modules for managing Globus resources:
  - `globus_auth` - Manage Globus Auth projects and OAuth clients
  - `globus_endpoint` - Manage Globus Transfer endpoints
  - `globus_collection` - Manage data collections on endpoints
  - `globus_group` - Manage user groups and access control
  - `globus_compute` - Manage compute endpoints for function execution
  - `globus_flow` - Manage automation workflows
- Authentication support for CLI, client credentials, and access token methods
- Comprehensive test suite with unit, integration, and e2e tests
- Modern development workflow using uv and tox
- Ansible Galaxy publishing support via tox environments
- Documentation including README, developer guide, and contributing guidelines

### Known Limitations
- Project and OAuth client deletion temporarily disabled due to Globus Auth high-assurance requirement
  - Users must delete these resources manually at https://app.globus.org/settings/developers
  - This limitation may be resolved in a future Globus Auth release

### Technical Details
- Built with Globus SDK 3.0+ for optimal performance and reliability
- Supports Python 3.12+ and Ansible 2.16+ for modern tooling compatibility
- Implements declarative, idempotent operations
- Includes CI/CD pipeline with GitHub Actions
- Uses ruff for fast linting and formatting
- Pre-commit hooks for code quality

### Documentation
- Comprehensive README with authentication setup and examples
- Developer guide (README-DEV.md) with modern workflow
- Contributing guidelines (CONTRIBUTING.md)
- Real-world deployment examples
- Troubleshooting guide and common solutions

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

## Release Planning

### Version 1.0.0 (Planned)
**Target**: Initial stable release

**Scope**:
- All core modules feature-complete
- Comprehensive test coverage (>90%)
- Production-ready documentation
- Performance benchmarks
- Security review completed

### Version 0.1.0 (Development)
**Status**: In development

**Scope**:
- Core module framework
- Authentication mechanisms
- Basic test infrastructure
- Development tooling setup

---

## Contributing to Changelog

When contributing, please:

1. **Update Unreleased section** with your changes
2. **Use appropriate categories** (Added, Changed, Fixed, etc.)
3. **Include breaking change notices** in Changed/Removed sections
4. **Reference issue numbers** where applicable
5. **Follow semantic versioning** for release planning

### Example Entry Format

```markdown
### Added
- New `globus_endpoint` parameter `high_assurance` for enhanced security (#123)
- Support for custom metadata in collections (#145)

### Fixed
- Fixed authentication token refresh issue (#134)
- Resolved endpoint creation timeout in large deployments (#156)

### Changed
- **BREAKING**: Renamed `endpoint_uuid` parameter to `endpoint_id` for consistency (#167)
  - Migration: Update all playbooks to use `endpoint_id` instead of `endpoint_uuid`
```

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
