@echo off
echo Building the application with PyInstaller...

REM Install dependencies, including PyInstaller
pip install -r requirements.txt

REM Build the .exe file using python -m
REM --- Corrected --add-data paths and added the icon ---
python -m PyInstaller --onefile --windowed --name "AI-Studio-Log-Converter" --icon="logo.ico" --add-data "src/custom_theme.json;." --add-data "logo.ico;." --add-data "logo.png;." "ai-studio-log-converter.pyw"

REM Check if the build was successful
if %errorlevel% neq 0 (
    echo.
    echo PyInstaller failed to build the application.
    pause
    exit /b %errorlevel%
)

echo.
echo Build successful. Cleaning up temporary files...

REM Remove temporary files and folders
rmdir /s /q build
del "*.spec"

echo.
echo Cleanup complete. The executable is in the 'dist' folder.
pause
