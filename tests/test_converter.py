# tests/test_converter.py

import sys
from pathlib import Path
from datetime import datetime

# Add the project root to the path to allow imports from the 'src' directory
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.converter import get_clean_title, _check_for_gdrive_links, process_files

# --- Tests for simple, pure functions ---

def test_get_clean_title():
    """Tests that the function correctly removes the date prefix from a title."""
    assert get_clean_title("2025-08-15 - My Awesome Log") == "My Awesome Log"
    assert get_clean_title("Log without date") == "Log without date"
    # The function should return the original string if the pattern doesn't fully match
    assert get_clean_title("2025-08-15 -") == "2025-08-15 -"

def test_check_for_gdrive_links_positive(log_data_with_gdrive):
    """
    Tests that the function finds a GDrive link when one is present.
    Note: We just pass the fixture name as an argument to the test function.
    """
    assert _check_for_gdrive_links(log_data_with_gdrive) is True

def test_check_for_gdrive_links_negative(log_data_without_gdrive):
    """Tests that the function does NOT find a GDrive link when it is absent."""
    assert _check_for_gdrive_links(log_data_without_gdrive) is False

# --- Test for a function with file I/O operations ---

def test_process_files_gdrive_indicator(tmp_path, minimal_config):
    """
    This is the main integration test. It checks if process_files correctly
    creates a filename with the GDrive indicator.
    `tmp_path` is a built-in pytest fixture that provides a temporary directory.
    """
    # 1. Setup: Prepare the environment inside the temporary directory
    source_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    source_dir.mkdir()
    output_dir.mkdir()

    # Create a test log file in the temporary source directory
    source_file = source_dir / "test_log_with_gdrive"
    source_file.write_text('{"chunkedPrompt": {"chunks": [{"driveImage": {"id": "123"}}]}}')

    # 2. Execution: Run the function we want to test
    process_files(
        files_to_process=[source_file],
        output_dir=output_dir,
        overwrite=True,
        config=minimal_config,
        lang_templates={},      # Not needed for this test
        frontmatter_template="", # Not needed for this test
        fast_mode=False          # Must be False for the feature to be active
    )

    # 3. Assertion: Check if the result is what we expect
    # Construct the expected output filename
    date_str = datetime.fromtimestamp(source_file.stat().st_mtime).strftime(minimal_config['date_format'])
    expected_filename = f"{date_str} - [A] test_log_with_gdrive.md"
    expected_file_path = output_dir / expected_filename

    # The main assertion: does the file with the CORRECT name exist?
    assert expected_file_path.exists()

    # An additional assertion: ensure that a file WITHOUT the indicator was NOT created
    unexpected_filename = f"{date_str} - test_log_with_gdrive.md"
    unexpected_file_path = output_dir / unexpected_filename
    assert not unexpected_file_path.exists()

def test_process_files_gdrive_indicator_is_skipped_in_fast_mode(tmp_path, minimal_config):
    """
    Tests that the GDrive indicator is NOT added when fast_mode is True,
    even if the file contains a GDrive link.
    """
    # 1. Setup
    source_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    source_dir.mkdir()
    output_dir.mkdir()

    source_file = source_dir / "test_log_with_gdrive"
    source_file.write_text('{"chunkedPrompt": {"chunks": [{"driveImage": {"id": "123"}}]}}')

    # 2. Execution, but with fast_mode=True
    process_files(
        files_to_process=[source_file],
        output_dir=output_dir,
        overwrite=True,
        config=minimal_config,
        lang_templates={},
        frontmatter_template="",
        fast_mode=True # The key difference is here!
    )

    # 3. Assertion (the opposite of the previous test)
    date_str = datetime.fromtimestamp(source_file.stat().st_mtime).strftime(minimal_config['date_format'])
    
    # The expected filename should NOT have the indicator
    expected_filename = f"{date_str} - test_log_with_gdrive.md"
    expected_file_path = output_dir / expected_filename
    
    # Assert that the file WITHOUT the indicator exists
    assert expected_file_path.exists()

    # Assert that the file WITH the indicator does NOT exist
    unexpected_filename = f"{date_str} - [A] test_log_with_gdrive.md"
    unexpected_file_path = output_dir / unexpected_filename
    assert not unexpected_file_path.exists()