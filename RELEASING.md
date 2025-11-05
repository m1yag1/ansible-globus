# Release Process

This guide covers how to release a new version of the Ansible Globus Collection to Ansible Galaxy.

## Prerequisites

- [ ] All changes merged to `main` branch
- [ ] All tests passing in CI
- [ ] git-cliff installed: `brew install git-cliff`
- [ ] Ansible Galaxy token configured as GitHub secret: `ANSIBLE_GALAXY_TOKEN`

## Release Steps

### Automated Two-Step Process

This project uses automated release tooling that leverages [conventional commits](https://www.conventionalcommits.org/) for version detection.

**Step 1: Prepare Release**

```bash
# Auto-detect version from commits
tox -e prepare-release

# Or manually specify
tox -e prepare-release -- 0.2.0      # Explicit version
tox -e prepare-release -- --minor    # Force minor bump
tox -e prepare-release -- --patch    # Force patch bump
```

This command will:
1. Analyze conventional commits since last tag
2. Suggest version bump based on commit types:
   - `feat:` commits → **minor** bump (0.1.0 → 0.2.0)
   - `fix:` commits → **patch** bump (0.1.0 → 0.1.1)
   - `BREAKING CHANGE:` → **minor** bump in 0.x (pre-1.0)
3. Generate CHANGELOG.md using git-cliff
4. Update galaxy.yml version
5. Leave files unstaged for review

**Step 2: Review Changes (Optional)**

Review and edit the generated files if needed:

```bash
# Review the changelog
cat CHANGELOG.md

# Edit if needed (add context, reword entries, etc.)
vim CHANGELOG.md

# Verify version
grep "^version:" galaxy.yml
```

**Step 3: Complete Release**

```bash
tox -e release
```

This command will:
1. Validate that CHANGELOG.md and galaxy.yml were updated
2. Verify you're on main branch (warns if not)
3. Run `tox -e galaxy-test` to verify build works
4. Ask for confirmation
5. Commit changes with: `chore(release): prepare for X.Y.Z`
6. Create git tag: `vX.Y.Z`
7. Push to GitHub with tags

**Important:** The tag push triggers GitHub Actions to automatically publish to Ansible Galaxy.

### Version Numbering (Pre-1.0)

This project follows [Semantic Versioning](https://semver.org/) with pre-1.0 semantics:

- **Minor (0.X.0)**: New features, breaking changes OK
- **Patch (0.X.Y)**: Bug fixes only

Examples:
- New feature: `0.1.0` → `0.2.0`
- Bug fix: `0.1.0` → `0.1.1`
- Multiple features: `0.15.3` → `0.16.0`
- Expected trajectory: `0.1.0` → ... → `0.100.2` → ... → `1.0.0`

### Manual Release (if needed)

If you need to release manually without the automation:

```bash
# 1. Update CHANGELOG.md manually
vim CHANGELOG.md

# 2. Update galaxy.yml version
sed -i '' 's/^version: .*/version: 0.2.0/' galaxy.yml

# 3. Test build
tox -e galaxy-test

# 4. Commit and tag
git add CHANGELOG.md galaxy.yml
git commit -m "chore(release): prepare for 0.2.0"
git tag -a v0.2.0 -m "Release v0.2.0"
git push origin main v0.2.0
```

### Monitor GitHub Actions

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
ansible-galaxy collection install m1yag1.globus:0.2.0

# Verify version
ansible-galaxy collection list m1yag1.globus
```

Should show:
```
Collection       Version
---------------- -------
m1yag1.globus 0.2.0
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
Error: m1yag1.globus:0.2.0 already exists
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

- [ ] All changes merged to main
- [ ] All CI tests passing
- [ ] Run: `tox -e prepare-release` (or with version override)
- [ ] Review generated `CHANGELOG.md` (edit if needed)
- [ ] Verify `galaxy.yml` version is correct
- [ ] Run: `tox -e release`
- [ ] Confirm when prompted (validates, tests, commits, tags, pushes)
- [ ] Monitor GitHub Actions: https://github.com/m1yag1/ansible-globus/actions
- [ ] Verify on Ansible Galaxy: https://galaxy.ansible.com/ui/repo/published/community/globus/
- [ ] Verify GitHub Release: https://github.com/m1yag1/ansible-globus/releases
- [ ] Test installation: `ansible-galaxy collection install m1yag1.globus:X.Y.Z`
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
