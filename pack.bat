@echo off
REM Helm Plugin MCP - Build & Package Script
REM Usage: double-click or run `pack.bat` from project root

cd /d "%~dp0"

echo [1/3] Cleaning previous builds...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
if exist *.egg-info rmdir /s /q *.egg-info

echo [2/3] Building package...
python -m build

if %ERRORLEVEL% neq 0 (
    echo Build failed!
    pause
    exit /b 1
)

echo [3/3] Package ready in dist/
echo.
echo To publish to PyPI, run:
echo   twine upload dist/*
echo.
pause