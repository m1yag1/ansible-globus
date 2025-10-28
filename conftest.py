"""Pytest configuration for ansible-globus tests."""

import sys
from pathlib import Path

# Add plugins directory to Python path
plugins_path = Path(__file__).parent / "plugins"
sys.path.insert(0, str(plugins_path))
