# Release Process

This guide covers how to release a new version of the Ansible Globus Collection to Ansible Galaxy.

## Prerequisites

- [ ] All changes merged to `main` branch
- [ ] All tests passing in CI
- [ ] git-cliff installed: `brew install git-cliff`
- [ ] Ansible Galaxy token configured as GitHub secret: `ANSIBLE_GALAXY_TOKEN`

## Release Steps

### 1. Determine Version Number

Follow [Semantic Versioning](https://semver.org/):

- **0.x.y** - Pre-1.0 development releases
  - **Minor (0.X.0)**: New features, may include breaking changes
  - **Patch (0.1.X)**: Bug fixes only
- **1.x.y** - Stable releases
  - **Major (X.0.0)**: Breaking changes
  - **Minor (1.X.0)**: New features, backward compatible
  - **Patch (1.0.X)**: Bug fixes only

Examples:
- Bug fix: `0.1.0` → `0.1.1`
- New feature: `0.1.0` → `0.2.0`
- First stable: `0.9.0` → `1.0.0`
- Breaking change after 1.0: `1.2.3` → `2.0.0`

### 2. Generate Changelog

The project uses [git-cliff](https://git-cliff.org/) to automatically generate changelogs from [conventional commits](https://www.conventionalcommits.org/).

```bash
# Preview changelog for new version (doesn't write anything)
tox -e changelog-generate -- 0.2.0

# Review the output to ensure it looks correct
```

If the output looks good:

```bash
# Update CHANGELOG.md with new version
tox -e changelog-update -- 0.2.0
```

**Manual review:**
- Open `CHANGELOG.md` and review the generated entries
- Edit if needed (add context, reword, remove noise)
- Ensure the date is correct
- Check that breaking changes are clearly marked

### 3. Update Version in galaxy.yml

```bash
# Edit galaxy.yml
vim galaxy.yml

# Update the version line:
version: 0.2.0
```

Or use sed:
```bash
sed -i '' 's/^version: .*/version: 0.2.0/' galaxy.yml
```

### 4. Run Full Test Suite

```bash
# Run all tests
tox

# Run linting
tox -e lint

# Test the Galaxy build
tox -e galaxy-test
```

Ensure all tests pass before proceeding.

### 5. Commit Release Preparation

```bash
# Stage changes
git add CHANGELOG.md galaxy.yml

# Commit with conventional commit format
git commit -m "chore(release): prepare for 0.2.0"

# Push to GitHub
git push origin main
```

Wait for CI to pass on this commit.

### 6. Create and Push Git Tag

```bash
# Create annotated tag
git tag -a v0.2.0 -m "Release v0.2.0"

# Push tag to GitHub
git push origin v0.2.0
```

**Important:** The tag must match the format `v*` (e.g., `v0.2.0`) to trigger the release workflow.

### 7. Monitor GitHub Actions

Once you push the tag, GitHub Actions will automatically:

1. **Validate** - Ensure tag matches galaxy.yml version
2. **Build** - Build collection with tox
3. **Publish** - Publish to Ansible Galaxy
4. **Release** - Create GitHub Release with tarball
5. **Test** - Verify installation from Galaxy

Monitor the workflow at:
```
https://github.com/m1yag1/ansible-globus/actions
```

### 8. Verify Release

After GitHub Actions completes (usually 2-5 minutes):

#### Verify on Ansible Galaxy
```bash
# Wait a minute for Galaxy indexing
sleep 60

# Install from Galaxy
ansible-galaxy collection install community.globus:0.2.0

# Verify version
ansible-galaxy collection list community.globus
```

Should show:
```
Collection       Version
---------------- -------
community.globus 0.2.0
```

#### Verify on GitHub
- Check GitHub Release: https://github.com/m1yag1/ansible-globus/releases
- Verify tarball is attached
- Verify release notes are correct

#### Verify on Ansible Galaxy
- Check Galaxy page: https://galaxy.ansible.com/ui/repo/published/community/globus/
- Verify new version appears
- Check download count starts incrementing

### 9. Announce Release (Optional)

Consider announcing the release:
- GitHub Discussions
- Project README badge
- Team Slack/Discord
- Social media

## Troubleshooting

### Version Mismatch Error

```
❌ Version mismatch!
   Git tag: v0.2.0
   galaxy.yml: 0.1.0
```

**Fix:** Update `galaxy.yml` to match the tag version.

### CHANGELOG.md Not Updated Warning

```
⚠️ Warning: Version 0.2.0 not found in CHANGELOG.md
```

**Fix:** Run `tox -e changelog-update -- 0.2.0` to update the changelog.

### Galaxy Token Error

```
❌ ANSIBLE_GALAXY_TOKEN not set
```

**Fix:** Add your Ansible Galaxy token to GitHub repository secrets:
1. Get token from: https://galaxy.ansible.com/me/preferences
2. Go to: https://github.com/m1yag1/ansible-globus/settings/secrets/actions
3. Add secret: `ANSIBLE_GALAXY_TOKEN`

### Version Already Exists on Galaxy

```
Error: community.globus:0.2.0 already exists
```

**Fix:** You cannot overwrite published versions. Bump to the next version (e.g., 0.2.1) and try again.

### Build Failed

```
❌ Build failed: tarball not found
```

**Fix:** Check that `galaxy.yml` is valid and all required files exist. Run `tox -e galaxy-build` locally to debug.

### Installation Test Failed

```
⚠️ Version mismatch: expected 0.2.0, got 0.1.0
```

**Fix:** Galaxy may not have indexed the new version yet. Wait 5-10 minutes and the test will pass on retry.

## Hotfix Process

For urgent bug fixes to a released version:

```bash
# 1. Create hotfix branch from tag
git checkout -b hotfix/0.2.1 v0.2.0

# 2. Make fix and commit
git commit -m "fix(critical): resolve data loss issue"

# 3. Update changelog
tox -e changelog-update -- 0.2.1

# 4. Update galaxy.yml version
sed -i '' 's/^version: .*/version: 0.2.1/' galaxy.yml

# 5. Commit
git commit -am "chore(release): prepare for 0.2.1 hotfix"

# 6. Merge to main
git checkout main
git merge hotfix/0.2.1

# 7. Tag and push
git tag -a v0.2.1 -m "Release v0.2.1 (hotfix)"
git push origin main v0.2.1
```

## Release Checklist

Use this checklist for each release:

- [ ] Determine version number (semver)
- [ ] Generate changelog: `tox -e changelog-update -- X.Y.Z`
- [ ] Review and edit `CHANGELOG.md`
- [ ] Update `galaxy.yml` version
- [ ] Run full test suite: `tox`
- [ ] Test Galaxy build: `tox -e galaxy-test`
- [ ] Commit: `git commit -m "chore(release): prepare for X.Y.Z"`
- [ ] Push to main: `git push origin main`
- [ ] Wait for CI to pass
- [ ] Create tag: `git tag -a vX.Y.Z -m "Release vX.Y.Z"`
- [ ] Push tag: `git push origin vX.Y.Z`
- [ ] Monitor GitHub Actions
- [ ] Verify on Ansible Galaxy
- [ ] Verify on GitHub Releases
- [ ] Test installation: `ansible-galaxy collection install community.globus:X.Y.Z`
- [ ] Announce release (if applicable)

## Automation Summary

### What's Automated
- ✅ Changelog generation (from conventional commits)
- ✅ Collection building (via tox)
- ✅ Publishing to Ansible Galaxy (on git tag push)
- ✅ GitHub Release creation (with tarball and notes)
- ✅ Installation verification

### What's Manual
- ⚠️ Deciding version number
- ⚠️ Reviewing/editing generated changelog
- ⚠️ Updating galaxy.yml version
- ⚠️ Creating and pushing git tags

## Version History Example

| Version | Date | Type | Notes |
|---------|------|------|-------|
| 0.1.0 | 2025-10-29 | Initial | First development release |
| 0.1.1 | 2025-11-05 | Patch | Bug fixes for auth module |
| 0.2.0 | 2025-11-15 | Minor | Added compute module |
| 1.0.0 | 2025-12-01 | Major | First stable release |

## Resources

- [Semantic Versioning](https://semver.org/)
- [Conventional Commits](https://www.conventionalcommits.org/)
- [git-cliff Documentation](https://git-cliff.org/)
- [Ansible Galaxy Publishing](https://docs.ansible.com/ansible/latest/dev_guide/developing_collections_publishing.html)
- [Keep a Changelog](https://keepachangelog.com/)
