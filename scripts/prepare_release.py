#!/usr/bin/env python3
"""
Prepare a release by updating CHANGELOG.md and galaxy.yml version.

This script:
1. Detects version bump from conventional commits
2. Updates CHANGELOG.md using git-cliff
3. Updates galaxy.yml version
4. Prints review instructions

Run via: tox -e prepare-release [-- --patch|--minor|X.Y.Z]
"""

import argparse
import re
import subprocess  # nosec B404 - Internal release automation script
import sys
from pathlib import Path


def run_command(cmd, check=True, capture=True):
    """Run a shell command and return output."""
    result = subprocess.run(  # nosec B602 - Internal release automation
        cmd,
        shell=True,  # Needed for git commands
        capture_output=capture,
        text=True,
        check=False,
    )
    if check and result.returncode != 0:
        print(f"❌ Command failed: {cmd}")
        if result.stderr:
            print(result.stderr)
        sys.exit(1)
    return result


def get_current_version():
    """Read current version from galaxy.yml."""
    galaxy_yml = Path("galaxy.yml")
    if not galaxy_yml.exists():
        print("❌ galaxy.yml not found")
        sys.exit(1)

    content = galaxy_yml.read_text()
    match = re.search(r'^version:\s*["\']?([0-9.]+)["\']?', content, re.MULTILINE)
    if not match:
        print("❌ Could not find version in galaxy.yml")
        sys.exit(1)

    return match.group(1)


def get_last_tag():
    """Get the most recent git tag."""
    result = run_command("git describe --tags --abbrev=0 2>/dev/null", check=False)
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def analyze_commits(since_ref):
    """Analyze conventional commits since a ref."""
    if since_ref:
        cmd = f"git log {since_ref}..HEAD --pretty=format:%s"
    else:
        cmd = "git log --pretty=format:%s"

    result = run_command(cmd, check=False)
    if result.returncode != 0:
        return {"feat": 0, "fix": 0, "breaking": 0, "other": 0}

    commits = result.stdout.strip().split("\n")
    stats = {"feat": 0, "fix": 0, "breaking": 0, "other": 0}

    for commit in commits:
        if not commit:
            continue
        if (
            "BREAKING CHANGE" in commit
            or commit.startswith("feat!:")
            or commit.startswith("fix!:")
        ):
            stats["breaking"] += 1
        elif commit.startswith("feat"):
            stats["feat"] += 1
        elif commit.startswith("fix"):
            stats["fix"] += 1
        else:
            stats["other"] += 1

    return stats


def suggest_version(current, stats):
    """Suggest next version based on commit stats."""
    parts = [int(x) for x in current.split(".")]
    major, minor, patch = parts[0], parts[1], parts[2]

    # Pre-1.0: feat/breaking → minor, fix → patch
    if stats["feat"] > 0 or stats["breaking"] > 0:
        return f"{major}.{minor + 1}.0"
    elif stats["fix"] > 0:
        return f"{major}.{minor}.{patch + 1}"
    else:
        # No version-bumping commits
        return None


def bump_version(current, bump_type):
    """Bump version based on type."""
    parts = [int(x) for x in current.split(".")]
    major, minor, patch = parts[0], parts[1], parts[2]

    if bump_type == "patch":
        return f"{major}.{minor}.{patch + 1}"
    elif bump_type == "minor":
        return f"{major}.{minor + 1}.0"
    else:
        print(f"❌ Unknown bump type: {bump_type}")
        sys.exit(1)


def update_galaxy_yml(new_version):
    """Update version in galaxy.yml."""
    galaxy_yml = Path("galaxy.yml")
    content = galaxy_yml.read_text()

    updated = re.sub(
        r'^(version:\s*)["\']?[0-9.]+["\']?',
        rf"\g<1>{new_version}",
        content,
        flags=re.MULTILINE,
    )

    galaxy_yml.write_text(updated)


def update_changelog(new_version):
    """Update CHANGELOG.md using git-cliff."""
    # Check if git-cliff is installed
    result = run_command("which git-cliff", check=False)
    if result.returncode != 0:
        print("❌ git-cliff not found. Install with: brew install git-cliff")
        sys.exit(1)

    # Generate changelog
    print(f"📝 Generating changelog for v{new_version}...")
    cmd = f"git-cliff --tag v{new_version} --output CHANGELOG.md"
    result = run_command(cmd, check=True)


def main():
    parser = argparse.ArgumentParser(description="Prepare a release")
    parser.add_argument(
        "version",
        nargs="?",
        help="Version (X.Y.Z) or bump type (--patch, --minor)",
    )
    args = parser.parse_args()

    print("📦 Preparing release...\n")

    # Get current version
    current = get_current_version()
    print(f"Current version: {current}")

    # Get last tag
    last_tag = get_last_tag()
    if last_tag:
        print(f"Last tag: {last_tag}")
    else:
        print("No previous tags found")

    # Analyze commits
    print(f"Analyzing commits since {last_tag or 'beginning'}...\n")
    stats = analyze_commits(last_tag)

    # Determine new version
    new_version = None

    if args.version:
        # Explicit version or bump type
        if args.version in ["--patch", "--minor"]:
            bump_type = args.version.removeprefix("--")
            new_version = bump_version(current, bump_type)
            print(f"Manual {bump_type} bump: {current} → {new_version}")
        elif re.match(r"^\d+\.\d+\.\d+$", args.version):
            new_version = args.version
            print(f"Manual version: {current} → {new_version}")
        else:
            print(f"❌ Invalid version: {args.version}")
            print("Use: X.Y.Z, --patch, or --minor")
            sys.exit(1)
    else:
        # Auto-detect from commits
        print("Found commits:")
        if stats["feat"] > 0:
            print(f"  - {stats['feat']} feat commit(s)")
        if stats["fix"] > 0:
            print(f"  - {stats['fix']} fix commit(s)")
        if stats["breaking"] > 0:
            print(f"  - {stats['breaking']} breaking change(s)")
        if stats["other"] > 0:
            print(f"  - {stats['other']} other commit(s)")

        new_version = suggest_version(current, stats)
        if not new_version:
            print("\n⚠️  No version-bumping commits found (feat/fix)")
            print("Use manual version: tox -e prepare-release -- 0.X.Y")
            sys.exit(1)

        bump_type = "minor" if (stats["feat"] > 0 or stats["breaking"] > 0) else "patch"
        print(f"\nSuggested: {new_version} ({bump_type} bump)")

    print()

    # Update files
    update_changelog(new_version)
    print("✓ Updated CHANGELOG.md")

    update_galaxy_yml(new_version)
    print(f"✓ Updated galaxy.yml ({current} → {new_version})")

    # Print next steps
    print("\n" + "=" * 60)
    print("✅ Release prepared!")
    print("=" * 60)
    print("\n📋 Review the changes:")
    print("   - CHANGELOG.md (edit if needed)")
    print(f"   - galaxy.yml (version: {new_version})")
    print("\n🚀 When ready, complete the release:")
    print("   tox -e release")
    print()


if __name__ == "__main__":
    main()
