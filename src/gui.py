# src/gui.py

"""
Module for the graphical user interface (GUI).

This file contains all the code related to the CustomTkinter-based GUI.
It defines the layout, widgets, and the functions that handle user interactions
like button clicks and path selections. It also includes the StdoutRedirector
class to display console output within the GUI.
"""

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
    A class to redirect stdout to a tkinter Text widget.
    This allows the user to see log messages and progress directly in the GUI.
    """
    def __init__(self, text_widget):
        self.text_space = text_widget
        # Regex to strip ANSI color codes for clean logging in the GUI.
        self.ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        self.line_buffer = ""

    def write(self, string):
        """
        Writes a string to the text widget, cleaning it and handling line breaks.
        """
        cleaned_string = self.ansi_escape.sub('', string)
        self.line_buffer += cleaned_string
        
        while '\n' in self.line_buffer:
            line, self.line_buffer = self.line_buffer.split('\n', 1)
            self.text_space.configure(state='normal')
            # Insert each line with an "indent" tag to add a left margin.
            self.text_space.insert('end', line + '\n', "indent")
            self.text_space.see('end')
            self.text_space.configure(state='disabled')

    def flush(self):
        """
        Flushes any remaining content in the buffer to the text widget.
        This is important for ensuring the last lines of output are displayed.
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
    """
    # Set the appearance mode and load the custom theme
    ctk.set_appearance_mode("Dark")
    
    # --- ИСПРАВЛЕНО: Используем resource_path для поиска темы ---
    theme_path = resource_path("custom_theme.json")
    ctk.set_default_color_theme(theme_path)

    app = ctk.CTk()
    app.title("AI Studio Log Converter")
    
    # --- ИСПРАВЛЕНО: Используем resource_path для поиска иконки ---
    icon_path = resource_path("logo.ico")
    if os.path.exists(icon_path):
        app.iconbitmap(icon_path)
    app.geometry("800x600")
    app.minsize(800, 600)

    # --- GUI Helper Functions ---

    def select_input_path():
        """Opens a dialog to select the source directory."""
        path = filedialog.askdirectory(initialdir=DEFAULT_INPUT_DIR)
        if path:
            input_path_entry.delete(0, 'end')
            input_path_entry.insert(0, path)

    def select_output_path():
        """Opens a dialog to select the output directory."""
        path = filedialog.askdirectory(initialdir=DEFAULT_OUTPUT_DIR)
        if path:
            output_path_entry.delete(0, 'end')
            output_path_entry.insert(0, path)

    def start_conversion():
        """
        The main function called when the 'Start Conversion' button is clicked.
        It gathers settings from the GUI and runs the conversion process.
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

        if not input_path.exists():
            print(f"❌ Error: The specified path does not exist: '{input_path}'")
            start_button.configure(state="normal")
            return

        try:
            if watch_mode:
                # Watch mode is a blocking, long-running process.
                # A full implementation in a GUI would require threading to not freeze the UI.
                # For now, we inform the user to run it from the CLI.
                if not input_path.is_dir():
                    print("Error: In watch mode, the source path must be a directory.")
                else:
                    print("Watch mode is best run from the command line.")
                    print(f"python ai-studio-log-converter.pyw \"{input_path}\" --watch")
            else:
                files = find_json_files(input_path, recursive)
                if not files:
                    print(f"\n⚠️ No valid JSON files found in '{input_path}'.")
                else:
                    process_files(files, output_dir, overwrite, config, lang_templates, frontmatter_template)
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
        finally:
            if not watch_mode:
                print("\nDone! You can start a new conversion or close the program.")
            start_button.configure(state="normal")

    # --- GUI Layout ---
    # The layout is defined using a grid system for flexibility.
    app.grid_columnconfigure(1, weight=1)

    # --- Frame for logo and title ---
    header_frame = ctk.CTkFrame(app, fg_color="transparent")
    header_frame.grid(row=0, column=0, columnspan=2, padx=20, pady=(10, 0), sticky="ew")
    header_frame.grid_columnconfigure(1, weight=1)

    # --- Logo ---
    logo_path = resource_path("logo.png")
    if os.path.exists(logo_path):
        logo_image = ctk.CTkImage(Image.open(logo_path), size=(48, 48))
        logo_label = ctk.CTkLabel(header_frame, image=logo_image, text="")
        logo_label.grid(row=0, column=0, padx=(10, 10), pady=10, sticky="w")

    title_label = ctk.CTkLabel(header_frame, text="Google AI Studio Log Converter", font=ctk.CTkFont(size=20, weight="bold"))
    title_label.grid(row=0, column=1, padx=10, pady=10, sticky="w")

    # --- Frame for settings ---
    settings_frame = ctk.CTkFrame(app)
    settings_frame.grid(row=1, column=0, columnspan=2, padx=20, pady=10, sticky="ew")
    settings_frame.grid_columnconfigure(1, weight=1)

    # Input Path
    input_path_label = ctk.CTkLabel(settings_frame, text="Source Path:")
    input_path_label.grid(row=0, column=0, padx=10, pady=10, sticky="w")
    input_path_entry = ctk.CTkEntry(settings_frame, placeholder_text=DEFAULT_INPUT_DIR)
    input_path_entry.insert(0, DEFAULT_INPUT_DIR)
    input_path_entry.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
    input_browse_button = ctk.CTkButton(settings_frame, text="Browse...", command=select_input_path, width=100)
    input_browse_button.grid(row=0, column=2, padx=10, pady=10)

    # Output Path
    output_path_label = ctk.CTkLabel(settings_frame, text="Output Path:")
    output_path_label.grid(row=1, column=0, padx=10, pady=10, sticky="w")
    output_path_entry = ctk.CTkEntry(settings_frame, placeholder_text=DEFAULT_OUTPUT_DIR)
    output_path_entry.insert(0, DEFAULT_OUTPUT_DIR)
    output_path_entry.grid(row=1, column=1, padx=10, pady=10, sticky="ew")
    output_browse_button = ctk.CTkButton(settings_frame, text="Browse...", command=select_output_path, width=100)
    output_browse_button.grid(row=1, column=2, padx=10, pady=10)

    # Checkboxes
    # --- ИСПРАВЛЕНО: Добавлен border_width=0 для удаления "призрачной" рамки ---
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

    # --- Start Button ---
    start_button = ctk.CTkButton(app, text="Start Conversion", command=start_conversion, height=40)
    start_button.grid(row=2, column=0, columnspan=2, padx=20, pady=20, sticky="ew")

    # --- Log Textbox ---
    log_textbox = ctk.CTkTextbox(app, height=150, state='disabled', font=ctk.CTkFont(family="Courier New", size=12), wrap="word")
    log_textbox.grid(row=3, column=0, columnspan=2, padx=20, pady=(0, 20), sticky="nsew")
    log_textbox.tag_config("indent", lmargin1=10) # Add left margin to each line
    app.grid_rowconfigure(3, weight=1)

    # Redirect stdout to the custom redirector class.
    sys.stdout = StdoutRedirector(log_textbox)

    # Start the main GUI loop.
    app.mainloop()
