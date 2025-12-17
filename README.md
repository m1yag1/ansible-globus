# Ansible Globus Collection

**[Read the full documentation](https://ansible-globus.readthedocs.io)**

- [Getting Started](https://ansible-globus.readthedocs.io/en/latest/getting-started/)
- [Module Reference](https://ansible-globus.readthedocs.io/en/latest/collections/)

## Installation

```bash
ansible-galaxy collection install m1yag1.globus
```

Or install from source:

```bash
git clone https://github.com/m1yag1/ansible-globus.git
cd ansible-globus
ansible-galaxy collection build
ansible-galaxy collection install m1yag1-globus-*.tar.gz
```

## Requirements

- Python 3.12+
- Ansible 2.16+
- Globus SDK 3.0+
- Globus account with appropriate permissions

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

## License

Apache License 2.0 - see [LICENSE](LICENSE) for details.
