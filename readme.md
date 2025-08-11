# AI Studio Log Converter

A powerful and flexible tool to convert Google AI Studio chat logs (JSON format) into well-structured Markdown (`.md`) files, perfect for knowledge bases like Obsidian. It intelligently handles various data formats, extracts metadata, saves embedded images, and is highly customizable.

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

## Running in the Background (Hidden Mode)

If you want the converter to run silently in the background using **Watch Mode** without a visible console window, you can create a simple helper script.

1.  **Create a new text file** in the same folder as `ai-studio-log-converter.exe`.
2.  **Open the file** in a text editor (like Notepad) and paste the following code:
    ```vbscript
    Set WshShell = CreateObject("WScript.Shell")
    WshShell.Run "ai-studio-log-converter.exe --watch", 0, false
    ```
    *   You can also specify a custom folder to watch, for example:
        `WshShell.Run "ai-studio-log-converter.exe ""C:\My Logs\AI Studio"" --watch", 0, false`
3.  **Save the file** with a `.vbs` extension (e.g., `start_watch_hidden.vbs`). Make sure to select "All Files (\*.\*)" in the "Save as type" dropdown to avoid saving it as a `.txt` file.

Now, you can double-click the `start_watch_hidden.vbs` file to launch the converter silently.

**To stop the background process:**
- Open the **Task Manager** (`Ctrl+Shift+Esc`).
- Go to the "Details" tab.
- Find `ai-studio-log-converter.exe` in the list and click "End task".

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
    *   For GUI mode:
        ```bash
        python ai-studio-log-converter.pyw
        ```
    *   Using command-line arguments:
        ```bash
        # Process a specific folder and save results to another folder
        python ai-studio-log-converter.pyw "C:\path\to\my-logs" -o "D:\converted-notes" -r --overwrite

        # Run in watch mode to automatically convert new/modified files in the 'input' folder
        python ai-studio-log-converter.pyw --watch
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
    python -m PyInstaller --onefile --noconsole --hidden-import watchdog ai-studio-log-converter.pyw
    ```
    *   `--onefile`: This flag packages everything into a single executable file.
    *   `--noconsole`: This flag prevents the console window from appearing when the `.exe` is run.
    *   `--hidden-import watchdog`: **Crucial!** Explicitly tells PyInstaller to include the `watchdog` library, which it might miss otherwise during static analysis.
    *   `ai-studio-log-converter.pyw`: Make sure this matches the name of your Python script (note the `.pyw` extension for windowed applications).

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
type: llm-log
kind: google-ai-studio
tags: 
status: archived
cdate: {cdate}
mdate: {mdate}
---
