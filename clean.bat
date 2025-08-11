@echo off
echo Cleaning up generated files and directories...

REM Удаление папки dist
if exist "dist" (
    echo Deleting 'dist' directory...
    rmdir /s /q dist
)

REM Удаление логов и конфигурационных файлов
if exist "config.yaml" (
    echo Deleting 'config.yaml'...
    del "config.yaml"
)

if exist "crash_log.txt" (
    echo Deleting 'crash_log.txt'...
    del "crash_log.txt"
)

if exist "frontmatter_template_en.txt" (
    echo Deleting 'frontmatter_template_en.txt'...
    del "frontmatter_template_en.txt"
)

if exist "frontmatter_template_ru.txt" (
    echo Deleting 'frontmatter_template_ru.txt'...
    del "frontmatter_template_ru.txt"
)

echo.
echo Cleanup complete.
pause
