# src/cli.py

"""
Module for all command-line interface (CLI) operations.

This includes the interactive mode for manual conversion and the watch mode
for automatic processing of new files. It helps separate the user-facing
CLI logic from the core conversion and GUI code.
"""

import time
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from colorama import Fore, Style

# Import functions and constants from other modules.
from .converter import find_json_files, process_files
from .config import DEFAULT_INPUT_DIR, DEFAULT_OUTPUT_DIR, CONFIG_FILE_NAME

class LogFileEventHandler(FileSystemEventHandler):
    """
    A handler for file system events, used in watch mode.
    It triggers a conversion when a new valid JSON file is created or modified.
    """
    def __init__(self, output_dir, overwrite, config, lang_templates, frontmatter_template):
        self.output_dir = output_dir
        self.overwrite = overwrite
        self.config = config
        self.lang_templates = lang_templates
        self.frontmatter_template = frontmatter_template
        # A dictionary to prevent processing the same file multiple times in quick succession.
        self.last_processed = {}

    def on_created(self, event):
        if not event.is_directory:
            self._process_file(Path(event.src_path))

    def on_modified(self, event):
        if not event.is_directory:
            self._process_file(Path(event.src_path))

    def _is_valid_json(self, file_path):
        """Checks if a file is a valid JSON and not a config file."""
        try:
            p = Path(file_path)
            # Ignore config files to avoid an infinite loop if they are modified.
            if p.name == CONFIG_FILE_NAME or "frontmatter_template" in p.name:
                return False
            with open(p, 'r', encoding='utf-8') as f:
                json.load(f)
            return True
        except (json.JSONDecodeError, UnicodeDecodeError, PermissionError, IsADirectoryError, IOError):
            return False

    def _process_file(self, json_path):
        """Processes a single file, with a debounce mechanism."""
        now = time.time()
        # Debounce: if the file was processed less than 2 seconds ago, skip it.
        if json_path in self.last_processed and (now - self.last_processed.get(json_path, 0)) < 2:
            return
        
        # Wait a moment for the file to be fully written to disk.
        time.sleep(0.5) 
        
        if self._is_valid_json(json_path):
            print(Fore.CYAN + f"\n[{datetime.now().strftime('%H:%M:%S')}] Detected valid file '{json_path.name}'. Processing...")
            process_files([json_path], self.output_dir, self.overwrite, self.config, self.lang_templates, self.frontmatter_template)
            self.last_processed[json_path] = now

def run_watch_mode(input_dir, output_dir, overwrite, config, lang_templates, frontmatter_template):
    """
    Runs the application in watch mode, monitoring a directory for changes.
    """
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
    """
    Runs the application in an interactive command-line mode.
    """
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
