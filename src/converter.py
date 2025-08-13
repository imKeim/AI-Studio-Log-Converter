import json
import os
import re
import base64
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, unquote
from tqdm import tqdm
import sys
from colorama import Fore, Style

# This import is needed for the ignore_filenames list
from .config import CONFIG_FILE_NAME, CRASH_LOG_FILE, ASSETS_DIR_NAME

__all__ = [
    "get_clean_title",
    "save_image_from_base64",
    "format_grounding_data",
    "convert_llm_log_to_markdown",
    "find_json_files",
    "process_files",
]

# --- Private Helper Functions for Refactoring ---

def _read_log_data(json_path: Path) -> tuple[dict | None, str]:
    """Reads and parses the JSON log file."""
    try:
        return json.loads(json_path.read_text(encoding='utf-8')), ""
    except json.JSONDecodeError as e:
        return None, f"Invalid JSON format. Details: {e}"
    except Exception as e:
        return None, f"Failed to read file. Details: {e}"

def _check_for_gdrive_links(log_data: dict) -> bool:
    """Efficiently scans log data for any Google Drive attachment references."""
    # A list of all known keys for Google Drive attachments.
    ATTACHMENT_KEYS = ["driveImage", "driveDocument", "driveVideo"]
    
    chunks = log_data.get('chunkedPrompt', {}).get('chunks') or log_data.get('history', [])
    for chunk in chunks:
        # Check if any of the attachment keys exist in the chunk itself.
        if any(key in chunk for key in ATTACHMENT_KEYS):
            return True
        # Also check within the 'parts' list of a chunk.
        for part in chunk.get('parts', []):
            if any(key in part for key in ATTACHMENT_KEYS):
                return True
    return False

def _build_frontmatter(json_path: Path, title: str, template: str, has_gdrive_link: bool, config: dict) -> str:
    """Builds the YAML frontmatter block."""
    try:
        mtime = datetime.fromtimestamp(json_path.stat().st_mtime)
        cdate = mtime.strftime('%Y-%m-%d %H:%M:%S')
        mdate = cdate
        
        # Format the main template
        frontmatter = template.format(title=title, cdate=cdate, mdate=mdate).strip()
        
        # If a GDrive link exists, add the specific tag
        if has_gdrive_link and config.get('enable_gdrive_indicator', False):
            tag_to_add = config.get('gdrive_frontmatter_tag', 'has-gdrive-attachment')
            # A simple but effective way to add the tag
            if "tags:" in frontmatter:
                frontmatter = frontmatter.replace("tags:", f"tags: {tag_to_add}", 1)
        
        return frontmatter
    except FileNotFoundError:
        return ""

def _build_metadata_table(log_data: dict, lang_templates: dict) -> str:
    """Builds the Markdown table with run settings."""
    run_settings = log_data.get('runSettings', {})
    if not run_settings:
        return ""

    loc = lang_templates.get('metadata_table', {})
    header_param = loc.get('header_parameter', 'Parameter')
    header_value = loc.get('header_value', 'Value')
    
    table_rows = []
    
    model_name = run_settings.get('model', 'N/A')
    clean_model_name = model_name.split('/')[-1]
    table_rows.append(f"| {loc.get('model', '**Model**')} | `{clean_model_name}` |")
    
    if 'temperature' in run_settings:
        table_rows.append(f"| {loc.get('temperature', '**Temperature**')} | `{run_settings['temperature']}` |")
    if 'topP' in run_settings:
        table_rows.append(f"| {loc.get('top_p', '**Top-P**')} | `{run_settings['topP']}` |")
    if 'topK' in run_settings:
        table_rows.append(f"| {loc.get('top_k', '**Top-K**')} | `{run_settings['topK']}` |")

    search_enabled = 'googleSearch' in run_settings or run_settings.get('enableSearchAsATool', False)
    search_text = loc.get('search_enabled', 'Enabled') if search_enabled else loc.get('search_disabled', 'Disabled')
    table_rows.append(f"| {loc.get('web_search', '**Web Search**')} | {search_text} |")
    
    table_header = f"| {header_param} | {header_value} |\n| :--- | :--- |"
    return table_header + "\n" + "\n".join(table_rows)

def _build_conversation_turns(log_data: dict, md_path: Path, config: dict, lang_templates: dict) -> str:
    """Builds the main conversation part of the Markdown file."""
    system_instruction = (log_data.get('systemInstruction', {}).get('text') or '').strip()
    prompt_data = log_data.get('chunkedPrompt', {})
    chunks = prompt_data.get('chunks') or prompt_data.get('pendingInputs') or log_data.get('history', [])
    
    if not system_instruction and not chunks:
        return ""

    conversation_turns = []
    i = 0
    while i < len(chunks):
        current_role = chunks[i].get('role')
        if not current_role:
            i += 1
            continue

        turn_chunks = []
        j = i
        while j < len(chunks) and chunks[j].get('role') == current_role:
            turn_chunks.append(chunks[j])
            j += 1
        
        turn_content = []
        pending_thoughts = []
        grounding_data = None
        header = lang_templates.get(f"{current_role}_header", f"## {current_role.capitalize()}")

        if i == 0 and current_role == 'user' and system_instruction:
            spoiler_header = lang_templates.get('system_instruction_header', 'System Instruction ⚙️')
            spoiler_template = lang_templates.get('system_instruction_template', '> [!note]- {header}\n> {text}')
            indented_system_text = system_instruction.replace('\n', '\n> ')
            spoiler_block = spoiler_template.format(header=spoiler_header, text=indented_system_text)
            turn_content.append(spoiler_block)

        for chunk in turn_chunks:
            if current_role == 'model' and chunk.get('isThought'):
                thought_text = (chunk.get('text') or '').strip()
                if thought_text:
                    thought_block = lang_templates['thought_block_template'].format(thought_text=thought_text.replace(chr(10), chr(10) + '> '))
                    pending_thoughts.append(thought_block)
                continue
            
            if 'grounding' in chunk:
                grounding_data = chunk.get('grounding')
            if 'text' in chunk:
                turn_content.append(chunk.get('text', '').strip())
            
            # Handle all known Google Drive attachment types
            attachment_keys = {"driveImage": "Image", "driveDocument": "Document", "driveVideo": "Video"}
            for key, label in attachment_keys.items():
                if attachment_data := chunk.get(key):
                    if drive_id := attachment_data.get('id'):
                        title = unquote(attachment_data.get('title', f"{label} from Google Drive"))
                        turn_content.append(f"[{title} (ID: {drive_id})](https://drive.google.com/file/d/{drive_id})")

            if youtube_video_data := chunk.get('youtubeVideo'):
                if video_id := youtube_video_data.get('id'):
                    turn_content.append(f"[YouTube Video (ID: {video_id})](https://www.youtube.com/watch?v={video_id})")

            if inline_data := chunk.get('inlineData'):
                if b64_data := inline_data.get('data'):
                    if mime_type := inline_data.get('mimeType'):
                        turn_content.append(save_image_from_base64(b64_data, mime_type, md_path))

            for part in chunk.get('parts', []):
                part_content = []
                if 'text' in part:
                    part_content.append(part.get('text', '').strip())
                
                elif inline_data := part.get('inlineData'):
                    if b64_data := inline_data.get('data'):
                        if mime_type := inline_data.get('mimeType'):
                            part_content.append(save_image_from_base64(b64_data, mime_type, md_path))
                
                # Handle all known Google Drive attachment types within parts
                for key, label in attachment_keys.items():
                    if attachment_data := part.get(key):
                        if drive_id := attachment_data.get('id'):
                            title = unquote(attachment_data.get('title', f"{label} from Google Drive"))
                            part_content.append(f"[{title} (ID: {drive_id})](https://drive.google.com/file/d/{drive_id})")
                
                full_part_text = "".join(part_content)
                if not any(full_part_text in content_part for content_part in turn_content):
                    turn_content.extend(part_content)

        if current_role == 'model':
            if pending_thoughts:
                turn_content = pending_thoughts + turn_content
            if grounding_data and config.get('enable_grounding_metadata', False):
                turn_content.append(format_grounding_data(grounding_data, lang_templates))

        if turn_content:
            conversation_turns.append(f"{header}\n\n" + "\n\n".join(filter(None, turn_content)))
        
        i = j

    return "\n\n***\n\n".join(conversation_turns)

def _write_markdown_file(md_path: Path, content: str) -> tuple[bool, str]:
    """Writes the final content to the Markdown file."""
    try:
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(content, encoding='utf-8')
        return True, ""
    except IOError as e:
        return False, f"Could not write output file. Details: {e}"

# --- Public Functions ---

def get_clean_title(base_title: str) -> str:
    """
    Extracts a clean, human-readable title from a filename string.

    Many log files are prefixed with a date (e.g., "2023-10-27 - My Conversation").
    This function strips that date prefix, returning only the descriptive part of the title.
    If the filename doesn't match the expected pattern, it returns the original string.
    """
    match = re.match(r"^\d{4}-\d{2}-\d{2} - (.*)", base_title)
    if match:
        return match.group(1)
    return base_title

def save_image_from_base64(base64_data: str, mime_type: str, md_path: Path) -> str:
    """
    Decodes a base64 encoded image string and saves it to a file.

    This function is used to handle images embedded directly in the log data.
    It creates an 'assets' subdirectory relative to the Markdown file's location,
    saves the image with a unique name, and returns a Markdown link formatted for
    Obsidian-style embedding.

    Args:
        base64_data (str): The base64-encoded image data.
        mime_type (str): The MIME type of the image (e.g., 'image/png'), used to determine the file extension.
        md_path (Path): The path to the output Markdown file, used to determine where to save the assets.

    Returns:
        str: An Obsidian-style Markdown link to the saved image, or an error message if saving fails.
    """
    assets_path = md_path.parent / ASSETS_DIR_NAME
    assets_path.mkdir(exist_ok=True)
    
    extension = mime_type.split('/')[-1]
    timestamp = int(datetime.now().timestamp() * 1000)
    image_filename = f"{md_path.stem}_img_{timestamp}.{extension}"
    image_path = assets_path / image_filename
    
    try:
        image_data = base64.b64decode(base64_data)
        with open(image_path, 'wb') as f:
            f.write(image_data)
        return f"![[{image_filename}]]"
    except (base64.binascii.Error, IOError) as e:
        return f"[Error saving image: {e}]"

def format_grounding_data(grounding_data: dict, lang_templates: dict) -> str:
    """
    Formats the grounding (search and sources) data into a collapsible Markdown block.

    When the model uses web search, the log contains "grounding" data, which includes
    the search queries used and the sources it found. This function takes that data
    and formats it into a clean, user-friendly "spoiler" or "callout" block in Markdown,
    so the user can easily see the model's sources.

    Args:
        grounding_data (dict): A dictionary containing the 'webSearchQueries' and 'groundingSources'.
        lang_templates (dict): A dictionary for localization, providing the text for headers.

    Returns:
        str: A formatted multi-line string for embedding in the final Markdown file.
    """
    loc = lang_templates.get('grounding_metadata', {})
    spoiler_header = loc.get('spoiler_header', "Sources Used")
    queries_header = loc.get('queries_header', "**Search Queries:**")
    sources_header = loc.get('sources_header', "**Sources:**")
    
    content = [f"> [!info]- {spoiler_header}"]
    
    queries = grounding_data.get('webSearchQueries', [])
    if queries:
        content.append(f"> {queries_header}")
        for query in queries:
            content.append(f"> - `{query}`")
    
    sources = grounding_data.get('groundingSources', [])
    if sources:
        if queries: content.append(">")
        content.append(f"> {sources_header}")
        for source in sources:
            uri = source.get('uri')
            title = source.get('title') or urlparse(uri).hostname if uri else "Source"
            num = source.get('referenceNumber', '')
            content.append(f"> {num}. [{title}]({uri})")
            
    return "\n".join(content)

def convert_llm_log_to_markdown(log_data: dict, json_path: Path, md_path: Path, config: dict, lang_templates: dict, frontmatter_template: str, has_gdrive_link: bool) -> (bool, str):
    """
    Converts a single AI Studio JSON log file into a structured Markdown file.

    This function now acts as a high-level orchestrator, delegating tasks
    to smaller, specialized helper functions. It receives pre-parsed log_data
    for efficiency.

    Args:
        log_data (dict): The pre-parsed content of the JSON log file.
        json_path (Path): The path to the original input JSON log file (for metadata).
        md_path (Path): The path where the output Markdown file will be saved.
        config (dict): A dictionary of user-defined configuration settings.
        lang_templates (dict): A dictionary containing localized strings for UI elements.
        frontmatter_template (str): A string template for the YAML frontmatter.
        has_gdrive_link (bool): A flag indicating if a GDrive link was found.

    Returns:
        tuple[bool, str]: A tuple containing a boolean indicating success (True) or failure (False),
                          and a string with an error message if the conversion failed.
    """
    # Check for essential content.
    if not log_data.get('systemInstruction') and not (log_data.get('chunkedPrompt', {}).get('chunks') or log_data.get('history')):
        return False, "JSON file contains no 'systemInstruction' and no valid dialog structure."

    final_title = get_clean_title(md_path.stem)
    
    # This list will accumulate all parts of the Markdown file.
    md_parts = []
    
    if config.get('enable_frontmatter', False):
        md_parts.append(_build_frontmatter(json_path, final_title, frontmatter_template, has_gdrive_link, config))

    md_parts.append(f"# {final_title}")

    if config.get('enable_metadata_table', False):
        metadata_table = _build_metadata_table(log_data, lang_templates)
        if metadata_table:
            md_parts.append(metadata_table)
            md_parts.append("\n\n***")

    conversation_md = _build_conversation_turns(log_data, md_path, config, lang_templates)
    if conversation_md:
        md_parts.append(conversation_md)

    # Join all parts with consistent spacing.
    final_md_output = "\n\n".join(filter(None, md_parts))
    
    return _write_markdown_file(md_path, final_md_output)

def find_json_files(path: Path, recursive: bool, fast_mode: bool = False):
    """
    Scans a directory to find all valid JSON files.

    Args:
        path (Path): The starting path to search.
        recursive (bool): If True, scans all subdirectories.
        fast_mode (bool): If True, instantly returns all files without an extension,
                          skipping the slow validation step.
    """
    if not path.exists():
        return []

    # --- Fast Mode ---
    # This mode assumes that any file without an extension is a potential log file.
    # It skips the slow content validation (json.load) for a massive speed boost.
    if fast_mode:
        print("Fast Mode enabled: Assuming files without an extension are logs.")
        files_to_check = []
        if path.is_file():
            if not path.suffix:
                files_to_check.append(path)
        elif path.is_dir():
            glob_pattern = '**/*' if recursive else '*'
            for file_path in path.glob(glob_pattern):
                if file_path.is_file() and not file_path.suffix:
                    files_to_check.append(file_path)
        
        print(f"Found {len(files_to_check)} potential logs to convert.")
        return sorted(files_to_check)

    # --- Normal (Reliable) Mode ---
    # This mode reads every single file to ensure it's a valid JSON, making it
    # much slower but 100% accurate.
    print("Normal Mode: Verifying every file to find valid JSONs...")
    all_potential_files = []
    if path.is_file():
        all_potential_files.append(path)
    elif path.is_dir():
        glob_pattern = '**/*' if recursive else '*'
        for file_path in path.glob(glob_pattern):
            if file_path.is_file():
                all_potential_files.append(file_path)

    if not all_potential_files:
        return []

    valid_json_files = []
    # Ignore configuration and other known files to avoid processing them.
    ignore_filenames = [CONFIG_FILE_NAME, CRASH_LOG_FILE, 'frontmatter_template_en.txt', 'frontmatter_template_ru.txt']
    
    print(f"Scanning {len(all_potential_files)} files...")
    with tqdm(all_potential_files, desc="Scanning files", unit="file", file=sys.stdout) as pbar:
        for file_path in pbar:
            if file_path.name in ignore_filenames:
                continue
            try:
                # This is the slow but reliable validation step.
                with open(file_path, 'r', encoding='utf-8') as f:
                    json.load(f)
                valid_json_files.append(file_path)
            except (json.JSONDecodeError, UnicodeDecodeError, PermissionError, IsADirectoryError, IOError):
                continue
                
    return sorted(valid_json_files)

def process_files(files_to_process, output_dir, overwrite, config, lang_templates, frontmatter_template, fast_mode=False):
    """
    Processes a list of JSON files, converting each to Markdown.

    This function iterates through a list of file paths, manages the conversion process
    for each, and reports the final statistics (success, skipped, error counts).
    It handles filename generation based on templates and respects the 'overwrite' flag.

    Args:
        files_to_process (list[Path]): The list of JSON files to convert.
        output_dir (Path): The directory where the output Markdown files will be saved.
        overwrite (bool): If True, existing Markdown files will be overwritten.
        config (dict): The main configuration dictionary.
        lang_templates (dict): The dictionary for localized strings.
        frontmatter_template (str): The template for YAML frontmatter.
        fast_mode (bool): If True, skips the check for GDrive links.

    Returns:
        tuple[int, int, int]: A tuple containing the counts of successful, skipped, and failed conversions.
    """
    if not files_to_process:
        return 0, 0, 0
        
    print(Style.BRIGHT + f"\nFound {len(files_to_process)} valid JSON files to process. Output will be saved to '{output_dir}'.")
    success_count, skipped_count, error_count = 0, 0, 0
    
    # Use tqdm for a progress bar to show the overall conversion progress.
    with tqdm(total=len(files_to_process), desc="Converting", unit="file", ncols=100, file=sys.stdout) as pbar:
        for json_path in files_to_process:
            # Read the file once to get its content for all checks and conversion
            log_data, error_msg = _read_log_data(json_path)
            if not log_data:
                error_count += 1
                tqdm.write(Fore.RED + f"\n❌ ERROR reading '{json_path.name}': {error_msg}")
                pbar.update(1)
                continue

            try:
                # Generate the date string for the new filename from the file's metadata.
                mtime = datetime.fromtimestamp(json_path.stat().st_mtime)
                date_str = mtime.strftime(config['date_format'])
            except FileNotFoundError:
                date_str = "XXXX-XX-XX"

            # Check for GDrive links, but ONLY if the feature is enabled AND Fast Mode is OFF
            has_gdrive_link = False
            gdrive_indicator = ""
            if config.get('enable_gdrive_indicator', False) and not fast_mode:
                has_gdrive_link = _check_for_gdrive_links(log_data)
                if has_gdrive_link:
                    gdrive_indicator = config.get('gdrive_filename_indicator', '')

            # Construct the new filename from the template in the config.
            filename = json_path.name
            base_filename = filename[:-5] if filename.lower().endswith('.json') else filename
            new_md_filename = config['filename_template'].format(
                date=date_str, 
                basename=base_filename,
                gdrive_indicator=gdrive_indicator
            )
            output_md_path = output_dir / new_md_filename

            # Skip conversion if the file exists and overwrite is disabled.
            if not overwrite and output_md_path.exists():
                skipped_count += 1
            else:
                # Call the main conversion function, passing the pre-loaded data.
                success, error_msg = convert_llm_log_to_markdown(
                    log_data, json_path, output_md_path, config, lang_templates, frontmatter_template, has_gdrive_link
                )
                if success:
                    success_count += 1
                else:
                    error_count += 1
                    # Print errors directly to the console.
                    tqdm.write(Fore.RED + f"\n❌ ERROR converting '{json_path.name}': {error_msg}")
            pbar.update(1)

    # Print a final summary of the conversion results.
    print(Style.BRIGHT + "\n--- Conversion Complete ---")
    print(Fore.GREEN + f"✅ Successfully converted: {success_count}")
    if skipped_count > 0: print(Fore.YELLOW + f"⏭️ Skipped (already exist): {skipped_count}")
    if error_count > 0: print(Fore.RED + f"❌ Errors: {error_count}")
    return success_count, skipped_count, error_count