# AI Studio Log Converter

A powerful and flexible tool to convert Google AI Studio chat logs (JSON format) into well-structured Markdown (`.md`) files, perfect for knowledge bases like Obsidian. It intelligently handles various data formats, extracts metadata, saves embedded images, and is highly customizable.

## Features

- **🤖 Smart Parsing:** Intelligently handles multiple JSON formats from different AI Studio versions.
- **🖼️ Image Handling:** Automatically saves `inlineData` (base64) images to an `assets` folder and creates local links.
- **🔗 Link Placeholders:** Creates clickable links for `driveImage` and `youtubeVideo` references, preserving context.
- **📊 Metadata Table:** Generates a convenient Markdown table at the top of each file with key session parameters (Model, Temperature, etc.).
- **⚙️ Full Configuration:** All settings, including templates and localization, are controlled via an easy-to-edit `config.yaml` file.
- **🌐 Localization (EN/RU):** All generated headers and templates can be switched between English and Russian.
- **✨ Interactive & CLI Modes:** Run a user-friendly wizard by double-clicking the `.exe` or use command-line arguments for automation.
- **📁 Smart Folder Structure:** Works with a clean `input`/`output` folder structure by default, which is created automatically.

## Usage for End-Users

This is the simplest way to use the converter without needing Python installed.

1.  Download the latest `.zip` archive from the [Releases](https://github.com/imKeim/AI-Studio-Log-Converter/releases) page.
2.  Extract the archive. You will get a folder with `ai-studio-log-converter.exe`, `config.yaml`, and other template files.
3.  Place your JSON log files (with or without `.json` extension) into the `input` folder.
4.  Double-click `ai-studio-log-converter.exe` to run the interactive wizard.
5.  Your converted `.md` files and any extracted images will appear in the `output` folder.

## Usage for Developers (Running from Source)

### Prerequisites
- Python 3.8+

### Setup
1.  Clone the repository:
    ```bash
    git clone https://github.com/imKeim/AI-Studio-Log-Converter.git
    cd AI-Studio-Log-Converter
    ```
2.  Install the required dependencies:
    ```bash
    pip install -r requirements.txt
    ```
3.  Place your JSON log files into the `input` folder.

4.  Run the script:
    *   For interactive mode:
        ```bash
        python ai-studio-log-converter.py
        ```
    *   Using command-line arguments:
        ```bash
        # Process default input folder, run recursively, and overwrite existing files
        python ai-studio-log-converter.py -r --overwrite

        # Process a specific folder and save results to another folder
        python ai-studio-log-converter.py "C:\path\to\my-logs" -o "D:\converted-notes"
        ```

## How to Build the `.exe` File

You can compile the script into a single, portable `.exe` file using PyInstaller.

1.  **Install PyInstaller:**
    ```bash
    pip install pyinstaller
    ```

2.  **Navigate to the project directory** in your terminal.

3.  **Run the build command:**
    ```bash
    python -m PyInstaller --onefile ai-studio-log-converter.py
    ```
    *   `--onefile`: This flag packages everything into a single executable file.
    *   `ai-studio-log-converter.py`: Make sure this matches the name of your Python script.

4.  **Find the result:** The final `ai-studio-log-converter.exe` file will be located in the `dist` folder.

## Configuration

The converter is fully customizable via the `config.yaml` and template files, which are created automatically on the first run.

### `config.yaml`

This file controls the main behavior of the script.

```yaml
# Language for the generated Markdown files. (en/ru)
language: 'en'
# Enable/disable the YAML frontmatter block.
enable_frontmatter: true
# Enable/disable the metadata table with run settings.
enable_metadata_table: true
# Template for the output filename. {date}, {basename}
filename_template: '{date} - {basename}.md'
# Date format for the {date} variable.
date_format: '%Y-%m-%d'

# Text templates for different languages.
localization:
  en:
    user_header: '## User Prompt 👤'
    model_header: '## Model Response 🤖'
    thought_block_template: |
      > [!bug]- Model Thoughts 🧠
      > {thought_text}
    system_instruction_header: System Instruction ⚙️
    system_instruction_template: |
      > [!note]- {header}
      > {text}
    metadata_table:
      header_parameter: Parameter
      header_value: Value
      model: '**Model**'
      temperature: '**Temperature**'
      top_p: '**Top-P**'
      top_k: '**Top-K**'
      web_search: '**Web Search**'
      search_enabled: Enabled
      search_disabled: Disabled
    frontmatter_template_file: frontmatter_template_en.txt
  ru:
    # ... Russian localization ...
```

### `frontmatter_template_en.txt`

This file contains the template for the YAML frontmatter.

```yaml
---
title: "{title}"
aliases:
  - "{title}"
para: resource
type: ll-log
kind: google-ai-studio
tags: 
status: archived
cdate: {cdate}
mdate: {mdate}
---
```