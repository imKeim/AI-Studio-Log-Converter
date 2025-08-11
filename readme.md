# AI Studio Log Converter

A versatile command-line and interactive tool to convert Google AI Studio chat logs (.json) into well-formatted Markdown (.md) files, perfect for knowledge bases like Obsidian.

## Features

- **Interactive Mode**: A user-friendly wizard guides you through the conversion process. No command-line skills needed!
- **Command-Line Mode**: For power users and automation, all features are available via command-line arguments.
- **External Configuration**: Easily customize settings in `config.yaml`.
- **Custom Templates**: Full control over the YAML frontmatter and output filename via external template files.
- **Recursive Search**: Process files in a directory and all its subdirectories.
- **Flexible Output**: Save converted files next to their originals or redirect them all to a single folder.
- **Safe by Default**: Won't overwrite existing Markdown files unless you explicitly allow it.

## Installation

Simply place `converter.exe` in any folder. For the best experience, keep it together with `config.yaml` and `frontmatter_template.txt`.

If you are running from source, install the required Python packages:
```bash
pip install pyyaml tqdm
```

## How to Use

### Standard Usage (Recommended)

1.  Run `converter.exe` once. It will automatically create two folders: `input` and `output`.
2.  Place all your `.json` log files into the `input` folder. You can create subdirectories inside `input` if you wish.
3.  Run `converter.exe` again.
4.  The program will process all files from the `input` folder and save the converted `.md` files in the `output` folder.

The interactive mode will simply ask you about recursive search and overwriting files, as the input/output folders are now set by default.

### Command-Line Mode (Advanced)

You can override the default folders using command-line arguments.

- `converter.exe`: Processes `./input` -> `./output`.
- `converter.exe C:\my_logs`: Processes `C:\my_logs` -> `./output`.
- `converter.exe C:\my_logs -o D:\final_notes`: Processes `C:\my_logs` -> `D:\final_notes`.

### Command-Line Mode (Advanced)

You can also use command-line arguments for automation.

**Syntax:**
`converter.exe [input_path] [options]`

**Arguments & Options:**
- `input_path`: (Required) Path to the source .json file or folder.
- `-o`, `--output`: (Optional) Path to a single directory where all .md files will be saved. If omitted, files are saved next to their sources.
- `-r`, `--recursive`: (Optional) Enable recursive search in subdirectories.
- `--overwrite`: (Optional) Allow overwriting existing .md files.

**Examples:**
```bash
# Convert all files in the current folder recursively
converter.exe . -r

# Convert a specific file and save the output in D:\Notes
converter.exe "C:\logs\my_chat.json" -o "D:\Notes"

# Convert all files from a folder, saving them next to originals, and allow overwriting
converter.exe "C:\all_my_logs" -r --overwrite
```

## Configuration

### `config.yaml`

This file controls the core behavior of the converter.

- `enable_frontmatter`: `true` or `false`. Toggles the creation of the YAML frontmatter block.
- `filename_template`: A template for the output filename.
  - `{date}`: The file's modification date.
  - `{basename}`: The original filename without extension.
- `date_format`: The format for the `{date}` variable (using Python's `strftime` syntax).
- `user_header`, `model_header`: The Markdown headers for user and model turns.
- `thought_block_template`: The template for the model's "thought" blocks (supports Obsidian callouts).

### `frontmatter_template.txt`

This file contains the exact template for the YAML frontmatter. It will be ignored if `enable_frontmatter` is `false` in `config.yaml`.

**Available variables:**
- `{title}`: The note's title, derived from the filename.
- `{cdate}`: The source file's creation date.
- `{mdate}`: The source file's modification date.