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

DEFAULT_CONFIG_TEMPLATE = """
# --- AI Studio Log Converter Settings ---

# Language for the generated Markdown files. (en/ru)
language: '{language}'

# Enable/disable the YAML frontmatter block at the start of the file.
enable_frontmatter: {enable_frontmatter}

# Enable/disable the metadata table with run settings (Model, Temperature, etc.).
enable_metadata_table: {enable_metadata_table}

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
        print(f"Info: Configuration file '{CONFIG_FILE_NAME}' not found. Creating a new one with comments.")
        try:
            config_content = DEFAULT_CONFIG_TEMPLATE.format(
                language=DEFAULT_CONFIG['language'],
                enable_frontmatter=str(DEFAULT_CONFIG['enable_frontmatter']).lower(),
                enable_metadata_table=str(DEFAULT_CONFIG['enable_metadata_table']).lower(),
                filename_template=DEFAULT_CONFIG['filename_template'],
                date_format=DEFAULT_CONFIG['date_format']
            ).strip()
            
            with open(config_path, 'w', encoding='utf-8') as f:
                f.write(config_content + "\n")
                yaml.dump({'localization': DEFAULT_CONFIG['localization']}, f, allow_unicode=True, sort_keys=False, indent=2)
            return DEFAULT_CONFIG
        except IOError as e:
            print(f"Error: Could not create config file: {e}. Using default settings.")
            return DEFAULT_CONFIG
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            user_config = yaml.safe_load(f) or {}
            config = {**DEFAULT_CONFIG, **user_config}
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
            
      