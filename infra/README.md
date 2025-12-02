# Infrastructure Setup

Ansible playbooks to provision AWS infrastructure for CI/CD testing.

## Quick Setup Guide

Follow these steps to enable integration tests in GitHub Actions:

### 1. Provision AWS Infrastructure

**Option A: Using tox directly (if you have AWS credentials configured)**

```bash
cd infra
env GITHUB_ORG=your-github-username \
    GITHUB_REPO=ansible-globus \
    AWS_REGION=us-east-1 \
    ENVIRONMENT=ci \
    SKIP_CONFIRM=1 \
    tox -e infra-deploy
```

**Option B: Using make + aws-vault (recommended for multiple AWS accounts)**

```bash
# Install aws-vault if not already installed
brew install aws-vault  # macOS

# Configure AWS credentials
aws-vault add your-profile

# Deploy infrastructure
cd infra
make deploy AWS_PROFILE=your-profile GITHUB_ORG=your-github-username
```

This creates an S3 bucket, GitHub OIDC provider, and IAM role. **Save the output** - you'll need the values for step 4!

### 2. Register Globus Native App

1. Go to https://developers.globus.org
2. Create a new **Native App** (not Confidential Client)
3. Add redirect URL: `http://localhost:8080`
4. **Save the Client ID**

**Note:** Scopes are requested dynamically during the OAuth flow (step 3), not configured in the Developer Console.

### 3. Generate OAuth Tokens

```bash
# From project root (use values from step 1 output)
# Using 'test' environment for CI (recommended)
python scripts/setup_oauth_tokens.py \
  --client-id YOUR_NATIVE_APP_CLIENT_ID \
  --bucket your-github-username-ansible-globus-globus-tokens-ci \
  --key globus/ci-tokens.json \
  --namespace ci \
  --environment test

# This will:
# - Open your browser for OAuth consent
# - Request tokens for Globus 'test' environment
# - Store tokens in S3
# - Tokens include refresh tokens (valid for ~6 months)
```

**Globus Environments:**
- `production` - Default production environment
- `test` - Test environment (recommended for CI)
- `sandbox` - Sandbox environment
- `preview` - Preview environment

**Note:** The environment you use here must match the `GLOBUS_SDK_ENVIRONMENT` set in GitHub Actions (currently set to `test`).

### 4. Add GitHub Repository Secrets

Go to your GitHub repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Add these 5 secrets (values from step 1 output):

| Secret Name | Value |
|-------------|-------|
| `AWS_ROLE_ARN` | From step 1 output (e.g. `arn:aws:iam::123456789:role/GitHubActions-ansible-globus-ci`) |
| `AWS_REGION` | `us-east-1` (or your region from step 1) |
| `S3_TOKEN_BUCKET` | From step 1 output (e.g. `m1yag1-ansible-globus-globus-tokens-ci`) |
| `S3_TOKEN_KEY` | `globus/ci-tokens.json` |
| `S3_TOKEN_NAMESPACE` | `ci` |

### 5. Setup GCS Instance for Integration Tests

The GCS integration tests require SSH access to an EC2 instance running Globus Connect Server.

Run the setup playbook against your GCS instance:
```bash
# Ensure AWS credentials are available (for security group updates)
aws-vault exec your-profile -- \
  ansible-playbook -i <gcs-instance-ip>, infra/setup-gcs-endpoint.yml
```

This playbook automatically:
- Fetches GitHub Actions IP ranges from `https://api.github.com/meta`
- Adds them to the EC2 security group for SSH access
- Generates an SSH key pair for GitHub Actions
- Saves the private key locally to `.gcs_ssh_private_key`

Then add the SSH key to GitHub secrets:
```bash
cat .gcs_ssh_private_key | gh secret set GCS_SSH_PRIVATE_KEY
```

### 6. Test It!

```bash
# Push to main branch to trigger integration tests
git push origin main

# Check GitHub Actions tab to see integration tests run
```

**Done!** Your integration tests will now run in CI using OAuth tokens from S3 in the Globus `test` environment.

---

## Local Development with Different Environments

If you want to run tests locally against a specific Globus environment:

```bash
# Set the environment
export GLOBUS_SDK_ENVIRONMENT=test

# Run tests
pytest tests/integration/
```

The Globus SDK automatically reads `GLOBUS_SDK_ENVIRONMENT` to determine which environment to use.

---

## What Gets Provisioned

1. **S3 Bucket**
   - Encrypted (AES256)
   - Versioned
   - Public access blocked
   - For storing Globus OAuth tokens

2. **IAM Role**
   - For GitHub Actions OIDC federation
   - Allows reading/writing tokens from S3
   - Scoped to your specific repo

3. **GitHub OIDC Provider** (if not exists)
   - Enables GitHub Actions to assume IAM roles without long-lived credentials

## Prerequisites

```bash
# Install required Ansible collection
ansible-galaxy collection install -r infra/requirements.yml

# Install aws-vault (if not already installed)
# macOS
brew install aws-vault

# Linux
curl -L -o /usr/local/bin/aws-vault https://github.com/99designs/aws-vault/releases/latest/download/aws-vault-linux-amd64
chmod +x /usr/local/bin/aws-vault

# Configure aws-vault with your AWS credentials
aws-vault add your-profile
```

## Usage

### Using the Makefile with tox (Recommended)

The easiest way to manage infrastructure with aws-vault:

```bash
# Check which AWS account you're using
make check AWS_PROFILE=your-profile

# Deploy infrastructure (with safety checks, via tox)
make deploy AWS_PROFILE=your-profile

# Deploy to a specific environment
make deploy AWS_PROFILE=prod ENVIRONMENT=production

# Destroy infrastructure (with confirmation, via tox)
make destroy AWS_PROFILE=your-profile

# List existing token buckets
make list-buckets AWS_PROFILE=your-profile

# Dry run (check mode)
make dry-run AWS_PROFILE=your-profile
```

The Makefile automatically:
- ✅ Verifies AWS account before deployment
- ✅ Prompts for confirmation
- ✅ Uses aws-vault for secure credential handling
- ✅ Runs ansible-playbook via tox (consistent with test workflow)
- ✅ Shows clear error messages

### Using tox Directly

If you prefer to run tox commands directly:

```bash
# Set environment variables
export GITHUB_ORG=your-username
export GITHUB_REPO=ansible-globus
export AWS_REGION=us-east-1
export ENVIRONMENT=ci

# Deploy via tox
aws-vault exec your-profile -- tox -e infra-deploy

# Destroy via tox
aws-vault exec your-profile -- tox -e infra-destroy

# Check mode (dry run)
aws-vault exec your-profile -- tox -e infra-check
```

### Direct ansible-playbook Usage

If you prefer to run the playbook directly (without tox):

```bash
# Verify which account you're using
aws-vault exec your-profile -- aws sts get-caller-identity

# Run the playbook
aws-vault exec your-profile -- \
  ansible-playbook infra/setup-token-storage.yml \
  -e github_org=your-username \
  -e github_repo=ansible-globus

# With custom environment
aws-vault exec your-profile -- \
  ansible-playbook infra/setup-token-storage.yml \
  -e github_org=your-username \
  -e github_repo=ansible-globus \
  -e environment=staging

# Destroy
aws-vault exec your-profile -- \
  ansible-playbook infra/setup-token-storage.yml \
  -e state=absent
```

### Skip Confirmation (for CI/automation)

```bash
# Skip interactive confirmation
SKIP_CONFIRM=1 make deploy AWS_PROFILE=your-profile

# Or with aws-vault directly
aws-vault exec your-profile -- \
  env SKIP_CONFIRM=1 ansible-playbook infra/setup-token-storage.yml
```

**Note:** This safely deletes the S3 bucket and IAM role. The OIDC provider is left in place as it may be shared by other repositories.

## Configuration Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `github_org` | `your-org` | GitHub organization or username |
| `github_repo` | `ansible-globus` | Repository name |
| `aws_region` | `us-east-1` | AWS region for resources |
| `environment` | `ci` | Environment name (ci/staging/prod) |
| `state` | `present` | `present` to create, `absent` to destroy |

## Multiple Environments

Create separate infrastructure for different environments:

```bash
# CI environment
ansible-playbook infra/setup-token-storage.yml -e environment=ci

# Staging environment
ansible-playbook infra/setup-token-storage.yml -e environment=staging

# Production environment
ansible-playbook infra/setup-token-storage.yml -e environment=prod
```

Each creates a separate bucket and IAM role with the environment suffix.

## Output

After running, you'll get:

```
✅ Infrastructure present complete!

S3 Bucket: your-org-ansible-globus-globus-tokens-ci
Token Path: s3://your-org-ansible-globus-globus-tokens-ci/globus/ci-tokens.json
IAM Role ARN: arn:aws:iam::123456789:role/GitHubActions-ansible-globus-ci

Next steps:
1. Run: python scripts/setup_oauth_tokens.py \
     --bucket your-org-ansible-globus-globus-tokens-ci \
     --key globus/ci-tokens.json \
     --namespace ci

2. Add to GitHub Secrets:
   AWS_ROLE_ARN=arn:aws:iam::123456789:role/GitHubActions-ansible-globus-ci
   S3_TOKEN_BUCKET=your-org-ansible-globus-globus-tokens-ci
   S3_TOKEN_KEY=globus/ci-tokens.json
   S3_TOKEN_NAMESPACE=ci
   AWS_REGION=us-east-1
```

## Security Features

- ✅ Bucket encryption enabled (AES256)
- ✅ Versioning enabled (can recover accidentally deleted tokens)
- ✅ Public access blocked
- ✅ OIDC federation (no long-lived credentials)
- ✅ Least privilege IAM policies
- ✅ Bucket policy enforces encryption

## Cleanup

To remove all infrastructure:

```bash
ansible-playbook infra/setup-token-storage.yml -e state=absent
```

This will:
1. Delete the S3 bucket (including all tokens)
2. Delete the IAM role
3. Delete inline IAM policies
4. Leave OIDC provider (may be used by other repos)

## Troubleshooting

### "Collection amazon.aws not found"

```bash
ansible-galaxy collection install amazon.aws
```

### "Access Denied" when creating resources

Ensure your AWS credentials have permissions for:
- `s3:CreateBucket`, `s3:DeleteBucket`
- `iam:CreateRole`, `iam:DeleteRole`, `iam:PutRolePolicy`
- `iam:CreateOpenIDConnectProvider`

### Bucket already exists

If you get an error that the bucket exists, either:
1. Choose a different `github_org` or `environment`
2. Delete the existing bucket manually
3. Modify `bucket_name` variable in the playbook
