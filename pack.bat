@echo off
REM Helm Plugin MCP - Build & Package Script
REM Usage: double-click or run `pack.bat` from project root

cd /d "%~dp0"

echo [1/4] Cleaning previous builds...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
for /d %%i in (*.egg-info) do rmdir /s /q "%%i"

echo [2/4] Building frontend (Vue + Vite)...
cd helm_mcp\frontend
call npm install --ci
if %ERRORLEVEL% neq 0 (
    echo npm install failed!
    pause
    exit /b 1
)
call npm run build
if %ERRORLEVEL% neq 0 (
    echo Frontend build failed!
    pause
    exit /b 1
)
cd /d "%~dp0"

echo [3/4] Building Python package...
python -m build

if %ERRORLEVEL% neq 0 (
    echo Python build failed!
    pause
    exit /b 1
)

echo [4/4] Package ready in dist/
echo.
echo To publish to PyPI, run:
echo   twine upload dist/*
echo.
pause
