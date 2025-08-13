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
import threading

# Import functions and constants from other modules.
from .converter import find_json_files, process_files
from .config import DEFAULT_INPUT_DIR, DEFAULT_OUTPUT_DIR

class StdoutRedirector:
    """
    Redirects stdout (standard output) to a CustomTkinter Text widget.

    This class is essential for displaying real-time console output, such as
    progress messages and error logs, directly within the application's GUI.
    It implements the `write` and `flush` methods, making it compatible with
    Python's `sys.stdout`. It is designed to be thread-safe.
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
        Writes a string to the text widget in a thread-safe manner.

        This method cleans the string of any ANSI codes, buffers the output,
        and schedules the GUI update on the main thread using `app.after`.
        """
        cleaned_string = self.ansi_escape.sub('', string)
        self.line_buffer += cleaned_string
        
        while '\n' in self.line_buffer:
            line, self.line_buffer = self.line_buffer.split('\n', 1)
            # Schedule the text insertion on the main Tkinter thread.
            self.text_space.master.after(0, self._insert_text, line + '\n')

    def flush(self):
        """
        Ensures any remaining buffered output is written to the widget.
        This is also thread-safe.
        """
        if self.line_buffer:
            # Schedule the final buffer flush on the main Tkinter thread.
            self.text_space.master.after(0, self._insert_text, self.line_buffer + '\n')
            self.line_buffer = ""

    def _insert_text(self, text_to_insert):
        """Helper method to perform the actual GUI update on the main thread."""
        self.text_space.configure(state='normal') # Enable writing to the widget
        self.text_space.insert('end', text_to_insert, "indent")
        self.text_space.see('end') # Scroll to the end to show the latest output
        self.text_space.configure(state='disabled') # Disable writing to prevent user edits


def run_gui_mode(config, lang_templates, frontmatter_template, resource_path):
    """
    Initializes and runs the main application GUI.

    This function sets up the main window, defines the layout and widgets,
    and connects user actions (like button clicks) to the underlying
    conversion logic, which is run in a separate thread to prevent freezing.
    """
    # --- Window Setup ---
    ctk.set_appearance_mode("Dark")
    
    theme_path = resource_path("custom_theme.json")
    ctk.set_default_color_theme(theme_path)

    app = ctk.CTk()
    app.title("AI Studio Log Converter")
    
    icon_path = resource_path("logo.ico")
    if os.path.exists(icon_path):
        app.iconbitmap(icon_path)
    app.geometry("900x600")
    app.minsize(900, 600)

    # --- GUI Helper Functions ---

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

    def conversion_worker(input_path, output_dir, recursive, overwrite, watch_mode, fast_mode):
        """
        This function contains the long-running logic and is executed in a background thread.
        """
        try:
            if not input_path.exists():
                print(f"❌ Error: The specified path does not exist: '{input_path}'")
                return

            if watch_mode:
                if not input_path.is_dir():
                    print("Error: In watch mode, the source path must be a directory.")
                else:
                    print("Watch mode is best run from the command line.")
                    print(f"python ai-studio-log-converter.pyw \"{input_path}\" --watch")
            else:
                # This is the long-running part: finding and processing files.
                files = find_json_files(input_path, recursive, fast_mode)
                if not files:
                    print(f"\n⚠️ No valid JSON files found in '{input_path}'.")
                else:
                    process_files(files, output_dir, overwrite, config, lang_templates, frontmatter_template, fast_mode=fast_mode)
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
        finally:
            # When the work is done, re-enable the button on the main thread.
            if not watch_mode:
                print("\nDone! You can start a new conversion or close the program.")
            app.after(0, lambda: start_button.configure(state="normal"))

    def start_conversion():
        """
        The main callback for the 'Start Conversion' button.
        This function now only gathers settings and starts the background worker thread.
        """
        start_button.configure(state="disabled")
        log_textbox.configure(state='normal')
        log_textbox.delete("1.0", "end")
        log_textbox.configure(state='disabled')

        input_path_str = input_path_entry.get() or DEFAULT_INPUT_DIR
        output_path_str = output_path_entry.get() or DEFAULT_OUTPUT_DIR
        
        input_path = Path(input_path_str)
        output_dir = Path(output_path_str)
        
        recursive = recursive_var.get()
        overwrite = overwrite_var.get()
        watch_mode = watch_var.get()
        fast_mode = fast_mode_var.get()
        
        # We temporarily update the config dict with the user's choice from the GUI.
        # This ensures the user's selection is respected for the current run.
        config['enable_gdrive_indicator'] = gdrive_indicator_var.get()

        # Create and start the background thread to do the heavy lifting.
        worker_thread = threading.Thread(
            target=conversion_worker,
            args=(input_path, output_dir, recursive, overwrite, watch_mode, fast_mode)
        )
        worker_thread.daemon = True  # Allows the app to exit even if the thread is running.
        worker_thread.start()

    def toggle_gdrive_indicator_visibility():
        """Shows or hides the GDrive attachment indicator checkbox based on Fast Mode state."""
        if fast_mode_var.get():
            # If Fast Mode is enabled, hide the checkbox
            gdrive_indicator_checkbox.pack_forget()
        else:
            # If Fast Mode is disabled, show the checkbox
            gdrive_indicator_checkbox.pack(side="left", padx=5)

    # --- GUI Layout ---
    app.grid_columnconfigure(1, weight=1)

    # --- Header Frame (for logo and title) ---
    header_frame = ctk.CTkFrame(app, fg_color="transparent")
    header_frame.grid(row=0, column=0, columnspan=2, padx=20, pady=(10, 0), sticky="ew")
    header_frame.grid_columnconfigure(1, weight=1)

    logo_path = resource_path("logo.png")
    if os.path.exists(logo_path):
        logo_image = ctk.CTkImage(Image.open(logo_path), size=(48, 48))
        logo_label = ctk.CTkLabel(header_frame, image=logo_image, text="")
        logo_label.grid(row=0, column=0, padx=(10, 10), pady=10, sticky="w")

    title_label = ctk.CTkLabel(header_frame, text="AI Studio Log Converter", font=ctk.CTkFont(size=20, weight="bold"))
    title_label.grid(row=0, column=1, padx=10, pady=10, sticky="w")

    # --- Settings Frame (for input/output paths and options) ---
    settings_frame = ctk.CTkFrame(app)
    settings_frame.grid(row=1, column=0, columnspan=2, padx=20, pady=10, sticky="ew")
    settings_frame.grid_columnconfigure(1, weight=1)

    input_path_label = ctk.CTkLabel(settings_frame, text="Source Path:")
    input_path_label.grid(row=0, column=0, padx=10, pady=10, sticky="w")
    input_path_entry = ctk.CTkEntry(settings_frame, placeholder_text=DEFAULT_INPUT_DIR)
    input_path_entry.insert(0, DEFAULT_INPUT_DIR)
    input_path_entry.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
    input_browse_button = ctk.CTkButton(settings_frame, text="Browse...", command=select_input_path, width=100)
    input_browse_button.grid(row=0, column=2, padx=10, pady=10)

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
    
    fast_mode_var = ctk.BooleanVar(value=True)
    fast_mode_checkbox = ctk.CTkCheckBox(checkbox_frame, text="Fast Mode (no extension)", variable=fast_mode_var, command=toggle_gdrive_indicator_visibility)
    fast_mode_checkbox.pack(side="left", padx=5)

    recursive_var = ctk.BooleanVar()
    recursive_checkbox = ctk.CTkCheckBox(checkbox_frame, text="Search Recursively", variable=recursive_var)
    recursive_checkbox.pack(side="left", padx=5)

    overwrite_var = ctk.BooleanVar()
    overwrite_checkbox = ctk.CTkCheckBox(checkbox_frame, text="Overwrite Existing", variable=overwrite_var)
    overwrite_checkbox.pack(side="left", padx=5)

    watch_var = ctk.BooleanVar()
    watch_checkbox = ctk.CTkCheckBox(checkbox_frame, text="Watch Mode", variable=watch_var)
    watch_checkbox.pack(side="left", padx=5)

    # This checkbox is for the GDrive attachment indicator.
    # Its visibility is controlled by the toggle_gdrive_indicator_visibility function.
    gdrive_indicator_var = ctk.BooleanVar(value=config.get('enable_gdrive_indicator', True))
    gdrive_indicator_checkbox = ctk.CTkCheckBox(checkbox_frame, text="Add GDrive Attachment Indicator", variable=gdrive_indicator_var)
    # The checkbox is not packed here initially; the toggle function will handle it.

    # --- Main Action Button ---
    start_button = ctk.CTkButton(app, text="Start Conversion", command=start_conversion, height=40)
    start_button.grid(row=2, column=0, columnspan=2, padx=20, pady=20, sticky="ew")

    # --- Log Output Textbox ---
    log_textbox = ctk.CTkTextbox(app, height=150, state='disabled', font=ctk.CTkFont(family="Courier New", size=12), wrap="word")
    log_textbox.grid(row=3, column=0, columnspan=2, padx=20, pady=(0, 20), sticky="nsew")
    log_textbox.tag_config("indent", lmargin1=10)
    app.grid_rowconfigure(3, weight=1)

    # --- Final Setup ---
    sys.stdout = StdoutRedirector(log_textbox)

    # Call the function on startup to set the initial correct state of the GUI.
    toggle_gdrive_indicator_visibility()

    app.mainloop()