import json
import os
import argparse
import sys
import re
import base64
import traceback
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from tqdm import tqdm
import yaml
from colorama import Fore, Style, init
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import customtkinter as ctk
from tkinter import filedialog, messagebox

# --- Colorama Initialization ---
init(autoreset=True)

# --- Global Constants & Default Configs ---
CONFIG_FILE_NAME = "config.yaml"
DEFAULT_INPUT_DIR = "input"
DEFAULT_OUTPUT_DIR = "output"
ASSETS_DIR_NAME = "assets"

DEFAULT_CONFIG_TEMPLATE = """
# --- AI Studio Log Converter Settings ---

# Language for the generated Markdown files. (en/ru)
language: '{language}'

# Enable/disable the YAML frontmatter block at the start of the file.
enable_frontmatter: {enable_frontmatter}

# Enable/disable the metadata table with run settings (Model, Temperature, etc.).
enable_metadata_table: {enable_metadata_table}

# Enable/disable the grounding metadata block (web search sources) at the end of a model's response.
enable_grounding_metadata: {enable_grounding_metadata}

# Template for the output filename.
# Available variables: {{date}}, {{basename}}
filename_template: '{filename_template}'

# Date format for the {{date}} variable in the filename.
# Python strftime syntax: https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes
date_format: '{date_format}'

# --- Localization Settings ---
# Text templates for different languages.
# The 'language' setting above determines which set of templates to use.
"""

DEFAULT_CONFIG = {
    'language': 'en',
    'enable_frontmatter': True,
    'enable_metadata_table': True,
    'enable_grounding_metadata': True, # <-- НОВАЯ ОПЦИЯ
    'filename_template': "{date} - {basename}.md",
    'date_format': "%Y-%m-%d",
    'localization': {
        'en': {
            'user_header': "## User Prompt 👤",
            'model_header': "## Model Response 🤖",
            'thought_block_template': """> [!bug]- Model Thoughts 🧠\n> {thought_text}""",
            'system_instruction_header': "System Instruction ⚙️",
            'system_instruction_template': """> [!note]- {header}\n> {text}""",
            'metadata_table': {
                'header_parameter': "Parameter",
                'header_value': "Value",
                'model': '**Model**',
                'temperature': '**Temperature**',
                'top_p': '**Top-P**',
                'top_k': '**Top-K**',
                'web_search': '**Web Search**',
                'search_enabled': "Enabled",
                'search_disabled': "Disabled"
            },
            # <-- НОВЫЙ БЛОК ЛОКАЛИЗАЦИИ -->
            'grounding_metadata': {
                'spoiler_header': "Sources Used by the Model ℹ️",
                'queries_header': "**Search Queries:**",
                'sources_header': "**Sources:**"
            },
            'frontmatter_template_file': "frontmatter_template_en.txt"
        },
        'ru': {
            'user_header': "## Запрос пользователя 👤",
            'model_header': "## Ответ модели 🤖",
            'thought_block_template': """> [!bug]- Размышления модели 🧠\n> {thought_text}""",
            'system_instruction_header': "Системная инструкция ⚙️",
            'system_instruction_template': """> [!note]- {header}\n> {text}""",
            'metadata_table': {
                'header_parameter': "Настройка",
                'header_value': "Значение",
                'model': '**Модель**',
                'temperature': '**Температура**',
                'top_p': '**Top-P**',
                'top_k': '**Top-K**',
                'web_search': '**Поиск в Google**',
                'search_enabled': "Включен",
                'search_disabled': "Отключен"
            },
            # <-- НОВЫЙ БЛОК ЛОКАЛИЗАЦИИ -->
            'grounding_metadata': {
                'spoiler_header': "Источники, использованные моделью ℹ️",
                'queries_header': "**Поисковые запросы:**",
                'sources_header': "**Источники:**"
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
        print(Fore.YELLOW + f"Info: Configuration file '{CONFIG_FILE_NAME}' not found. Creating a new one with comments.")
        try:
            config_content = DEFAULT_CONFIG_TEMPLATE.format(
                language=DEFAULT_CONFIG['language'],
                enable_frontmatter=str(DEFAULT_CONFIG['enable_frontmatter']).lower(),
                enable_metadata_table=str(DEFAULT_CONFIG['enable_metadata_table']).lower(),
                enable_grounding_metadata=str(DEFAULT_CONFIG['enable_grounding_metadata']).lower(),
                filename_template=DEFAULT_CONFIG['filename_template'],
                date_format=DEFAULT_CONFIG['date_format']
            ).strip()
            
            with open(config_path, 'w', encoding='utf-8') as f:
                f.write(config_content + "\n")
                yaml.dump({'localization': DEFAULT_CONFIG['localization']}, f, allow_unicode=True, sort_keys=False, indent=2)
            return DEFAULT_CONFIG
        except IOError as e:
            print(Fore.RED + f"Error: Could not create config file: {e}. Using default settings.")
            return DEFAULT_CONFIG
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            user_config = yaml.safe_load(f) or {}
            config = {**DEFAULT_CONFIG, **user_config}
            
            if config.get('language') not in ['en', 'ru']:
                print(Fore.YELLOW + f"Warning: Invalid language '{config.get('language')}' in '{CONFIG_FILE_NAME}'. Defaulting to 'en'.")
                config['language'] = 'en'
                
            return config
    except (yaml.YAMLError, IOError) as e:
        print(Fore.RED + f"Error: Could not read config file '{CONFIG_FILE_NAME}': {e}. Using default settings.")
        return DEFAULT_CONFIG

def load_or_create_template(template_filename: str, lang: str) -> str:
    template_path = Path(template_filename)
    if not template_path.exists():
        print(Fore.YELLOW + f"Info: Template file '{template_filename}' not found. Creating a default one.")
        default_template = DEFAULT_FRONTMATTER_TEMPLATES.get(lang, DEFAULT_FRONTMATTER_TEMPLATES['en'])
        try:
            template_path.write_text(default_template, encoding='utf-8')
            return default_template
        except IOError as e:
            print(Fore.RED + f"Error: Could not create template file: {e}. Using a built-in template.")
            return default_template
    try:
        return template_path.read_text(encoding='utf-8')
    except IOError as e:
        print(Fore.RED + f"Error: Could not read template file: {e}. Using a built-in template.")
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

# --- НОВАЯ ФУНКЦИЯ: Форматирование метаданных поиска ---
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


class LogFileEventHandler(FileSystemEventHandler):
    def __init__(self, output_dir, overwrite, config, lang_templates, frontmatter_template):
        self.output_dir = output_dir
        self.overwrite = overwrite
        self.config = config
        self.lang_templates = lang_templates
        self.frontmatter_template = frontmatter_template
        self.last_processed = {}

    def on_created(self, event):
        if not event.is_directory:
            self._process_file(Path(event.src_path))

    def on_modified(self, event):
        if not event.is_directory:
            self._process_file(Path(event.src_path))

    def _is_valid_json(self, file_path):
        try:
            p = Path(file_path)
            if p.name == CONFIG_FILE_NAME or "frontmatter_template" in p.name:
                return False
            with open(p, 'r', encoding='utf-8') as f:
                json.load(f)
            return True
        except (json.JSONDecodeError, UnicodeDecodeError, PermissionError, IsADirectoryError, IOError):
            return False

    def _process_file(self, json_path):
        now = time.time()
        if json_path in self.last_processed and (now - self.last_processed.get(json_path, 0)) < 2:
            return
        
        time.sleep(0.5) 
        
        if self._is_valid_json(json_path):
            print(Fore.CYAN + f"\n[{datetime.now().strftime('%H:%M:%S')}] Detected valid file '{json_path.name}'. Processing...")
            process_files([json_path], self.output_dir, self.overwrite, self.config, self.lang_templates, self.frontmatter_template)
            self.last_processed[json_path] = now

def run_watch_mode(input_dir, output_dir, overwrite, config, lang_templates, frontmatter_template):
    print(Style.BRIGHT + f"--- Starting Watch Mode ---")
    
    print(Style.BRIGHT + "Performing initial scan of the directory...")
    initial_files = find_json_files(input_dir, recursive=False)
    if initial_files:
        process_files(initial_files, output_dir, overwrite, config, lang_templates, frontmatter_template)
    else:
        print("No initial files to process.")
    
    print(Style.BRIGHT + "\n--- Initial scan complete. Watching for new changes ---")
    print(f"👀 Watching folder: {Fore.YELLOW}'{input_dir}'")
    print(f"📄 Saving output to: {Fore.YELLOW}'{output_dir}'")
    print(f"🔄 Overwrite existing files: {'Yes' if overwrite else 'No'}")
    print(Fore.CYAN + "\n(Press Ctrl+C to stop watching)")

    event_handler = LogFileEventHandler(output_dir, overwrite, config, lang_templates, frontmatter_template)
    observer = Observer()
    observer.schedule(event_handler, str(input_dir), recursive=False)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("\n🛑 Watch mode stopped.")
    observer.join()

def run_interactive_mode(config, lang_templates, frontmatter_template):
    print(Style.BRIGHT + "--- AI Studio Log Converter (Interactive Mode) ---")
    
    while True:
        src_path_str = input(Fore.CYAN + f"➡️ Enter source path (default: '{DEFAULT_INPUT_DIR}'): " + Style.RESET_ALL).strip() or DEFAULT_INPUT_DIR
        src_path = Path(src_path_str)
        if src_path.exists():
            break
        print(Fore.RED + f"❌ Error: The path '{src_path}' does not exist. Please try again.")

    out_path_str = input(Fore.CYAN + f"➡️ Enter output path (default: '{DEFAULT_OUTPUT_DIR}'): " + Style.RESET_ALL).strip() or DEFAULT_OUTPUT_DIR
    output_dir = Path(out_path_str)

    recursive_str = input(Fore.CYAN + "➡️ Search recursively in subfolders? (y/N, default: N): " + Style.RESET_ALL).strip().lower()
    recursive = recursive_str == 'y'

    overwrite_str = input(Fore.CYAN + "➡️ Overwrite existing files? (y/N, default: N): " + Style.RESET_ALL).strip().lower()
    overwrite = overwrite_str == 'y'

    files = find_json_files(src_path, recursive)
    if not files:
        print(Fore.YELLOW + f"\n⚠️ No valid JSON files found in '{src_path}'.")
        print(Fore.YELLOW + "Please place your files there and run the program again.")
        return

    process_files(files, output_dir, overwrite, config, lang_templates, frontmatter_template)

class StdoutRedirector:
    """A class to redirect stdout to a tkinter Text widget."""
    def __init__(self, text_widget):
        self.text_space = text_widget
        # Regex to strip ANSI escape codes for clean logging in the GUI
        self.ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        self.line_buffer = ""

    def write(self, string):
        # Clean and buffer the incoming string
        cleaned_string = self.ansi_escape.sub('', string)
        self.line_buffer += cleaned_string
        
        # Process complete lines from the buffer
        while '\n' in self.line_buffer:
            line, self.line_buffer = self.line_buffer.split('\n', 1)
            self.text_space.configure(state='normal')
            # Insert the line with the 'indent' tag
            self.text_space.insert('end', line + '\n', "indent")
            self.text_space.see('end')
            self.text_space.configure(state='disabled')

    def flush(self):
        # Flush any remaining content in the buffer
        if self.line_buffer:
            self.text_space.configure(state='normal')
            self.text_space.insert('end', self.line_buffer + '\n', "indent")
            self.text_space.see('end')
            self.text_space.configure(state='disabled')
            self.line_buffer = ""

def run_gui_mode(config, lang_templates, frontmatter_template):
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")

    app = ctk.CTk()
    app.title("AI Studio Log Converter")
    app.geometry("800x600")
    app.minsize(800, 600)

    # --- Functions for GUI ---
    def select_input_path():
        path = filedialog.askdirectory(initialdir=DEFAULT_INPUT_DIR)
        if path:
            input_path_entry.delete(0, 'end')
            input_path_entry.insert(0, path)

    def select_output_path():
        path = filedialog.askdirectory(initialdir=DEFAULT_OUTPUT_DIR)
        if path:
            output_path_entry.delete(0, 'end')
            output_path_entry.insert(0, path)

    def start_conversion():
        start_button.configure(state="disabled")
        log_textbox.configure(state='normal')
        log_textbox.delete("1.0", "end")
        log_textbox.configure(state='disabled')

        input_path_str = input_path_entry.get() or DEFAULT_INPUT_DIR
        output_path_str = output_path_entry.get() or DEFAULT_OUTPUT_DIR
        
        input_path = Path(input_path_str)
        output_dir = Path(output_path_str)
        
        recursive = recursive_var.get()
        overwrite = overwrite_var.get()
        watch_mode = watch_var.get()

        if not input_path.exists():
            print(Fore.RED + f"❌ Error: The specified path does not exist: '{input_path}'")
            start_button.configure(state="normal")
            return

        try:
            if watch_mode:
                if not input_path.is_dir():
                    print(Fore.RED + "Error: In watch mode, the source path must be a directory.")
                else:
                    # Watch mode is blocking, so we can't run it directly in the main thread
                    # For now, we'll just print a message. A real implementation would need threading.
                    print(Fore.YELLOW + "Watch mode should be run from the command line.")
                    print(Fore.YELLOW + f"python ai-studio-log-converter.py \"{input_path}\" --watch")

            else:
                files = find_json_files(input_path, recursive)
                if not files:
                    print(Fore.YELLOW + f"\n⚠️ No valid JSON files found in '{input_path}'.")
                else:
                    process_files(files, output_dir, overwrite, config, lang_templates, frontmatter_template)
        except Exception as e:
            print(Fore.RED + f"An unexpected error occurred: {e}")
        finally:
            if not watch_mode:
                print("\n" + Style.BRIGHT + "Done! You can start a new conversion or close the program.")
            start_button.configure(state="normal")

    # --- GUI Layout ---
    app.grid_columnconfigure(0, weight=1)
    
    title_label = ctk.CTkLabel(app, text="Google AI Studio Log Converter", font=ctk.CTkFont(size=20, weight="bold"))
    title_label.grid(row=0, column=0, padx=20, pady=(10, 20), sticky="ew")

    # --- Frame for settings ---
    settings_frame = ctk.CTkFrame(app)
    settings_frame.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
    settings_frame.grid_columnconfigure(1, weight=1)

    # Input Path
    input_path_label = ctk.CTkLabel(settings_frame, text="Source Path:")
    input_path_label.grid(row=0, column=0, padx=10, pady=10, sticky="w")
    input_path_entry = ctk.CTkEntry(settings_frame, placeholder_text=DEFAULT_INPUT_DIR)
    input_path_entry.insert(0, DEFAULT_INPUT_DIR)
    input_path_entry.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
    input_browse_button = ctk.CTkButton(settings_frame, text="Browse...", command=select_input_path, width=100)
    input_browse_button.grid(row=0, column=2, padx=10, pady=10)

    # Output Path
    output_path_label = ctk.CTkLabel(settings_frame, text="Output Path:")
    output_path_label.grid(row=1, column=0, padx=10, pady=10, sticky="w")
    output_path_entry = ctk.CTkEntry(settings_frame, placeholder_text=DEFAULT_OUTPUT_DIR)
    output_path_entry.insert(0, DEFAULT_OUTPUT_DIR)
    output_path_entry.grid(row=1, column=1, padx=10, pady=10, sticky="ew")
    output_browse_button = ctk.CTkButton(settings_frame, text="Browse...", command=select_output_path, width=100)
    output_browse_button.grid(row=1, column=2, padx=10, pady=10)

    # Checkboxes
    checkbox_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
    checkbox_frame.grid(row=2, column=0, columnspan=3, padx=10, pady=10, sticky="w")
    
    recursive_var = ctk.BooleanVar()
    recursive_checkbox = ctk.CTkCheckBox(checkbox_frame, text="Search Recursively", variable=recursive_var)
    recursive_checkbox.pack(side="left", padx=5)

    overwrite_var = ctk.BooleanVar()
    overwrite_checkbox = ctk.CTkCheckBox(checkbox_frame, text="Overwrite Existing", variable=overwrite_var)
    overwrite_checkbox.pack(side="left", padx=5)

    watch_var = ctk.BooleanVar()
    watch_checkbox = ctk.CTkCheckBox(checkbox_frame, text="Watch Mode", variable=watch_var)
    watch_checkbox.pack(side="left", padx=5)

    # --- Start Button ---
    start_button = ctk.CTkButton(app, text="Start Conversion", command=start_conversion, height=40)
    start_button.grid(row=2, column=0, padx=20, pady=20, sticky="ew")

    # --- Log Textbox ---
    log_textbox = ctk.CTkTextbox(app, height=150, state='disabled', font=ctk.CTkFont(family="Courier New", size=12), wrap="word")
    log_textbox.grid(row=3, column=0, padx=20, pady=(0, 20), sticky="nsew")
    log_textbox.tag_config("indent", lmargin1=10) # Add left margin to each line
    app.grid_rowconfigure(3, weight=1)

    # Redirect stdout
    sys.stdout = StdoutRedirector(log_textbox)

    app.mainloop()

def log_crash(exc_info):
    """Logs crash information to a file and shows a popup."""
    log_file = "crash_log.txt"
    error_details = "".join(traceback.format_exception(exc_info[0], exc_info[1], exc_info[2]))
    
    try:
        with open(log_file, "w", encoding="utf-8") as f:
            f.write("A critical error occurred:\n")
            f.write(error_details)
        print(f"Critical error. Details saved to {log_file}")
    except Exception as e:
        print(f"Failed to write crash log: {e}")

    # Show error in a simple tkinter messagebox as customtkinter might not be available
    try:
        # Use a temporary root for the messagebox
        root = ctk.CTk()
        root.withdraw() 
        messagebox.showerror(
            "Application Crash",
            f"A critical error occurred!\n\nDetails have been saved to {log_file}"
        )
    except Exception as e:
        print(f"Failed to show crash popup: {e}")


def main():
    # Добавляем импорт urlparse в начало файла, если его там еще нет
    # from urllib.parse import urlparse
    
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
    parser.add_argument("input_path", nargs='?', type=Path, default=None,
                        help=f"Source file or folder. If omitted, runs in interactive mode.")
    parser.add_argument("-o", "--output", type=Path, default=output_dir_default,
                        help=f"Output directory (default: '{DEFAULT_OUTPUT_DIR}').")
    parser.add_argument("-r", "--recursive", action="store_true", help="Search recursively.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing files.")
    parser.add_argument("--watch", action="store_true", help="Run in watch mode to automatically convert new files.")
    parser.add_argument("-c", "--cli", action="store_true", help="Force run in command-line interactive mode instead of GUI.")
    
    args = parser.parse_args()

    # Logic to decide which mode to run
    if args.watch:
        # Watch mode takes precedence
        input_path = args.input_path if args.input_path is not None else input_dir_default
        if not input_path.is_dir():
            print(Fore.RED + "Error: In --watch mode, the input path must be a directory.")
            sys.exit(1)
        run_watch_mode(input_path, args.output, args.overwrite, config, lang_templates, frontmatter_template)
    
    elif args.input_path is not None:
        # Batch processing with a given path
        files = find_json_files(args.input_path, args.recursive)
        if not files:
            print(Fore.YELLOW + f"\n⚠️ No valid JSON files found in '{args.input_path}'.")
            if args.input_path == input_dir_default:
                 print(Fore.YELLOW + "Please place your files there and run the program again.")
            return
        process_files(files, args.output, args.overwrite, config, lang_templates, frontmatter_template)

    elif args.cli:
        # Forced interactive CLI mode
        run_interactive_mode(config, lang_templates, frontmatter_template)

    else:
        # Default to GUI mode if no other flags are provided
        try:
            run_gui_mode(config, lang_templates, frontmatter_template)
        except Exception:
            log_crash(sys.exc_info())
            sys.exit(1) # Exit with an error code
    
    # В режиме GUI этот код не будет достигнут, так как окно имеет свой цикл.
    # Для .exe, запущенного из консоли, это позволит окну не закрываться сразу.
    if getattr(sys, 'frozen', False) and not args.watch and not (len(sys.argv) == 1):
        input("\nPress Enter to exit.")

if __name__ == "__main__":
    main()
