@echo off
echo Building Sphinx documentation...
python -m sphinx.cmd.build -b html . _build
echo Documentation build complete.
pause
