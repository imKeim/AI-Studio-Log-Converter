# tests/test_converter.py

import sys
from pathlib import Path
from datetime import datetime
import pytest # Import pytest to use its features

# Add the project root to the path to allow imports from the 'src' directory
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.converter import get_clean_title, _check_for_gdrive_links, process_files
from src.config import ASSETS_DIR_NAME

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

# --- Tests for functions with file I/O operations ---

@pytest.mark.parametrize("attachment_key", [
    "driveImage",
    "driveDocument",
    "driveVideo"
])
def test_process_files_gdrive_indicator_for_all_types(attachment_key, tmp_path, minimal_config):
    """
    This is a parameterized test. It runs for every attachment type to ensure
    the GDrive indicator is added correctly for all of them.
    """
    # 1. Setup
    source_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    source_dir.mkdir()
    output_dir.mkdir()

    # Dynamically create the JSON content with the current attachment key
    source_file = source_dir / "test_log_with_gdrive"
    source_file.write_text(f'{{"chunkedPrompt": {{"chunks": [{{"role": "user", "{attachment_key}": {{"id": "123"}}}}]}}}}')

    # 2. Execution
    process_files(
        files_to_process=[source_file],
        output_dir=output_dir,
        overwrite=True,
        config=minimal_config,
        lang_templates={'user_header': 'User', 'model_header': 'Model'},
        frontmatter_template="",
        fast_mode=False
    )

    # 3. Assertion
    date_str = datetime.fromtimestamp(source_file.stat().st_mtime).strftime(minimal_config['date_format'])
    expected_filename = f"{date_str} - [A] test_log_with_gdrive.md"
    expected_file_path = output_dir / expected_filename
    assert expected_file_path.exists()

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
    source_file.write_text('{"chunkedPrompt": {"chunks": [{"role": "user", "driveImage": {"id": "123"}}]}}')

    # 2. Execution, but with fast_mode=True
    process_files(
        files_to_process=[source_file],
        output_dir=output_dir,
        overwrite=True,
        config=minimal_config,
        lang_templates={'user_header': 'User', 'model_header': 'Model'},
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

def test_process_files_saves_embedded_image(tmp_path, minimal_config):
    """
    Tests the critical old functionality: saving a base64 embedded image.
    """
    # 1. Setup
    source_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    source_dir.mkdir()
    output_dir.mkdir()

    source_file = source_dir / "log_with_image"
    # This is a real 1x1 pixel PNG in base64
    image_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
    # The JSON now includes "role": "user" to be realistic
    source_file.write_text(f'{{"chunkedPrompt": {{"chunks": [{{"role": "user", "parts": [{{"inlineData": {{"mimeType": "image/png", "data": "{image_b64}"}}}}]}}]}}}}')

    # 2. Execution
    process_files(
        files_to_process=[source_file],
        output_dir=output_dir,
        overwrite=True,
        config=minimal_config,
        lang_templates={'user_header': 'User', 'model_header': 'Model'}, # Minimal templates
        frontmatter_template="",
        fast_mode=False
    )

    # 3. Assertion
    date_str = datetime.fromtimestamp(source_file.stat().st_mtime).strftime(minimal_config['date_format'])
    md_filename = f"{date_str} - log_with_image.md"
    md_filepath = output_dir / md_filename
    
    # Check 1: The markdown file was created
    assert md_filepath.exists()

    # Check 2: The assets directory was created
    assets_path = output_dir / ASSETS_DIR_NAME
    assert assets_path.exists()
    assert assets_path.is_dir()

    # Check 3: An image file was created inside the assets directory
    saved_images = list(assets_path.glob("*.png"))
    assert len(saved_images) == 1
    
    # Check 4: The markdown file contains the correct link to the image
    image_link_text = f"![[{saved_images[0].name}]]"
    assert image_link_text in md_filepath.read_text(encoding='utf-8')