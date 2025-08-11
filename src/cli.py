# src/cli.py

"""
Module for all command-line interface (CLI) operations.

This includes the interactive mode for manual conversion and the watch mode
for automatic processing of new files. It helps separate the user-facing
CLI logic from the core conversion and GUI code.
"""

__all__ = ["run_watch_mode", "run_interactive_mode", "LogFileEventHandler"]

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
    Handles file system events for the 'watch' mode.

    This class, inheriting from watchdog's FileSystemEventHandler, is the core
    of the watch mode functionality. It listens for file creation and modification
    events in the specified input directory and triggers the conversion process
    for valid JSON files.
    """
    def __init__(self, output_dir, overwrite, config, lang_templates, frontmatter_template):
        """
        Initializes the event handler with all necessary conversion parameters.
        """
        self.output_dir = output_dir
        self.overwrite = overwrite
        self.config = config
        self.lang_templates = lang_templates
        self.frontmatter_template = frontmatter_template
        # This dictionary acts as a debounce mechanism to prevent processing the same
        # file multiple times in rapid succession (e.g., on create then modify).
        self.last_processed = {}

    def on_created(self, event):
        """Called when a file or directory is created."""
        if not event.is_directory:
            self._process_file(Path(event.src_path))

    def on_modified(self, event):
        """Called when a file or directory is modified."""
        if not event.is_directory:
            self._process_file(Path(event.src_path))

    def _is_valid_json(self, file_path):
        """
        Validates if a given file is a processable JSON log.

        It checks that the file is valid JSON and is not one of the application's
        own configuration files, which could otherwise trigger an infinite loop
        if they are modified.
        """
        try:
            p = Path(file_path)
            # Explicitly ignore the main config file and frontmatter template.
            if p.name == CONFIG_FILE_NAME or "frontmatter_template" in p.name:
                return False
            # The most reliable check is to actually try parsing the file.
            with open(p, 'r', encoding='utf-8') as f:
                json.load(f)
            return True
        except (json.JSONDecodeError, UnicodeDecodeError, PermissionError, IsADirectoryError, IOError):
            # Any error during reading or parsing means it's not a valid target file.
            return False

    def _process_file(self, json_path):
        """
        Coordinates the processing of a single file event.

        This method includes a debounce timer to prevent duplicate processing
        and a small delay to ensure the file has been completely written to disk
        before attempting to read it.
        """
        now = time.time()
        # Debounce check: if the file was processed very recently, ignore this event.
        if (now - self.last_processed.get(json_path, 0)) < 2:
            return
        
        # A short pause can prevent errors from reading a file that is still being written.
        time.sleep(0.5) 
        
        if self._is_valid_json(json_path):
            print(Fore.CYAN + f"\n[{datetime.now().strftime('%H:%M:%S')}] Detected valid file '{json_path.name}'. Processing...")
            # Call the main processing function from the converter module.
            process_files([json_path], self.output_dir, self.overwrite, self.config, self.lang_templates, self.frontmatter_template)
            # Record the time of processing for the debounce mechanism.
            self.last_processed[json_path] = now

def run_watch_mode(input_dir, output_dir, overwrite, config, lang_templates, frontmatter_template):
    """
    Sets up and runs the application in 'watch' mode.

    This function initializes the file system observer to monitor a directory
    for new or modified JSON files. It performs an initial scan to process any
    existing files before starting the watch.

    Args:
        input_dir (Path): The directory to watch for log files.
        output_dir (Path): The directory where Markdown files will be saved.
        overwrite (bool): Whether to overwrite existing Markdown files.
        config (dict): The main configuration dictionary.
        lang_templates (dict): The dictionary for localized strings.
        frontmatter_template (str): The template for YAML frontmatter.
    """
    print(Style.BRIGHT + f"--- Starting Watch Mode ---")
    
    # It's helpful to process any files that already exist when the mode starts.
    print(Style.BRIGHT + "Performing initial scan of the directory...")
    initial_files = find_json_files(input_dir, recursive=False)
    if initial_files:
        process_files(initial_files, output_dir, overwrite, config, lang_templates, frontmatter_template)
    else:
        print("No initial files to process.")
    
    print(Style.BRIGHT + "\n--- Initial scan complete. Watching for new changes ---")
    # Display the current settings to the user.
    print(f"👀 Watching folder: {Fore.YELLOW}'{input_dir}'")
    print(f"📄 Saving output to: {Fore.YELLOW}'{output_dir}'")
    print(f"🔄 Overwrite existing files: {'Yes' if overwrite else 'No'}")
    print(Fore.CYAN + "\n(Press Ctrl+C to stop watching)")

    # Set up the observer and the event handler.
    event_handler = LogFileEventHandler(output_dir, overwrite, config, lang_templates, frontmatter_template)
    observer = Observer()
    observer.schedule(event_handler, str(input_dir), recursive=False)
    observer.start()
    try:
        # Keep the script running indefinitely to listen for events.
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        # Gracefully shut down the observer on a Ctrl+C command.
        observer.stop()
        print("\n🛑 Watch mode stopped.")
    observer.join()

def run_interactive_mode(config, lang_templates, frontmatter_template):
    """
    Runs the application in a step-by-step interactive command-line mode.

    This function guides the user through a series of prompts to specify the
    input path, output path, and other conversion options, then runs the
    conversion process once.

    Args:
        config (dict): The main configuration dictionary.
        lang_templates (dict): The dictionary for localized strings.
        frontmatter_template (str): The template for YAML frontmatter.
    """
    print(Style.BRIGHT + "--- AI Studio Log Converter (Interactive Mode) ---")
    
    # Prompt the user for the source path, with validation.
    while True:
        src_path_str = input(Fore.CYAN + f"➡️ Enter source path (default: '{DEFAULT_INPUT_DIR}'): " + Style.RESET_ALL).strip() or DEFAULT_INPUT_DIR
        src_path = Path(src_path_str)
        if src_path.exists():
            break
        print(Fore.RED + f"❌ Error: The path '{src_path}' does not exist. Please try again.")

    # Prompt for the remaining options.
    out_path_str = input(Fore.CYAN + f"➡️ Enter output path (default: '{DEFAULT_OUTPUT_DIR}'): " + Style.RESET_ALL).strip() or DEFAULT_OUTPUT_DIR
    output_dir = Path(out_path_str)

    recursive_str = input(Fore.CYAN + "➡️ Search recursively in subfolders? (y/N, default: N): " + Style.RESET_ALL).strip().lower()
    recursive = recursive_str == 'y'

    overwrite_str = input(Fore.CYAN + "➡️ Overwrite existing files? (y/N, default: N): " + Style.RESET_ALL).strip().lower()
    overwrite = overwrite_str == 'y'

    # Find all the files to be processed based on user input.
    files = find_json_files(src_path, recursive)
    if not files:
        print(Fore.YELLOW + f"\n⚠️ No valid JSON files found in '{src_path}'.")
        print(Fore.YELLOW + "Please place your files there and run the program again.")
        return

    # Run the main processing function on the found files.
    process_files(files, output_dir, overwrite, config, lang_templates, frontmatter_template)
