import sys
import argparse
import traceback
from pathlib import Path
import customtkinter as ctk
from tkinter import messagebox

# Абсолютный импорт из папки src
from src.config import (
    load_or_create_config,
    load_or_create_template,
    DEFAULT_CONFIG,
    DEFAULT_INPUT_DIR,
    DEFAULT_OUTPUT_DIR
)
from src.converter import (
    find_json_files,
    process_files
)
from src.cli import (
    run_interactive_mode,
    run_watch_mode
)
from src.gui import run_gui_mode
from colorama import Fore, Style, init

# Инициализация Colorama
init(autoreset=True)

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

    try:
        root = ctk.CTk()
        root.withdraw() 
        messagebox.showerror(
            "Application Crash",
            f"A critical error occurred!\n\nDetails have been saved to {log_file}"
        )
    except Exception as e:
        print(f"Failed to show crash popup: {e}")

def main():
    """Main function to run the application."""
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
                        help=f"Source file or folder. If omitted, runs in GUI mode.")
    parser.add_argument("-o", "--output", type=Path, default=output_dir_default,
                        help=f"Output directory (default: '{DEFAULT_OUTPUT_DIR}').")
    parser.add_argument("-r", "--recursive", action="store_true", help="Search recursively.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing files.")
    parser.add_argument("--watch", action="store_true", help="Run in watch mode to automatically convert new files.")
    parser.add_argument("-c", "--cli", action="store_true", help="Force run in command-line interactive mode instead of GUI.")
    
    args = parser.parse_args()

    # Logic to decide which mode to run
    if args.watch:
        input_path = args.input_path if args.input_path is not None else input_dir_default
        if not input_path.is_dir():
            print(Fore.RED + "Error: In --watch mode, the input path must be a directory.")
            sys.exit(1)
        run_watch_mode(input_path, args.output, args.overwrite, config, lang_templates, frontmatter_template)
    
    elif args.input_path is not None:
        files = find_json_files(args.input_path, args.recursive)
        if not files:
            print(Fore.YELLOW + f"\n⚠️ No valid JSON files found in '{args.input_path}'.")
            if args.input_path == input_dir_default:
                 print(Fore.YELLOW + "Please place your files there and run the program again.")
            return
        process_files(files, args.output, args.overwrite, config, lang_templates, frontmatter_template)

    elif args.cli:
        run_interactive_mode(config, lang_templates, frontmatter_template)

    else:
        try:
            run_gui_mode(config, lang_templates, frontmatter_template)
        except Exception:
            log_crash(sys.exc_info())
            sys.exit(1)

if __name__ == "__main__":
    main()
