@echo off
echo Building the application with PyInstaller...

REM Установка зависимостей
pip install -r requirements.txt

REM Сборка .exe файла
pyinstaller --onefile --windowed --name "AI-Studio-Log-Converter" "ai-studio-log-converter.pyw"

REM Проверка, была ли сборка успешной
if %errorlevel% neq 0 (
    echo.
    echo PyInstaller failed to build the application.
    pause
    exit /b %errorlevel%
)

echo.
echo Build successful. Cleaning up temporary files...

REM Удаление временных файлов и папок
rmdir /s /q build
del "*.spec"

echo.
echo Cleanup complete. The executable is in the 'dist' folder.
pause
