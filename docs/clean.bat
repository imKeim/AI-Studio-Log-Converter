@echo off
echo Cleaning Sphinx documentation build...
python -m sphinx.cmd.build -M clean . _build
echo Documentation clean complete.
pause
