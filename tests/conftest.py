# tests/conftest.py

import pytest
import json
from pathlib import Path

@pytest.fixture
def log_data_with_gdrive():
    """A fixture that loads and returns data from a log with a GDrive link."""
    path = Path(__file__).parent / "data" / "log_with_gdrive.json"
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

@pytest.fixture
def log_data_without_gdrive():
    """A fixture that loads and returns data from a log WITHOUT a GDrive link."""
    path = Path(__file__).parent / "data" / "log_without_gdrive.json"
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

@pytest.fixture
def minimal_config():
    """A fixture that provides a minimal config dictionary for tests."""
    return {
        'enable_gdrive_indicator': True,
        'gdrive_filename_indicator': "[A] ",
        'filename_template': "{date} - {gdrive_indicator}{basename}.md",
        'date_format': "%Y-%m-%d",
        # Add other keys to prevent KeyErrors in the tested functions
        'enable_frontmatter': False,
        'enable_metadata_table': False,
        'enable_grounding_metadata': False,
    }