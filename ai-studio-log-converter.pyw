# Standard library imports
import sys
import argparse
import traceback
from pathlib import Path
import os

# Third-party imports
import customtkinter as ctk
from tkinter import messagebox
from colorama import Fore, Style, init

# Local application imports
# These are absolute imports from the 'src' folder, which is treated as a package.
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

# --- Helper Function for PyInstaller ---

def resource_path(relative_path):
    """
    Get the absolute path to a resource. This is crucial for PyInstaller,
    as it bundles assets into a temporary folder (_MEIPASS) at runtime.
    This function ensures that whether running from source or as a compiled
    .exe, the application can find its assets (like icons and themes).
    """
    try:
        # PyInstaller creates a temp folder and stores its path in _MEIPASS.
        base_path = sys._MEIPASS
    except Exception:
        # If not running in a PyInstaller bundle, use the normal absolute path.
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

# --- Main Application Logic ---

def log_crash(exc_info):
    """
    Logs unhandled exceptions to a file and displays a user-friendly error popup.
    This prevents the application from closing silently on a critical error.
    """
    log_file = "crash_log.txt"
    # The traceback module provides a detailed, formatted exception string.
    error_details = "".join(traceback.format_exception(exc_info[0], exc_info[1], exc_info[2]))
    
    try:
        with open(log_file, "w", encoding="utf-8") as f:
            f.write("A critical error occurred:\n")
            f.write(error_details)
        print(f"Critical error. Details saved to {log_file}")
    except Exception as e:
        print(f"Failed to write crash log: {e}")

    # Display a GUI popup to inform the user, which is more user-friendly
    # than a console message, especially for a GUI application.
    try:
        # A temporary root window is needed to show a messagebox.
        root = ctk.CTk()
        root.withdraw()  # Hide the empty root window.
        messagebox.showerror(
            "Application Crash",
            f"A critical error occurred!\n\nDetails have been saved to {log_file}"
        )
    except Exception as e:
        print(f"Failed to show crash popup: {e}")

def main():
    """
    The main function that orchestrates the entire application.
    It sets up the environment, parses arguments, and launches the correct mode.
    """
    # Initialize Colorama to make terminal output colorful and cross-platform.
    init(autoreset=True)

    # Ensure default input/output directories exist on startup.
    input_dir_default = Path(DEFAULT_INPUT_DIR)
    output_dir_default = Path(DEFAULT_OUTPUT_DIR)
    input_dir_default.mkdir(exist_ok=True)
    output_dir_default.mkdir(exist_ok=True)

    # Load configuration from files or create them if they don't exist.
    # This ensures the app always has a valid config to work with.
    config = load_or_create_config()
    lang = config.get('language', 'en')
    lang_templates = config.get('localization', {}).get(lang, DEFAULT_CONFIG['localization']['en'])
    frontmatter_template_file = lang_templates.get('frontmatter_template_file', f"frontmatter_template_{lang}.txt")
    frontmatter_template = load_or_create_template(frontmatter_template_file, lang)

    # --- Argument Parsing ---
    # argparse is used to define and parse command-line arguments,
    # making the application flexible and scriptable.
    parser = argparse.ArgumentParser(description="Converts Google AI Studio logs to Markdown.")
    parser.add_argument("input_path", nargs='?', type=Path, default=None,
                        help="Source file or folder. If omitted, runs in GUI mode.")
    parser.add_argument("-o", "--output", type=Path, default=output_dir_default,
                        help=f"Output directory (default: '{DEFAULT_OUTPUT_DIR}').")
    parser.add_argument("-r", "--recursive", action="store_true", help="Search recursively.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing files.")
    parser.add_argument("--watch", action="store_true", help="Run in watch mode to automatically convert new files.")
    parser.add_argument("-c", "--cli", action="store_true", help="Force run in command-line interactive mode instead of GUI.")
    
    args = parser.parse_args()

    # --- Mode Selection Logic ---
    # The application decides which mode to run based on the provided arguments.
    # This logic block is the central dispatcher for the app's functionality.
    if args.watch:
        # Watch mode is for continuous, automatic conversion.
        input_path = args.input_path if args.input_path is not None else input_dir_default
        if not input_path.is_dir():
            print(Fore.RED + "Error: In --watch mode, the input path must be a directory.")
            sys.exit(1)
        run_watch_mode(input_path, args.output, args.overwrite, config, lang_templates, frontmatter_template)
    
    elif args.input_path is not None:
        # Batch mode: process a specific file or folder once and exit.
        files = find_json_files(args.input_path, args.recursive)
        if not files:
            print(Fore.YELLOW + f"\n⚠️ No valid JSON files found in '{args.input_path}'.")
            if args.input_path == input_dir_default:
                 print(Fore.YELLOW + "Please place your files there and run the program again.")
            return
        process_files(files, args.output, args.overwrite, config, lang_templates, frontmatter_template)

    elif args.cli:
        # Interactive CLI mode for users who prefer the command line.
        run_interactive_mode(config, lang_templates, frontmatter_template)

    else:
        # Default mode: run the GUI if no other mode is specified.
        try:
            # The resource_path function is passed to the GUI so it can find assets.
            run_gui_mode(config, lang_templates, frontmatter_template, resource_path)
        except Exception:
            # If the GUI crashes, log the error and exit gracefully.
            log_crash(sys.exc_info())
            sys.exit(1)

if __name__ == "__main__":
    # This is the standard entry point for a Python script.
    # The code inside this block will only run when the script is executed directly.
    main()
