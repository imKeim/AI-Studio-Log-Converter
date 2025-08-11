import json
import os
import re
import base64
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from tqdm import tqdm
import sys
from colorama import Fore, Style

__all__ = [
    "get_clean_title",
    "save_image_from_base64",
    "format_grounding_data",
    "convert_llm_log_to_markdown",
    "find_json_files",
    "process_files",
]

def get_clean_title(base_title: str) -> str:
    """
    Extracts a clean, human-readable title from a filename string.

    Many log files are prefixed with a date (e.g., "2023-10-27 - My Conversation").
    This function strips that date prefix, returning only the descriptive part of the title.
    If the filename doesn't match the expected pattern, it returns the original string.

    Args:
        base_title (str): The original filename or title string.

    Returns:
        str: The cleaned-up title without the date prefix.
    """
    # Use a regular expression to find titles that start with a YYYY-MM-DD date pattern.
    match = re.match(r"^\d{4}-\d{2}-\d{2} - (.*)", base_title)
    if match:
        # If a match is found, return the first capturing group, which is the title part.
        return match.group(1)
    # If no match, return the original title.
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
    # Define the 'assets' folder path, creating it if it doesn't exist.
    assets_path = md_path.parent / "assets"
    assets_path.mkdir(exist_ok=True)
    
    # Determine the file extension from the MIME type.
    extension = mime_type.split('/')[-1]
    # Generate a unique filename to avoid collisions, using the markdown file's name and a timestamp.
    timestamp = int(datetime.now().timestamp() * 1000)
    image_filename = f"{md_path.stem}_img_{timestamp}.{extension}"
    image_path = assets_path / image_filename
    
    try:
        # Decode the base64 string into binary image data.
        image_data = base64.b64decode(base64_data)
        # Write the binary data to the new image file.
        with open(image_path, 'wb') as f:
            f.write(image_data)
        # Return an Obsidian-style embed link.
        return f"![[{image_filename}]]"
    except (base64.binascii.Error, IOError) as e:
        # If decoding or writing fails, return a descriptive error message.
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
    # Get localized strings for headers, with default fallbacks.
    loc = lang_templates.get('grounding_metadata', {})
    spoiler_header = loc.get('spoiler_header', "Sources Used")
    queries_header = loc.get('queries_header', "**Search Queries:**")
    sources_header = loc.get('sources_header', "**Sources:**")
    
    # Start with the main spoiler block header.
    content = [f"> [!info]- {spoiler_header}"]
    
    # Format the web search queries, if they exist.
    queries = grounding_data.get('webSearchQueries', [])
    if queries:
        content.append(f"> {queries_header}")
        for query in queries:
            content.append(f"> - `{query}`")
    
    # Format the grounding sources, if they exist.
    sources = grounding_data.get('groundingSources', [])
    if sources:
        if queries: content.append(">") # Add a spacer line for visual separation.
        content.append(f"> {sources_header}")
        for source in sources:
            uri = source.get('uri')
            # Use the source title, or fall back to the hostname from the URI.
            title = source.get('title') or urlparse(uri).hostname if uri else "Source"
            num = source.get('referenceNumber', '')
            content.append(f"> {num}. [{title}]({uri})")
            
    # Join all the formatted lines into a single string.
    return "\n".join(content)

def convert_llm_log_to_markdown(json_path: Path, md_path: Path, config: dict, lang_templates: dict, frontmatter_template: str) -> (bool, str):
    """
    Converts a single AI Studio JSON log file into a structured Markdown file.

    This is the main function that orchestrates the entire conversion process for one file.
    It reads the JSON log, processes its structure, extracts conversations, handles metadata,
    and writes the final, formatted content to a Markdown file.

    Args:
        json_path (Path): The path to the input JSON log file.
        md_path (Path): The path where the output Markdown file will be saved.
        config (dict): A dictionary of user-defined configuration settings.
        lang_templates (dict): A dictionary containing localized strings for UI elements.
        frontmatter_template (str): A string template for the YAML frontmatter.

    Returns:
        tuple[bool, str]: A tuple containing a boolean indicating success (True) or failure (False),
                          and a string with an error message if the conversion failed.
    """
    try:
        # Attempt to read and parse the JSON file. This is the first and most critical step.
        log_data = json.loads(json_path.read_text(encoding='utf-8'))
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON format. Details: {e}"
    except Exception as e:
        return False, f"Failed to read file. Details: {e}"

    # Clean the title for use in the Markdown content.
    final_title = get_clean_title(md_path.stem)

    # This list will accumulate all parts of the Markdown file before being joined together.
    full_md_content = []
    # Optionally, add YAML frontmatter for organization in tools like Obsidian.
    if config.get('enable_frontmatter', False):
        try:
            # Use the file's modification time for creation and modification dates.
            file_mtime_str = datetime.fromtimestamp(json_path.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            cdate = file_mtime_str
            mdate = file_mtime_str
            # Format and add the frontmatter to the content.
            full_md_content.append(frontmatter_template.format(title=final_title, cdate=cdate, mdate=mdate).strip())
        except FileNotFoundError:
            # Ignore if the file doesn't exist, though this is unlikely here.
            pass

    # Add the main H1 title of the document.
    full_md_content.append(f"# {final_title}")

    # Optionally, add a metadata table with details about the model and its settings.
    if config.get('enable_metadata_table', False):
        run_settings = log_data.get('runSettings', {})
        if run_settings:
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
            full_table = table_header + "\n" + "\n".join(table_rows)
            full_md_content.append(full_table + "\n\n***")

    # This list will hold the formatted user and model turns.
    conversation_turns = []
    
    # Extract the system instruction, which defines the model's persona or task.
    system_instruction = (log_data.get('systemInstruction', {}).get('text') or '').strip()
    prompt_data = log_data.get('chunkedPrompt', {})
    # The actual conversation content is in 'chunks', 'pendingInputs', or 'history'.
    # We check them in order of preference to find the conversation data.
    chunks = prompt_data.get('chunks') or prompt_data.get('pendingInputs') or log_data.get('history', [])
    
    # If there's no conversation data at all, the file is not a valid log.
    if not system_instruction and not chunks:
        return False, "JSON file contains no 'systemInstruction' and no valid dialog structure."

    # We iterate through the chunks to reconstruct the conversation turn by turn.
    i = 0
    while i < len(chunks):
        # Determine the role of the current speaker (e.g., 'user' or 'model').
        current_role = chunks[i].get('role')
        if not current_role:
            # Skip any chunks that don't have a role.
            i += 1
            continue

        # Group all consecutive chunks from the same role into a single "turn".
        turn_chunks = []
        j = i
        while j < len(chunks) and chunks[j].get('role') == current_role:
            turn_chunks.append(chunks[j])
            j += 1
        
        # This list will hold all the content pieces for the current turn.
        turn_content = []
        pending_thoughts = []
        grounding_data = None
        # Get the appropriate header for the role (e.g., "## User" or "## Model").
        header = lang_templates.get(f"{current_role}_header", f"## {current_role.capitalize()}")

        # Special case: If this is the very first turn and it's from the user,
        # embed the system instruction within a collapsible block for context.
        if i == 0 and current_role == 'user' and system_instruction:
            spoiler_header = lang_templates.get('system_instruction_header', 'System Instruction ⚙️')
            spoiler_template = lang_templates.get('system_instruction_template', '> [!note]- {header}\n> {text}')
            # Indent the system text to fit within the blockquote format.
            indented_system_text = system_instruction.replace('\n', '\n> ')
            spoiler_block = spoiler_template.format(header=spoiler_header, text=indented_system_text)
            turn_content.append(spoiler_block)

        # Process each chunk within the current turn.
        for chunk in turn_chunks:
            # Handle "thoughts": internal monologue of the model, useful for debugging.
            if current_role == 'model' and chunk.get('isThought'):
                thought_text = (chunk.get('text') or '').strip()
                if thought_text:
                    # Format the thought into a collapsible block.
                    thought_block = lang_templates['thought_block_template'].format(thought_text=thought_text.replace(chr(10), chr(10) + '> '))
                    pending_thoughts.append(thought_block)
                continue # Skip to the next chunk
            
            # Store grounding data if it exists in this chunk.
            if 'grounding' in chunk:
                grounding_data = chunk['grounding']

            # Append simple text content.
            if 'text' in chunk:
                turn_content.append(chunk['text'].strip())
            
            # Handle images from Google Drive.
            if 'driveImage' in chunk:
                drive_id = chunk['driveImage'].get('id')
                if drive_id:
                    # Create a placeholder link as we can't access the image directly.
                    placeholder = f"[Image from Google Drive (ID: {drive_id})](https://drive.google.com/file/d/{drive_id})"
                    turn_content.append(placeholder)
            
            # Handle YouTube video links.
            if 'youtubeVideo' in chunk:
                video_id = chunk['youtubeVideo'].get('id')
                if video_id:
                    placeholder = f"[YouTube Video (ID: {video_id})](https://www.youtube.com/watch?v={video_id})"
                    turn_content.append(placeholder)

            # Handle inline images (base64 encoded).
            if 'inlineData' in chunk:
                image_link = save_image_from_base64(chunk['inlineData']['data'], chunk['inlineData']['mimeType'], md_path)
                turn_content.append(image_link)

            # Some chunks have a 'parts' array containing mixed content (text and images).
            for part in chunk.get('parts', []):
                part_content = []
                if 'text' in part:
                    part_content.append(part['text'].strip())
                elif 'inlineData' in part: # Embedded image data.
                    image_link = save_image_from_base64(part['inlineData']['data'], part['inlineData']['mimeType'], md_path)
                    part_content.append(image_link)
                elif 'driveImage' in part: # Google Drive image.
                    drive_id = part['driveImage'].get('id')
                    if drive_id:
                        placeholder = f"[Image from Google Drive (ID: {drive_id})](https://drive.google.com/file/d/{drive_id})"
                        part_content.append(placeholder)
                
                # This check prevents duplicating content that might appear in both
                # the outer chunk and its 'parts'.
                full_part_text = "".join(part_content)
                if not any(full_part_text in content_part for content_part in turn_content):
                    turn_content.extend(part_content)

        # After processing all chunks in a turn, assemble the final content for that turn.
        if current_role == 'model':
            # Prepend any "thoughts" to the model's response.
            if pending_thoughts:
                turn_content = pending_thoughts + turn_content
            # Append grounding data if it exists and is enabled in the config.
            if grounding_data and config.get('enable_grounding_metadata', False):
                grounding_md = format_grounding_data(grounding_data, lang_templates)
                turn_content.append(grounding_md)

        # If the turn has any content, format it with its header and add to the list of turns.
        if turn_content:
            conversation_turns.append(f"{header}\n\n" + "\n\n".join(filter(None, turn_content)))
        
        # Move the main loop index to the start of the next turn.
        i = j

    # Join the main content blocks (frontmatter, title, metadata) and the conversation turns.
    final_md_output = "\n\n".join(full_md_content) + "\n\n***\n\n" + "\n\n***\n\n".join(conversation_turns)

    try:
        # Ensure the output directory exists.
        md_path.parent.mkdir(parents=True, exist_ok=True)
        # Write the fully assembled Markdown content to the output file.
        md_path.write_text(final_md_output, encoding='utf-8')
        return True, ""
    except IOError as e:
        return False, f"Could not write output file. Details: {e}"

def find_json_files(path: Path, recursive: bool):
    """
    Scans a directory (or a single file) to find all valid JSON files.

    This function is responsible for locating the source files for conversion.
    It can operate recursively and includes a progress bar for long scans.
    It validates files by attempting to parse them as JSON, ensuring that only
    well-formed logs are processed.

    Args:
        path (Path): The starting path to search, which can be a file or a directory.
        recursive (bool): If True, scans all subdirectories of the given path.

    Returns:
        list[Path]: A sorted list of paths to valid JSON files.
    """
    if not path.exists():
        return []
    files_to_check = []
    if path.is_file():
        files_to_check.append(path)
    elif path.is_dir():
        if recursive:
            # Walk through all directories and subdirectories.
            for root, _, filenames in os.walk(path):
                for filename in filenames:
                    files_to_check.append(Path(root) / filename)
        else:
            # Scan only the top-level directory.
            for filename in os.listdir(path):
                file_path = path / filename
                if file_path.is_file():
                    files_to_check.append(file_path)
    
    valid_json_files = []
    # Define file extensions to ignore to speed up scanning.
    ignore_extensions = ['.py', '.exe', '.yaml', '.txt', '.md', '.spec', '.zip']
    print(f"Scanning {len(files_to_check)} files to find valid JSONs...")
    # Use tqdm for a user-friendly progress bar.
    for file_path in tqdm(files_to_check, desc="Scanning files", unit="file", file=sys.stdout):
        if file_path.suffix.lower() in ignore_extensions:
            continue
        try:
            # The core validation: can the file be opened and parsed as JSON?
            with open(file_path, 'r', encoding='utf-8') as f:
                json.load(f)
            # If successful, add it to our list of valid files.
            valid_json_files.append(file_path)
        except (json.JSONDecodeError, UnicodeDecodeError, PermissionError, IsADirectoryError):
            # Ignore files that are not valid JSON, unreadable, or are directories.
            continue
    return sorted(valid_json_files)

def process_files(files_to_process, output_dir, overwrite, config, lang_templates, frontmatter_template):
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
            try:
                # Generate the date string for the new filename from the file's metadata.
                mtime = datetime.fromtimestamp(json_path.stat().st_mtime)
                date_str = mtime.strftime(config['date_format'])
            except FileNotFoundError:
                date_str = "XXXX-XX-XX"

            # Construct the new filename from the template in the config.
            filename = json_path.name
            base_filename = filename[:-5] if filename.lower().endswith('.json') else filename
            new_md_filename = config['filename_template'].format(date=date_str, basename=base_filename)
            output_md_path = output_dir / new_md_filename

            # Skip conversion if the file exists and overwrite is disabled.
            if not overwrite and output_md_path.exists():
                skipped_count += 1
            else:
                # Call the main conversion function for the individual file.
                success, error_msg = convert_llm_log_to_markdown(json_path, output_md_path, config, lang_templates, frontmatter_template)
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
