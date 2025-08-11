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

def get_clean_title(base_title: str) -> str:
    """Extracts a clean title from a filename string."""
    match = re.match(r"^\d{4}-\d{2}-\d{2} - (.*)", base_title)
    if match:
        return match.group(1)
    return base_title

def save_image_from_base64(base64_data: str, mime_type: str, md_path: Path) -> str:
    """Saves an image from a base64 string to the assets folder."""
    assets_path = md_path.parent / "assets"
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
    """Formats grounding metadata into a Markdown spoiler block."""
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
        if queries: content.append(">") # Add a spacer line
        content.append(f"> {sources_header}")
        for source in sources:
            uri = source.get('uri')
            title = source.get('title') or urlparse(uri).hostname if uri else "Source"
            num = source.get('referenceNumber', '')
            content.append(f"> {num}. [{title}]({uri})")
            
    return "\n".join(content)

def convert_llm_log_to_markdown(json_path: Path, md_path: Path, config: dict, lang_templates: dict, frontmatter_template: str) -> (bool, str):
    """Converts a single JSON log file to a Markdown file."""
    try:
        log_data = json.loads(json_path.read_text(encoding='utf-8'))
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON format. Details: {e}"
    except Exception as e:
        return False, f"Failed to read file. Details: {e}"

    final_title = get_clean_title(md_path.stem)

    full_md_content = ""
    if config.get('enable_frontmatter', False):
        try:
            file_mtime_str = datetime.fromtimestamp(json_path.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            cdate = file_mtime_str
            mdate = file_mtime_str
            full_md_content += frontmatter_template.format(title=final_title, cdate=cdate, mdate=mdate).strip() + "\n\n"
        except FileNotFoundError: pass

    full_md_content += f"# {final_title}\n\n"

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
            full_md_content += full_table + "\n\n***\n\n"

    conversation_turns = []
    
    system_instruction = (log_data.get('systemInstruction', {}).get('text') or '').strip()
    prompt_data = log_data.get('chunkedPrompt', {})
    chunks = prompt_data.get('chunks') or prompt_data.get('pendingInputs') or log_data.get('history', [])
    
    if not system_instruction and not chunks:
        return False, "JSON file contains no 'systemInstruction' and no valid dialog structure."

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
                grounding_data = chunk['grounding']

            if 'text' in chunk:
                turn_content.append(chunk['text'].strip())
            
            if 'driveImage' in chunk:
                drive_id = chunk['driveImage'].get('id')
                if drive_id:
                    placeholder = f"[Image from Google Drive (ID: {drive_id})](https://drive.google.com/file/d/{drive_id})"
                    turn_content.append(placeholder)
            
            if 'youtubeVideo' in chunk:
                video_id = chunk['youtubeVideo'].get('id')
                if video_id:
                    placeholder = f"[YouTube Video (ID: {video_id})](https://www.youtube.com/watch?v={video_id})"
                    turn_content.append(placeholder)

            if 'inlineData' in chunk:
                image_link = save_image_from_base64(chunk['inlineData']['data'], chunk['inlineData']['mimeType'], md_path)
                turn_content.append(image_link)

            for part in chunk.get('parts', []):
                part_content = []
                if 'text' in part:
                    part_content.append(part['text'].strip())
                elif 'inlineData' in part:
                    image_link = save_image_from_base64(part['inlineData']['data'], part['inlineData']['mimeType'], md_path)
                    part_content.append(image_link)
                elif 'driveImage' in part:
                    drive_id = part['driveImage'].get('id')
                    if drive_id:
                        placeholder = f"[Image from Google Drive (ID: {drive_id})](https://drive.google.com/file/d/{drive_id})"
                        part_content.append(placeholder)
                
                full_part_text = "".join(part_content)
                if not any(full_part_text in content_part for content_part in turn_content):
                    turn_content.extend(part_content)

        if current_role == 'model':
            if pending_thoughts:
                turn_content = pending_thoughts + turn_content
            if grounding_data and config.get('enable_grounding_metadata', False):
                grounding_md = format_grounding_data(grounding_data, lang_templates)
                turn_content.append(grounding_md)

        if turn_content:
            conversation_turns.append(f"{header}\n\n" + "\n\n".join(filter(None, turn_content)))
        
        i = j

    full_md_content += "\n***\n\n".join(conversation_turns)

    try:
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(full_md_content, encoding='utf-8')
        return True, ""
    except IOError as e:
        return False, f"Could not write output file. Details: {e}"

def find_json_files(path: Path, recursive: bool):
    """Finds all valid JSON files in a given path."""
    if not path.exists():
        return []
    files_to_check = []
    if path.is_file():
        files_to_check.append(path)
    elif path.is_dir():
        if recursive:
            for root, _, filenames in os.walk(path):
                for filename in filenames:
                    files_to_check.append(Path(root) / filename)
        else:
            for filename in os.listdir(path):
                file_path = path / filename
                if file_path.is_file():
                    files_to_check.append(file_path)
    valid_json_files = []
    ignore_extensions = ['.py', '.exe', '.yaml', '.txt', '.md', '.spec', '.zip']
    print(f"Scanning {len(files_to_check)} files to find valid JSONs...")
    for file_path in tqdm(files_to_check, desc="Scanning files", unit="file", file=sys.stdout):
        if file_path.suffix.lower() in ignore_extensions:
            continue
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                json.load(f)
            valid_json_files.append(file_path)
        except (json.JSONDecodeError, UnicodeDecodeError, PermissionError, IsADirectoryError):
            continue
    return sorted(valid_json_files)

def process_files(files_to_process, output_dir, overwrite, config, lang_templates, frontmatter_template):
    """Processes a list of JSON files."""
    if not files_to_process:
        return 0, 0, 0
        
    print(Style.BRIGHT + f"\nFound {len(files_to_process)} valid JSON files to process. Output will be saved to '{output_dir}'.")
    success_count, skipped_count, error_count = 0, 0, 0
    
    with tqdm(total=len(files_to_process), desc="Converting", unit="file", ncols=100, file=sys.stdout) as pbar:
        for json_path in files_to_process:
            try:
                mtime = datetime.fromtimestamp(json_path.stat().st_mtime)
                date_str = mtime.strftime(config['date_format'])
            except FileNotFoundError: date_str = "XXXX-XX-XX"

            filename = json_path.name
            if filename.lower().endswith('.json'):
                base_filename = filename[:-5]
            else:
                base_filename = filename
            
            new_md_filename = config['filename_template'].format(date=date_str, basename=base_filename)
            output_md_path = output_dir / new_md_filename

            if not overwrite and output_md_path.exists():
                skipped_count += 1
            else:
                success, error_msg = convert_llm_log_to_markdown(json_path, output_md_path, config, lang_templates, frontmatter_template)
                if success:
                    success_count += 1
                else:
                    error_count += 1
                    tqdm.write(Fore.RED + f"\n❌ ERROR converting '{json_path.name}': {error_msg}")
            pbar.update(1)

    print(Style.BRIGHT + "\n--- Conversion Complete ---")
    print(Fore.GREEN + f"✅ Successfully converted: {success_count}")
    if skipped_count > 0: print(Fore.YELLOW + f"⏭️ Skipped (already exist): {skipped_count}")
    if error_count > 0: print(Fore.RED + f"❌ Errors: {error_count}")
    return success_count, skipped_count, error_count
