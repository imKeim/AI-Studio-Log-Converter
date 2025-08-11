import json
import os
import argparse
import sys
import re
import base64
from datetime import datetime
from pathlib import Path
from tqdm import tqdm
import yaml

# --- Global Constants & Default Configs ---
CONFIG_FILE_NAME = "config.yaml"
DEFAULT_INPUT_DIR = "input"
DEFAULT_OUTPUT_DIR = "output"
ASSETS_DIR_NAME = "assets"

DEFAULT_CONFIG = {
    'language': 'en',
    'enable_frontmatter': True,
    'enable_metadata_table': True, # <-- НОВАЯ ОПЦИЯ
    'filename_template': "{date} - {basename}.md",
    'date_format': "%Y-%m-%d",
    'localization': {
        'en': {
            'user_header': "## User Prompt 👤",
            'model_header': "## Model Response 🤖",
            'thought_block_template': """> [!bug]- Model Thoughts 🧠\n> {thought_text}""",
            'system_instruction_header': "System Instruction ⚙️",
            'system_instruction_template': """> [!note]- {header}\n> {text}""",
            # <-- НОВЫЙ БЛОК ЛОКАЛИЗАЦИИ -->
            'metadata_table': {
                'header_parameter': "Parameter",
                'header_value': "Value",
                'model': "**Model**",
                'temperature': "**Temperature**",
                'top_p': "**Top-P**",
                'top_k': "**Top-K**",
                'web_search': "**Web Search**",
                'search_enabled': "Enabled",
                'search_disabled': "Disabled"
            },
            'frontmatter_template_file': "frontmatter_template_en.txt"
        },
        'ru': {
            'user_header': "## Запрос пользователя 👤",
            'model_header': "## Ответ модели 🤖",
            'thought_block_template': """> [!bug]- Размышления модели 🧠\n> {thought_text}""",
            'system_instruction_header': "Системная инструкция ⚙️",
            'system_instruction_template': """> [!note]- {header}\n> {text}""",
            # <-- НОВЫЙ БЛОК ЛОКАЛИЗАЦИИ -->
            'metadata_table': {
                'header_parameter': "Настройка",
                'header_value': "Значение",
                'model': "**Модель**",
                'temperature': "**Температура**",
                'top_p': "**Top-P**",
                'top_k': "**Top-K**",
                'web_search': "**Поиск в Google**",
                'search_enabled': "Включен",
                'search_disabled': "Отключен"
            },
            'frontmatter_template_file': "frontmatter_template_ru.txt"
        }
    }
}

DEFAULT_FRONTMATTER_TEMPLATES = {
    'en': """---
title: "{title}"
aliases:
  - "{title}"
para: resource
type: llm-log
kind: google-ai-studio
tags: 
status: archived
cdate: {cdate}
mdate: {mdate}
---""",
    'ru': """---
title: "{title}"
aliases:
  - "{title}"
para: ресурс
type: llm-лог
kind: google-ai-studio
tags: 
status: архивировано
cdate: {cdate}
mdate: {mdate}
---"""
}

def load_or_create_config() -> dict:
    config_path = Path(CONFIG_FILE_NAME)
    if not config_path.exists():
        print(f"Info: Configuration file '{CONFIG_FILE_NAME}' not found. Creating a new one.")
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(DEFAULT_CONFIG, f, allow_unicode=True, sort_keys=False)
            return DEFAULT_CONFIG
        except IOError as e:
            print(f"Error: Could not create config file: {e}. Using default settings.")
            return DEFAULT_CONFIG
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            # Объединяем конфиг по умолчанию с пользовательским, чтобы новые опции работали
            user_config = yaml.safe_load(f) or {}
            config = DEFAULT_CONFIG.copy()
            config.update(user_config)
            return config
    except (yaml.YAMLError, IOError) as e:
        print(f"Error: Could not read config file '{CONFIG_FILE_NAME}': {e}. Using default settings.")
        return DEFAULT_CONFIG

def load_or_create_template(template_filename: str, lang: str) -> str:
    template_path = Path(template_filename)
    if not template_path.exists():
        print(f"Info: Template file '{template_filename}' not found. Creating a default one.")
        default_template = DEFAULT_FRONTMATTER_TEMPLATES.get(lang, DEFAULT_FRONTMATTER_TEMPLATES['en'])
        try:
            template_path.write_text(default_template, encoding='utf-8')
            return default_template
        except IOError as e:
            print(f"Error: Could not create template file: {e}. Using a built-in template.")
            return default_template
    try:
        return template_path.read_text(encoding='utf-8')
    except IOError as e:
        print(f"Error: Could not read template file: {e}. Using a built-in template.")
        return DEFAULT_FRONTMATTER_TEMPLATES.get(lang, DEFAULT_FRONTMATTER_TEMPLATES['en'])

def get_clean_title(base_title: str) -> str:
    match = re.match(r"^\d{4}-\d{2}-\d{2} - (.*)", base_title)
    if match:
        return match.group(1)
    return base_title

def save_image_from_base64(base64_data: str, mime_type: str, md_path: Path) -> str:
    assets_path = md_path.parent / ASSETS_DIR_NAME
    assets_path.mkdir(exist_ok=True)
    
    extension = mime_type.split('/')[-1]
    timestamp = int(time.time() * 1000)
    image_filename = f"{md_path.stem}_img_{timestamp}.{extension}"
    image_path = assets_path / image_filename
    
    try:
        image_data = base64.b64decode(base64_data)
        with open(image_path, 'wb') as f:
            f.write(image_data)
        return f"![[{image_filename}]]"
    except (base64.binascii.Error, IOError) as e:
        return f"[Error saving image: {e}]"

def convert_llm_log_to_markdown(json_path: Path, md_path: Path, config: dict, lang_templates: dict, frontmatter_template: str) -> (bool, str):
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

    # --- НОВАЯ ЛОГИКА: Создание таблицы метаданных ---
    if config.get('enable_metadata_table', False):
        run_settings = log_data.get('runSettings', {})
        if run_settings:
            loc = lang_templates.get('metadata_table', {})
            header_param = loc.get('header_parameter', 'Parameter')
            header_value = loc.get('header_value', 'Value')
            
            table_rows = []
            
            # Модель
            model_name = run_settings.get('model', 'N/A')
            clean_model_name = model_name.split('/')[-1]
            table_rows.append(f"| {loc.get('model', '**Model**')} | `{clean_model_name}` |")
            
            # Температура
            if 'temperature' in run_settings:
                table_rows.append(f"| {loc.get('temperature', '**Temperature**')} | `{run_settings['temperature']}` |")
            
            # Top-P
            if 'topP' in run_settings:
                table_rows.append(f"| {loc.get('top_p', '**Top-P**')} | `{run_settings['topP']}` |")

            # Top-K
            if 'topK' in run_settings:
                table_rows.append(f"| {loc.get('top_k', '**Top-K**')} | `{run_settings['topK']}` |")

            # Поиск в Google
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

        if current_role == 'model' and pending_thoughts:
            turn_content = pending_thoughts + turn_content

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
    for file_path in tqdm(files_to_check, desc="Scanning files", unit="file"):
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
    print(f"\nFound {len(files_to_process)} valid JSON files to process. Output will be saved to '{output_dir}'.")
    success_count, skipped_count, error_count = 0, 0, 0
    
    with tqdm(total=len(files_to_process), desc="Converting", unit="file", ncols=100) as pbar:
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
                    tqdm.write(f"\n❌ ERROR converting '{json_path.name}': {error_msg}")
            pbar.update(1)

    print("\n--- Conversion Complete ---")
    print(f"✅ Successfully converted: {success_count}")
    if skipped_count > 0: print(f"⏭️ Skipped (already exist): {skipped_count}")
    if error_count > 0: print(f"❌ Errors: {error_count}")

def run_interactive_mode(input_dir, output_dir, config, lang_templates, frontmatter_template):
    print("--- AI Studio Log Converter (Interactive Mode) ---")
    print(f"Source folder: '{input_dir}'")
    print(f"Output folder: '{output_dir}'")
    
    recursive_str = input("➡️ Search recursively in subfolders? (y/N, default: N): ").strip().lower()
    recursive = recursive_str == 'y'

    overwrite_str = input("➡️ Overwrite existing files? (y/N, default: N): ").strip().lower()
    overwrite = overwrite_str == 'y'

    files = find_json_files(input_dir, recursive)
    if not files:
        print(f"\n⚠️ No valid JSON files found in the '{input_dir}' folder.")
        print("Please place your files there and run the program again.")
        return

    process_files(files, output_dir, overwrite, config, lang_templates, frontmatter_template)

def main():
    input_dir_default = Path(DEFAULT_INPUT_DIR)
    output_dir_default = Path(DEFAULT_OUTPUT_DIR)
    input_dir_default.mkdir(exist_ok=True)
    output_dir_default.mkdir(exist_ok=True)

    config = load_or_create_config()
    lang = config.get('language', 'en')
    lang_templates = config.get('localization', {}).get(lang, DEFAULT_CONFIG['localization']['en'])
    frontmatter_template_file = lang_templates.get('frontmatter_template_file', f"frontmatter_template_{lang}.txt")
    frontmatter_template = load_or_create_template(frontmatter_template_file, lang)

    parser = argparse.ArgumentParser(description="Converts Google AI Studio logs to Markdown.")
    parser.add_argument("input_path", nargs='?', type=Path, default=input_dir_default,
                        help=f"Source file or folder (default: '{DEFAULT_INPUT_DIR}').")
    parser.add_argument("-o", "--output", type=Path, default=output_dir_default,
                        help=f"Output directory (default: '{DEFAULT_OUTPUT_DIR}').")
    parser.add_argument("-r", "--recursive", action="store_true", help="Search recursively.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing files.")
    
    if len(sys.argv) > 1:
        args = parser.parse_args()
        input_path = args.input_path
        output_path = args.output
        
        files = find_json_files(input_path, args.recursive)
        if not files:
            print(f"\n⚠️ No valid JSON files found in '{input_path}'.")
            if input_path == input_dir_default:
                 print("Please place your files there and run the program again.")
            return
        
        process_files(files, output_path, args.overwrite, config, lang_templates, frontmatter_template)
    else:
        run_interactive_mode(input_dir_default, output_dir_default, config, lang_templates, frontmatter_template)
    
    if getattr(sys, 'frozen', False):
        input("\nPress Enter to exit.")

if __name__ == "__main__":
    main()