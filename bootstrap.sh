#!/usr/bin/env bash
# bootstrap.sh — One-command setup for HoudiniMCP (Linux + macOS).
#
# Puts uv on the machine, installs the houdinimcp package from PyPI, then hands
# over to the installer, which does the Houdini plugin and the MCP client
# configuration.
#
# Fresh install:        curl -sSL https://raw.githubusercontent.com/rozhabrev/<REPO>/main/bootstrap.sh | bash
# From inside a clone:  bash bootstrap.sh          (uses the code in the clone)
# No questions:         bash bootstrap.sh --yes
# Every installer flag is passed through: bash bootstrap.sh --houdini-version 22.0 --harness codex
set -euo pipefail

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[0;33m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
ok()   { echo -e "${GREEN}[OK]${NC}   $1"; }
fail() { echo -e "${RED}[FAIL]${NC} $1"; }
warn() { echo -e "${YELLOW}[!!]${NC}   $1"; }
step() { echo -e "${CYAN}[..]${NC}   $1"; }

echo -e "\n${BOLD}=== HoudiniMCP bootstrap ===${NC}\n"

# Houdini sets PYTHONHOME/PYTHONPATH, which breaks every other Python process.
unset PYTHONHOME PYTHONPATH

if ! command -v uv >/dev/null; then
    step "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi
command -v uv >/dev/null || { fail "uv install failed. https://docs.astral.sh/uv/"; exit 1; }
ok "$(uv --version)"

if [ -f "pyproject.toml" ] && [ -f "houdini_mcp_server.py" ]; then
    ok "Inside the repository — installing from this clone"
    uv run python -m bridge.onboarding.install "$@"
else
    step "Installing rozhabrev Houdini MCP from GitHub..."
    uv tool install --force git+https://github.com/rozhabrev/<REPO>
    ok "Installed"
    houdinimcp-install "$@"
fi
