@echo off
setlocal enabledelayedexpansion
REM bootstrap.bat - One-command setup for HoudiniMCP (Windows).
REM
REM Puts uv on the machine, installs the houdinimcp package from GitHub, then
REM hands over to the installer, which does the Houdini plugin and the MCP
REM client configuration.
REM
REM Fresh install:        powershell -c "irm https://raw.githubusercontent.com/rozhabrev/easyhoudini_mcp/main/bootstrap.bat -OutFile bootstrap.bat; .\bootstrap.bat"
REM From inside a clone:  bootstrap.bat          (uses the code in the clone)
REM No questions:         bootstrap.bat --yes
REM Every installer flag is passed through: bootstrap.bat --houdini-version 22.0 --harness codex

echo.
echo === HoudiniMCP bootstrap ===
echo.

where uv >nul 2>&1
if errorlevel 1 (
    echo [..]   Installing uv...
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    set "PATH=%USERPROFILE%\.local\bin;!PATH!"
)
where uv >nul 2>&1
if errorlevel 1 (
    echo [FAIL] uv install failed. https://docs.astral.sh/uv/
    exit /b 1
)
for /f "tokens=*" %%v in ('uv --version') do echo [OK]   %%v

if exist "pyproject.toml" if exist "houdini_mcp_server.py" set "IN_REPO=1"
if defined IN_REPO (
    echo [OK]   Inside the repository - installing from this clone
    uv run python -m bridge.onboarding.install %*
    exit /b !errorlevel!
)

echo [..]   Installing rozhabrev Houdini MCP from GitHub...
uv tool install --force git+https://github.com/rozhabrev/easyhoudini_mcp || exit /b 1
echo [OK]   Installed
houdinimcp-install %*
exit /b !errorlevel!
