# src/gui.py

"""
Module for the graphical user interface (GUI).

This file contains all the code related to the CustomTkinter-based GUI.
It defines the layout, widgets, and the functions that handle user interactions
like button clicks and path selections. It also includes the StdoutRedirector
class to display console output within the GUI.
"""

__all__ = ["run_gui_mode", "StdoutRedirector"]

import sys
import re
import customtkinter as ctk
from tkinter import filedialog
from pathlib import Path
import os
from PIL import Image

# Import functions and constants from other modules.
from .converter import find_json_files, process_files
from .config import DEFAULT_INPUT_DIR, DEFAULT_OUTPUT_DIR

class StdoutRedirector:
    """
    Redirects stdout (standard output) to a CustomTkinter Text widget.

    This class is essential for displaying real-time console output, such as
    progress messages and error logs, directly within the application's GUI.
    It implements the `write` and `flush` methods, making it compatible with
    Python's `sys.stdout`.
    """
    def __init__(self, text_widget):
        """Initializes the redirector with the target text widget."""
        self.text_space = text_widget
        # Compiles a regular expression to remove ANSI escape codes (used for color
        # in terminals) to ensure the text in the GUI is clean.
        self.ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        self.line_buffer = ""

    def write(self, string):
        """
        Writes a string to the text widget.

        This method cleans the string of any ANSI codes, buffers the output,
        and inserts it line by line into the text widget to ensure smooth updates.
        """
        cleaned_string = self.ansi_escape.sub('', string)
        self.line_buffer += cleaned_string
        
        # Process the buffer line by line.
        while '\n' in self.line_buffer:
            line, self.line_buffer = self.line_buffer.split('\n', 1)
            self.text_space.configure(state='normal') # Enable writing to the widget
            self.text_space.insert('end', line + '\n', "indent")
            self.text_space.see('end') # Scroll to the end to show the latest output
            self.text_space.configure(state='disabled') # Disable writing to prevent user edits

    def flush(self):
        """
        Ensures any remaining buffered output is written to the widget.

        This method is called automatically by the system at certain times,
        such as when the program exits, to make sure no output is lost.
        """
        if self.line_buffer:
            self.text_space.configure(state='normal')
            self.text_space.insert('end', self.line_buffer + '\n', "indent")
            self.text_space.see('end')
            self.text_space.configure(state='disabled')
            self.line_buffer = ""

def run_gui_mode(config, lang_templates, frontmatter_template, resource_path):
    """
    Initializes and runs the main application GUI.

    This function sets up the main window, defines the layout and widgets,
    and connects user actions (like button clicks) to the underlying
    conversion logic.

    Args:
        config (dict): The main configuration dictionary.
        lang_templates (dict): The dictionary for localized strings.
        frontmatter_template (str): The template for YAML frontmatter.
        resource_path (function): A helper function (from the main .pyw file)
                                  to get the absolute path to bundled resources.
    """
    # --- Window Setup ---
    ctk.set_appearance_mode("Dark")
    
    # Load the custom color theme.
    theme_path = resource_path("custom_theme.json")
    ctk.set_default_color_theme(theme_path)

    app = ctk.CTk()
    app.title("AI Studio Log Converter")
    
    # Set the application icon.
    icon_path = resource_path("logo.ico")
    if os.path.exists(icon_path):
        app.iconbitmap(icon_path)
    app.geometry("800x600")
    app.minsize(800, 600)

    # --- GUI Helper Functions (defined inside the main function to have access to app variables) ---

    def select_input_path():
        """Callback for the 'Browse...' button for the source path."""
        path = filedialog.askdirectory(initialdir=DEFAULT_INPUT_DIR)
        if path:
            input_path_entry.delete(0, 'end')
            input_path_entry.insert(0, path)

    def select_output_path():
        """Callback for the 'Browse...' button for the output path."""
        path = filedialog.askdirectory(initialdir=DEFAULT_OUTPUT_DIR)
        if path:
            output_path_entry.delete(0, 'end')
            output_path_entry.insert(0, path)

    def start_conversion():
        """
        The main callback for the 'Start Conversion' button.

        This function gathers all settings from the GUI widgets, validates them,
        and then calls the appropriate processing functions from the converter module.
        """
        # Disable the button to prevent multiple clicks and clear the log.
        start_button.configure(state="disabled")
        log_textbox.configure(state='normal')
        log_textbox.delete("1.0", "end")
        log_textbox.configure(state='disabled')

        # Get all settings from the GUI elements.
        input_path_str = input_path_entry.get() or DEFAULT_INPUT_DIR
        output_path_str = output_path_entry.get() or DEFAULT_OUTPUT_DIR
        
        input_path = Path(input_path_str)
        output_dir = Path(output_path_str)
        
        recursive = recursive_var.get()
        overwrite = overwrite_var.get()
        watch_mode = watch_var.get()

        # Basic validation for the input path.
        if not input_path.exists():
            print(f"❌ Error: The specified path does not exist: '{input_path}'")
            start_button.configure(state="normal")
            return

        try:
            # Handle watch mode separately.
            if watch_mode:
                # A proper GUI implementation of a long-running task like watch mode
                # would require threading to prevent the UI from freezing.
                # As a simpler solution, we guide the user to use the CLI for this feature.
                if not input_path.is_dir():
                    print("Error: In watch mode, the source path must be a directory.")
                else:
                    print("Watch mode is best run from the command line.")
                    print(f"python ai-studio-log-converter.pyw \"{input_path}\" --watch")
            else:
                # For a standard one-off conversion:
                files = find_json_files(input_path, recursive)
                if not files:
                    print(f"\n⚠️ No valid JSON files found in '{input_path}'.")
                else:
                    # Trigger the main file processing logic.
                    process_files(files, output_dir, overwrite, config, lang_templates, frontmatter_template)
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
        finally:
            # Re-enable the start button after the process is complete or an error occurs.
            if not watch_mode:
                print("\nDone! You can start a new conversion or close the program.")
            start_button.configure(state="normal")

    # --- GUI Layout ---
    # The main layout is managed by a grid system, which allows for flexible resizing.
    app.grid_columnconfigure(1, weight=1) # Allow the second column to expand

    # --- Header Frame (for logo and title) ---
    header_frame = ctk.CTkFrame(app, fg_color="transparent")
    header_frame.grid(row=0, column=0, columnspan=2, padx=20, pady=(10, 0), sticky="ew")
    header_frame.grid_columnconfigure(1, weight=1)

    # Application Logo
    logo_path = resource_path("logo.png")
    if os.path.exists(logo_path):
        logo_image = ctk.CTkImage(Image.open(logo_path), size=(48, 48))
        logo_label = ctk.CTkLabel(header_frame, image=logo_image, text="")
        logo_label.grid(row=0, column=0, padx=(10, 10), pady=10, sticky="w")

    # Application Title
    title_label = ctk.CTkLabel(header_frame, text="Google AI Studio Log Converter", font=ctk.CTkFont(size=20, weight="bold"))
    title_label.grid(row=0, column=1, padx=10, pady=10, sticky="w")

    # --- Settings Frame (for input/output paths and options) ---
    settings_frame = ctk.CTkFrame(app)
    settings_frame.grid(row=1, column=0, columnspan=2, padx=20, pady=10, sticky="ew")
    settings_frame.grid_columnconfigure(1, weight=1)

    # Input Path Selection
    input_path_label = ctk.CTkLabel(settings_frame, text="Source Path:")
    input_path_label.grid(row=0, column=0, padx=10, pady=10, sticky="w")
    input_path_entry = ctk.CTkEntry(settings_frame, placeholder_text=DEFAULT_INPUT_DIR)
    input_path_entry.insert(0, DEFAULT_INPUT_DIR)
    input_path_entry.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
    input_browse_button = ctk.CTkButton(settings_frame, text="Browse...", command=select_input_path, width=100)
    input_browse_button.grid(row=0, column=2, padx=10, pady=10)

    # Output Path Selection
    output_path_label = ctk.CTkLabel(settings_frame, text="Output Path:")
    output_path_label.grid(row=1, column=0, padx=10, pady=10, sticky="w")
    output_path_entry = ctk.CTkEntry(settings_frame, placeholder_text=DEFAULT_OUTPUT_DIR)
    output_path_entry.insert(0, DEFAULT_OUTPUT_DIR)
    output_path_entry.grid(row=1, column=1, padx=10, pady=10, sticky="ew")
    output_browse_button = ctk.CTkButton(settings_frame, text="Browse...", command=select_output_path, width=100)
    output_browse_button.grid(row=1, column=2, padx=10, pady=10)

    # --- Checkbox Options ---
    checkbox_frame = ctk.CTkFrame(settings_frame, fg_color="transparent", border_width=0)
    checkbox_frame.grid(row=2, column=0, columnspan=3, padx=10, pady=10, sticky="w")
    
    recursive_var = ctk.BooleanVar()
    recursive_checkbox = ctk.CTkCheckBox(checkbox_frame, text="Search Recursively", variable=recursive_var)
    recursive_checkbox.pack(side="left", padx=5)

    overwrite_var = ctk.BooleanVar()
    overwrite_checkbox = ctk.CTkCheckBox(checkbox_frame, text="Overwrite Existing", variable=overwrite_var)
    overwrite_checkbox.pack(side="left", padx=5)

    watch_var = ctk.BooleanVar()
    watch_checkbox = ctk.CTkCheckBox(checkbox_frame, text="Watch Mode", variable=watch_var)
    watch_checkbox.pack(side="left", padx=5)

    # --- Main Action Button ---
    start_button = ctk.CTkButton(app, text="Start Conversion", command=start_conversion, height=40)
    start_button.grid(row=2, column=0, columnspan=2, padx=20, pady=20, sticky="ew")

    # --- Log Output Textbox ---
    log_textbox = ctk.CTkTextbox(app, height=150, state='disabled', font=ctk.CTkFont(family="Courier New", size=12), wrap="word")
    log_textbox.grid(row=3, column=0, columnspan=2, padx=20, pady=(0, 20), sticky="nsew")
    log_textbox.tag_config("indent", lmargin1=10) # Add a left margin for readability.
    app.grid_rowconfigure(3, weight=1) # Allow the log area to expand vertically.

    # --- Final Setup ---
    # Redirect all print statements to our custom redirector to display them in the GUI.
    sys.stdout = StdoutRedirector(log_textbox)

    # Start the CustomTkinter main event loop.
    app.mainloop()
