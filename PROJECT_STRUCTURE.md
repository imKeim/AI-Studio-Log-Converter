# Project Structure Overview

This document provides a clear overview of the files and directories in the AI Studio Log Converter project. It's designed to help developers and new contributors understand the purpose of each component at a glance.

---

## 📂 Root Directory

-   **`ai-studio-log-converter.pyw`**: The main entry point of the application. This script parses command-line arguments and decides which mode to run (GUI, CLI, Batch, or Watch). The `.pyw` extension ensures that no console window appears when it's run in GUI mode on Windows.

-   **`build.bat`**: A batch script for Windows that automates the process of building the application into a single `.exe` file using PyInstaller. It first installs all necessary dependencies and then runs the build command.

-   **`clean.bat`**: A helper script to remove all generated files and directories, such as build artifacts (`dist`, `build`), log files, and configuration files. This is useful for starting with a clean slate.

-   **`requirements.txt`**: Lists all the Python packages required for the application to run (its runtime dependencies). These can be installed using `pip install -r requirements.txt`.

-   **`requirements-dev.txt`**: Lists additional packages that are only needed for development or building the project, such as `pyinstaller`. This keeps the main dependencies clean.

-   **`README.md`**: The main documentation file for the project. It contains a detailed description, features, usage instructions for both end-users and developers, and build steps.

-   **`PROJECT_STRUCTURE.md`**: This file! A map of the project's structure.

-   **`.gitignore`**: A standard Git file that specifies which files and directories should be ignored by version control (e.g., virtual environments, cache files, build outputs).

-   **`LICENSE`**: Contains the MIT License, which defines the legal terms under which the software can be used, modified, and distributed.

-   **`logo.ico` / `logo.png`**: Image assets used for the application's icon and in the GUI.

---

## 📁 `src/` Directory

This directory contains all the core Python source code, organized into logical modules.

-   **`__init__.py`**: (Implicit) Makes the `src` directory a Python package, allowing for modular imports.

-   **`cli.py`**: Handles all Command-Line Interface (CLI) logic. This includes the interactive mode where the user is prompted for inputs and the "watch" mode that automatically processes files on change.

-   **`config.py`**: Manages all configuration-related tasks. It defines default settings, loads the `config.yaml` file, and creates it with helpful comments if it doesn't exist. It also handles loading language-specific templates.

-   **`converter.py`**: The heart of the application. This module contains the core logic for parsing the input JSON log files, extracting data, handling images, and converting everything into a well-structured Markdown file.

-   **`gui.py`**: Contains all the code for the Graphical User Interface (GUI), which is built using the `customtkinter` library. It defines the window layout, all the widgets (buttons, text boxes), and the functions that handle user interactions.

-   **`custom_theme.json`**: A JSON file that defines the custom color theme for the `customtkinter` GUI, ensuring a consistent and polished look.
