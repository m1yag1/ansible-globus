#!/usr/bin/env python3
"""
Complete the release by committing, tagging, and pushing.

This script:
1. Validates that CHANGELOG.md and galaxy.yml were updated
2. Runs tox -e galaxy-test to verify build
3. Commits changes with conventional commit message
4. Tags with version
5. Pushes to GitHub

Run via: tox -e release
Or: python scripts/release.py --commit  # Non-interactive mode
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


def get_version_from_galaxy():
    """Read version from galaxy.yml."""
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


def check_changelog_updated(version):
    """Check if CHANGELOG.md has entry for version."""
    changelog = Path("CHANGELOG.md")
    if not changelog.exists():
        print("❌ CHANGELOG.md not found")
        return False

    content = changelog.read_text()
    # Look for [X.Y.Z] in changelog
    pattern = rf"\[{re.escape(version)}\]"
    if not re.search(pattern, content):
        print(f"❌ CHANGELOG.md does not contain entry for [{version}]")
        print("   Did you run: tox -e prepare-release")
        return False

    return True


def check_git_status():
    """Check that CHANGELOG.md and galaxy.yml are modified."""
    result = run_command("git status --porcelain", check=True)
    status = result.stdout.strip()

    if not status:
        print("❌ No changes to commit")
        print("   Did you run: tox -e prepare-release")
        return False

    lines = status.split("\n")
    modified_files = [line.split()[-1] for line in lines if line]

    required = {"CHANGELOG.md", "galaxy.yml"}
    found = set(modified_files) & required

    if found != required:
        missing = required - found
        print(f"❌ Expected changes not found: {', '.join(missing)}")
        print(f"   Modified files: {', '.join(modified_files)}")
        print("   Did you run: tox -e prepare-release")
        return False

    return True


def check_branch():
    """Ensure we're on main branch."""
    result = run_command("git branch --show-current", check=True)
    branch = result.stdout.strip()

    if branch != "main":
        print(f"⚠️  Warning: Not on main branch (current: {branch})")
        response = input("Continue anyway? [y/N] ")
        if response.lower() != "y":
            print("Aborted")
            sys.exit(1)


def run_galaxy_test():
    """Run galaxy build test."""
    print("\n🧪 Testing Galaxy build...")
    result = run_command("tox -e galaxy-test", check=False, capture=False)

    if result.returncode != 0:
        print("\n❌ Galaxy build test failed")
        print("   Fix the issues and try again")
        sys.exit(1)

    print("✓ Galaxy build test passed")


def main():
    parser = argparse.ArgumentParser(description="Complete the release process")
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Skip confirmation prompt and proceed with release",
    )
    args = parser.parse_args()

    print("🚀 Completing release...\n")

    # Get version
    version = get_version_from_galaxy()
    print(f"Version: {version}")

    # Validations
    print("\n📋 Validating...")

    if not check_changelog_updated(version):
        sys.exit(1)
    print("✓ CHANGELOG.md updated")

    if not check_git_status():
        sys.exit(1)
    print("✓ Git status valid")

    check_branch()
    print("✓ Branch check passed")

    # Run tests
    run_galaxy_test()

    # Confirm before proceeding (unless --commit flag is used)
    print("\n" + "=" * 60)
    print(f"Ready to release v{version}")
    print("=" * 60)
    print("\nThis will:")
    print("  1. Commit CHANGELOG.md and galaxy.yml")
    print(f"  2. Create git tag v{version}")
    print("  3. Push to origin with tags")
    print("\nGitHub Actions will then automatically publish to Ansible Galaxy.")
    print()

    if not args.commit:
        response = input("Proceed? [y/N] ")
        if response.lower() != "y":
            print("Aborted")
            sys.exit(0)
    else:
        print("--commit flag provided, proceeding without confirmation...")

    # Git operations
    print("\n📝 Committing changes...")
    run_command("git add CHANGELOG.md galaxy.yml", check=True, capture=False)

    commit_msg = f"chore(release): prepare for {version}"
    run_command(f'git commit -m "{commit_msg}"', check=True, capture=False)
    print(f"✓ Committed: {commit_msg}")

    print(f"\n🏷️  Creating tag v{version}...")
    run_command(
        f'git tag -a v{version} -m "Release v{version}"', check=True, capture=False
    )
    print(f"✓ Tagged: v{version}")

    print("\n⬆️  Pushing to GitHub...")
    result = run_command("git push origin main", check=False, capture=False)
    if result.returncode != 0:
        print("❌ Failed to push to main")
        print("   You may need to manually push and tag")
        sys.exit(1)

    result = run_command(f"git push origin v{version}", check=False, capture=False)
    if result.returncode != 0:
        print("❌ Failed to push tag")
        print(f"   You may need to manually push tag: git push origin v{version}")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("✅ Release completed successfully!")
    print("=" * 60)
    print(f"\n🎉 Version {version} released!")
    print("\n📦 Check GitHub Actions for publishing status:")
    print("   https://github.com/m1yag1/ansible-globus/actions")
    print("\n🌐 Once published, verify on Ansible Galaxy:")
    print("   https://galaxy.ansible.com/ui/repo/published/community/globus/")
    print("\n📋 GitHub Release:")
    print(f"   https://github.com/m1yag1/ansible-globus/releases/tag/v{version}")
    print()


if __name__ == "__main__":
    main()
