# src/config.py

"""
Module for handling all configuration-related tasks.

This includes loading the main `config.yaml`, creating it with defaults if it doesn't exist,
and managing frontmatter templates. All default settings and constants are defined here
to provide a single source of truth for configuration values across the application.
"""

import yaml
from pathlib import Path
from colorama import Fore, Style

# --- Constants ---
# Define constants for filenames and directories to avoid magic strings.
CONFIG_FILE_NAME = "config.yaml"
DEFAULT_INPUT_DIR = "input"
DEFAULT_OUTPUT_DIR = "output"
ASSETS_DIR_NAME = "assets"

# --- Default Configuration Templates ---

# A template for generating a well-commented config.yaml file on the first run.
# This helps users understand the available settings without reading the source code.
DEFAULT_CONFIG_TEMPLATE = """
# --- AI Studio Log Converter Settings ---

# Language for the generated Markdown files. (en/ru)
language: '{language}'

# Enable/disable the YAML frontmatter block at the start of the file.
enable_frontmatter: {enable_frontmatter}

# Enable/disable the metadata table with run settings (Model, Temperature, etc.).
enable_metadata_table: {enable_metadata_table}

# Enable/disable the grounding metadata block (web search sources) at the end of Template for the output filename.
# Available variables: {{date}}, {{basename}}
filename_template: '{filename_template}'

# Date format for the {{date}} variable in the filename.
# Python strftime syntax: https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes
date_format: '{date_format}'

# --- Localization Settings ---
# Text templates for different languages.
# The 'language' setting above determines which set of templates to use.
"""

# A dictionary holding the default configuration values.
# This structure is used as a fallback and to create the initial config file.
DEFAULT_CONFIG = {
    'language': 'en',
    'enable_frontmatter': True,
    'enable_metadata_table': True,
    'enable_grounding_metadata': True,
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
            'grounding_metadata': {
                'spoiler_header': "Источники, использованные моделью ℹ️",
                'queries_header': "**Поисковые запросы:**",
                'sources_header': "**Источники:**"
            },
            'frontmatter_template_file': "frontmatter_template_ru.txt"
        }
    }
}

# Default templates for the frontmatter, separated by language.
# These are used if the template files are missing.
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

# --- Functions ---

def load_or_create_config() -> dict:
    """
    Loads the configuration from config.yaml or creates it from a template if it doesn't exist.
    
    This function ensures that the application always has a valid configuration to work with.
    It merges the user's settings with the defaults to prevent errors if the user's config
    is missing some keys.
    
    Returns:
        dict: The fully populated configuration dictionary.
    """
    config_path = Path(CONFIG_FILE_NAME)
    if not config_path.exists():
        print(Fore.YELLOW + f"Info: Configuration file '{CONFIG_FILE_NAME}' not found. Creating a new one with comments.")
        try:
            # Format the template with default values to create a helpful initial config file.
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
                # Dump the complex 'localization' dictionary separately for clean YAML formatting.
                yaml.dump({'localization': DEFAULT_CONFIG['localization']}, f, allow_unicode=True, sort_keys=False, indent=2)
            return DEFAULT_CONFIG
        except IOError as e:
            print(Fore.RED + f"Error: Could not create config file: {e}. Using default settings.")
            return DEFAULT_CONFIG
            
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            user_config = yaml.safe_load(f) or {}
            # Merge default config with user's config. User's values take precedence.
            config = {**DEFAULT_CONFIG, **user_config}
            
            # Validate the language setting to prevent errors later.
            if config.get('language') not in ['en', 'ru']:
                print(Fore.YELLOW + f"Warning: Invalid language '{config.get('language')}' in '{CONFIG_FILE_NAME}'. Defaulting to 'en'.")
                config['language'] = 'en'
                
            return config
    except (yaml.YAMLError, IOError) as e:
        print(Fore.RED + f"Error: Could not read config file '{CONFIG_FILE_NAME}': {e}. Using default settings.")
        return DEFAULT_CONFIG

def load_or_create_template(template_filename: str, lang: str) -> str:
    """
    Loads a frontmatter template from a file or creates a default one if it's missing.

    Args:
        template_filename (str): The name of the template file to load.
        lang (str): The language ('en' or 'ru') to use for the default template.

    Returns:
        str: The content of the frontmatter template.
    """
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
