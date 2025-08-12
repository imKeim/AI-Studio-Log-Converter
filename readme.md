# AI Studio Log Converter

A powerful and flexible tool to convert Google AI Studio chat logs (JSON format) into well-structured Markdown (`.md`) files, perfect for knowledge bases like Obsidian. It intelligently handles various data formats, extracts metadata, saves embedded images, and is highly customizable.

![AI Studio Log Converter GUI](docs/images/app_screenshot.png)

## Features

- **✨ Modern GUI:** A clean, user-friendly graphical interface built with CustomTkinter.
- **🤖 Smart Parsing:** Intelligently handles multiple JSON formats from different AI Studio versions.
- **🖼️ Image Handling:** Automatically saves `inlineData` (base64) images to an `assets` folder and creates local links.
- **🔗 Link Placeholders:** Creates clickable links for `driveImage` and `youtubeVideo` references, preserving context.
- **📊 Metadata Table:** Generates a convenient Markdown table at the top of each file with key session parameters (Model, Temperature, etc.).
- **⚙️ Full Configuration:** All settings, including templates and localization, are controlled via an easy-to-edit `config.yaml` file.
- **🌐 Localization (EN/RU):** All generated headers and templates can be switched between English and Russian.
- **👀 Watch Mode:** Automatically convert files as they are added or modified in the input folder (CLI only).
- **📁 Smart Folder Structure:** Works with a clean `input`/`output` folder structure by default, which is created automatically.

## Usage for End-Users

This is the simplest way to use the converter without needing Python installed.

1.  Download the latest `.zip` archive from the [Releases](https://github.com/imKeim/AI-Studio-Log-Converter/releases) page.
2.  Extract the archive. You will get a folder with `ai-studio-log-converter.exe`, `config.yaml`, and other template files.
3.  Double-click `ai-studio-log-converter.exe` to run the graphical interface.
4.  Use the "Browse..." buttons to select your source and output folders.
5.  Choose your options using the checkboxes.
6.  Click "Start Conversion"!

## Running in the Background (Hidden Mode)

To run **Watch Mode** silently without a visible console window, you can create a simple helper script.

1.  **Create a new text file** in the same folder as `ai-studio-log-converter.exe`.
2.  **Paste the following code:**
    ```vbscript
    Set WshShell = CreateObject("WScript.Shell")
    WshShell.Run "ai-studio-log-converter.exe --watch", 0, false
    ```
3.  **Save the file** with a `.vbs` extension (e.g., `start_watch_hidden.vbs`).

Now, you can double-click the `.vbs` file to launch the converter silently. To stop it, use the Task Manager (`Ctrl+Shift+Esc`) to end the `ai-studio-log-converter.exe` process.

## For Developers

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
3.  Run the application:
    ```bash
    # To launch the GUI (default)
    python ai-studio-log-converter.pyw

    # To launch the interactive CLI
    python ai-studio-log-converter.pyw --cli
    ```

## Building the Executable

### Method 1: Using the Build Script (Recommended for Windows)

The easiest way to build the application on Windows is to use the provided batch script.

1.  Install all development dependencies:
    ```bash
    pip install -r requirements-dev.txt
    ```
2.  Simply double-click the `build.bat` file.

The script will automatically install all dependencies, run PyInstaller with the correct options, and clean up temporary files.

### Method 2: Manual Build

1.  Install all dependencies:
    ```bash
    pip install -r requirements.txt
    pip install -r requirements-dev.txt
    ```
2.  Run the build command from the project root:
    ```bash
    python -m PyInstaller --onefile --windowed --name "AI-Studio-Log-Converter" --icon="logo.ico" --add-data "src/custom_theme.json;." --add-data "logo.ico;." --add-data "logo.png;." "ai-studio-log-converter.pyw"
    ```
3.  The final `AI-Studio-Log-Converter.exe` will be in the `dist` folder.

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
type: llm-log
kind: google-ai-studio
tags: 
status: archived
cdate: {cdate}
mdate: {mdate}
---
```