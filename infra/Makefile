# Makefile for managing ansible-globus infrastructure
#
# Usage with aws-vault:
#   make deploy AWS_PROFILE=your-profile
#   make destroy AWS_PROFILE=your-profile
#   make check AWS_PROFILE=your-profile

.PHONY: help check deploy destroy list-buckets

# Default values
AWS_PROFILE ?= default
GITHUB_ORG ?= $(shell git config --get remote.origin.url | sed -E 's/.*[:/]([^/]+)\/.*$$/\1/')
GITHUB_REPO ?= ansible-globus
AWS_REGION ?= us-east-1
ENVIRONMENT ?= ci

help:
	@echo "Ansible-Globus Infrastructure Management"
	@echo ""
	@echo "Available targets:"
	@echo "  make check         - Verify AWS account and credentials"
	@echo "  make deploy        - Create infrastructure (via tox)"
	@echo "  make destroy       - Destroy infrastructure (via tox)"
	@echo "  make list-buckets  - List existing token buckets"
	@echo ""
	@echo "Configuration:"
	@echo "  AWS_PROFILE=$(AWS_PROFILE)"
	@echo "  GITHUB_ORG=$(GITHUB_ORG)"
	@echo "  GITHUB_REPO=$(GITHUB_REPO)"
	@echo "  AWS_REGION=$(AWS_REGION)"
	@echo "  ENVIRONMENT=$(ENVIRONMENT)"
	@echo ""
	@echo "Examples:"
	@echo "  make deploy AWS_PROFILE=myprofile"
	@echo "  make destroy AWS_PROFILE=myprofile ENVIRONMENT=staging"
	@echo "  make check AWS_PROFILE=prod"
	@echo ""
	@echo "Direct tox usage:"
	@echo "  aws-vault exec myprofile -- tox -e infra-deploy"
	@echo "  aws-vault exec myprofile -- tox -e infra-destroy"

check:
	@echo "🔍 Checking AWS credentials and account..."
	@echo ""
	aws-vault exec $(AWS_PROFILE) -- aws sts get-caller-identity
	@echo ""
	@echo "✅ Using AWS profile: $(AWS_PROFILE)"
	@read -p "Does this look correct? [y/N] " confirm && [ "$$confirm" = "y" ] || (echo "Aborted." && exit 1)

deploy: check
	@echo ""
	@echo "🚀 Deploying infrastructure via tox..."
	@echo "  GitHub: $(GITHUB_ORG)/$(GITHUB_REPO)"
	@echo "  Environment: $(ENVIRONMENT)"
	@echo "  Region: $(AWS_REGION)"
	@echo ""
	aws-vault exec $(AWS_PROFILE) -- \
		env GITHUB_ORG=$(GITHUB_ORG) \
		    GITHUB_REPO=$(GITHUB_REPO) \
		    AWS_REGION=$(AWS_REGION) \
		    ENVIRONMENT=$(ENVIRONMENT) \
		tox -e infra-deploy

destroy:
	@echo "⚠️  WARNING: This will DELETE the following resources:"
	@echo "  - S3 Bucket: $(GITHUB_ORG)-$(GITHUB_REPO)-globus-tokens-$(ENVIRONMENT)"
	@echo "  - IAM Role: GitHubActions-$(GITHUB_REPO)-$(ENVIRONMENT)"
	@echo ""
	@read -p "Are you sure? Type 'yes' to confirm: " confirm && [ "$$confirm" = "yes" ] || (echo "Aborted." && exit 1)
	@echo ""
	@echo "🗑️  Destroying infrastructure via tox..."
	aws-vault exec $(AWS_PROFILE) -- \
		env GITHUB_ORG=$(GITHUB_ORG) \
		    GITHUB_REPO=$(GITHUB_REPO) \
		    AWS_REGION=$(AWS_REGION) \
		    ENVIRONMENT=$(ENVIRONMENT) \
		tox -e infra-destroy

list-buckets:
	@echo "📦 Listing Globus token buckets..."
	@echo ""
	aws-vault exec $(AWS_PROFILE) -- \
		aws s3 ls | grep globus-tokens || echo "No Globus token buckets found"

# Deploy to multiple environments
deploy-all:
	@echo "🚀 Deploying to all environments..."
	$(MAKE) deploy ENVIRONMENT=ci
	$(MAKE) deploy ENVIRONMENT=staging
	$(MAKE) deploy ENVIRONMENT=prod

# Interactive mode with account verification
deploy-safe:
	@echo "🔐 Safe deployment with account verification"
	@echo ""
	@echo "Step 1: Verify AWS account"
	@aws-vault exec $(AWS_PROFILE) -- aws sts get-caller-identity
	@echo ""
	@echo "Step 2: Verify configuration"
	@echo "  AWS Profile: $(AWS_PROFILE)"
	@echo "  GitHub Org: $(GITHUB_ORG)"
	@echo "  GitHub Repo: $(GITHUB_REPO)"
	@echo "  Environment: $(ENVIRONMENT)"
	@echo "  Region: $(AWS_REGION)"
	@echo ""
	@read -p "Proceed with deployment? [y/N] " confirm && [ "$$confirm" = "y" ] || (echo "Aborted." && exit 1)
	@$(MAKE) deploy

# Dry run (check mode)
dry-run:
	@echo "🔍 Running in check mode via tox (no changes will be made)..."
	aws-vault exec $(AWS_PROFILE) -- \
		env GITHUB_ORG=$(GITHUB_ORG) \
		    GITHUB_REPO=$(GITHUB_REPO) \
		    AWS_REGION=$(AWS_REGION) \
		    ENVIRONMENT=$(ENVIRONMENT) \
		tox -e infra-check
