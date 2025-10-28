"""Pytest configuration for ansible-globus tests."""

import sys
from pathlib import Path

# Add plugins and tests directories to Python path
plugins_path = Path(__file__).parent / "plugins"
tests_path = Path(__file__).parent / "tests"
sys.path.insert(0, str(plugins_path))
sys.path.insert(0, str(tests_path))
