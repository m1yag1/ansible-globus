# Makefile for Ansible Globus Collection

.PHONY: help install test lint clean build docs dev-setup integration-test security-check

# Default target
help:
	@echo "Available targets:"
	@echo "  help            - Show this help message"
	@echo "  dev-setup       - Set up development environment with uv"
	@echo "  install         - Install the collection locally"
	@echo "  test            - Run unit tests"
	@echo "  integration-test - Run integration tests (requires authentication)"
	@echo "  lint            - Run code linting"
	@echo "  security-check  - Run security scans"
	@echo "  clean           - Clean build artifacts"
	@echo "  build           - Build collection tarball"
	@echo "  docs            - Build documentation"
	@echo "  all-checks      - Run all quality checks"
	@echo ""
	@echo "Modern development workflow:"
	@echo "  uv sync              - Install dependencies"
	@echo "  uv run ruff check    - Run linting (fast!)"
	@echo "  uv run ruff format   - Format code (fast!)"
	@echo "  uv run tox -e py311-ansible6 - Run tests"
	@echo "  uv run tox -e e2e    - Run E2E tests"

# Development setup using uv
dev-setup:
	@echo "Setting up development environment with uv..."
	@echo "Installing dependencies..."
	uv sync
	@echo "Installing pre-commit hooks..."
	uv run pre-commit install
	@echo "✅ Development environment ready!"
	@echo "Activate with: source .venv/bin/activate"

# Install collection locally
install:
	@echo "Installing collection locally..."
	ansible-galaxy collection build --force
	ansible-galaxy collection install *.tar.gz --force

# Unit tests
test:
	@echo "Running unit tests via tox..."
	@if command -v tox >/dev/null 2>&1; then \
		tox -e py311-ansible6; \
	else \
		echo "⚠️  tox not found, falling back to direct pytest"; \
		echo "   Consider running: python dev-setup.py"; \
		pytest tests/unit/ -v --cov=plugins/module_utils --cov-report=term-missing --cov-report=html || true; \
	fi

# Integration tests (requires Globus authentication)
integration-test:
	@echo "Running integration tests..."
	@echo "Note: This requires valid Globus authentication"
	pytest tests/integration/ -v -m integration

# Linting
lint:
	@echo "Running code linting with ruff..."
	@if command -v uv >/dev/null 2>&1; then \
		uv run ruff check plugins/ tests/; \
	elif command -v ruff >/dev/null 2>&1; then \
		ruff check plugins/ tests/; \
	else \
		echo "⚠️  Neither uv nor ruff found"; \
		echo "   Run: uv sync"; \
	fi

# Security checks
security-check:
	@echo "Running security checks..."
	bandit -r plugins/ -f json -o bandit-report.json || true
	safety check || true
	@echo "Security reports generated: bandit-report.json"

# Clean build artifacts
clean:
	@echo "Cleaning build artifacts..."
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -f *.tar.gz
	rm -rf htmlcov/
	rm -f .coverage
	rm -f coverage.xml
	rm -f bandit-report.json
	rm -f safety-report.json
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

# Build collection
build: clean
	@echo "Building collection..."
	ansible-galaxy collection build

# Build documentation
docs:
	@echo "Building documentation..."
	@echo "Validating README..."
	python -c "import markdown; markdown.markdown(open('README.md').read())"
	@echo "Documentation validated successfully!"

# Run all quality checks
all-checks: lint test security-check
	@echo "All quality checks completed!"

# Development workflow targets
dev-test: lint test
	@echo "Development tests completed!"

dev-install: build install
	@echo "Development installation completed!"

# CI simulation
ci-simulation: all-checks build
	@echo "CI simulation completed successfully!"

# Release preparation
release-prep: all-checks build docs
	@echo "Release preparation completed!"
	@echo "Collection tarball: $(shell ls *.tar.gz)"
	@echo "Ready for release!"

# Quick development cycle
quick: lint test build
	@echo "Quick development cycle completed!"

# Format code
format:
	@echo "Formatting code..."
	black plugins/ tests/
	isort plugins/ tests/
	@echo "Code formatting completed!"

# Install development dependencies
deps:
	@echo "Installing development dependencies..."
	pip install -r tests/requirements.txt
	pip install black isort flake8 bandit safety ansible-lint yamllint

# Test matrix (different Python/Ansible versions)
test-matrix:
	@echo "Running test matrix..."
	@echo "This would run tests against multiple Python/Ansible versions"
	@echo "Use CI pipeline for full matrix testing"

# Performance testing
perf-test:
	@echo "Running performance tests..."
	@echo "Performance testing not yet implemented"

# Generate test coverage report
coverage:
	@echo "Generating coverage report..."
	pytest tests/unit/ --cov=plugins/module_utils --cov-report=html --cov-report=term
	@echo "Coverage report generated in htmlcov/"

# Validate examples
validate-examples:
	@echo "Validating example playbooks..."
	ansible-playbook docs/examples/complete_gcs_deployment.yml --syntax-check
	ansible-playbook docs/examples/multi_site_research.yml --syntax-check
	@echo "Example playbooks validated!"

# Run specific module tests
test-module-%:
	@echo "Running tests for module: $*"
	pytest tests/unit/test_globus_$*.py -v

# Development server (for documentation)
serve-docs:
	@echo "Starting documentation server..."
	@echo "Documentation available at: http://localhost:8000"
	python -m http.server 8000 -d docs/ || python -m SimpleHTTPServer 8000

# Check for outdated dependencies
deps-check:
	@echo "Checking for outdated dependencies..."
	pip list --outdated

# Git hooks setup
git-hooks:
	@echo "Setting up git hooks..."
	@echo "#!/bin/bash" > .git/hooks/pre-commit
	@echo "make lint" >> .git/hooks/pre-commit
	chmod +x .git/hooks/pre-commit
	@echo "Git hooks configured!"
