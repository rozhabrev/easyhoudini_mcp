"""Detect the agent harnesses on this machine and register the bridge with them.

Every harness runs the same command and differs only in where that command is
written. The command is `houdinimcp-bridge` from an installed package, and
`uv --directory <repo> run --frozen python houdini_mcp_server.py` from a
checkout. `--frozen` is not an option: without it `uv run` resolves and syncs
before every start, so one dependency that no index can serve takes a working
setup away in the middle of a session.
"""
import json
import os
import platform
import re
import shutil
import subprocess
import sys

SERVER_NAME = "houdini"


def server_command(repo_dir: str = None) -> dict:
    """The command a harness runs to start the bridge.

    repo_dir names a checkout. Without one the bridge came from a package, and
    the console script that pip or uv put on the path starts it.
    """
    if repo_dir:
        return {
            "command": "uv",
            # --frozen: start with the lock that is in the checkout. Without
            # it, uv resolves first, and a dependency that no index has stops
            # a bridge that worked a minute ago.
            "args": ["--directory", repo_dir, "run", "--frozen", "python",
                     "houdini_mcp_server.py"],
        }
    return {"command": _bridge_script(), "args": []}


def _bridge_script() -> str:
    """The path of the houdinimcp-bridge console script.

    A harness starts the bridge with its own environment, so the name alone is
    not enough: it must be the full path of the script that belongs to the
    Python that runs this installer.
    """
    name = "houdinimcp-bridge.exe" if os.name == "nt" else "houdinimcp-bridge"
    for folder in (os.path.dirname(sys.executable),
                   os.path.join(os.path.dirname(sys.executable), "Scripts"),
                   os.path.join(sys.prefix, "bin")):
        candidate = os.path.join(folder, name)
        if os.path.isfile(candidate):
            return candidate
    return shutil.which("houdinimcp-bridge") or "houdinimcp-bridge"


def server_command_text(repo_dir: str = None) -> str:
    command = server_command(repo_dir)
    return " ".join([command["command"], *command["args"]])


def _home(*parts) -> str:
    return os.path.join(os.path.expanduser("~"), *parts)


def _write_json_server(path: str, repo_dir: str, dry_run: bool, key: str = "mcpServers") -> str:
    """Merge the server into a JSON config, keeping everything else in it."""
    config = {}
    if os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as handle:
                config = json.load(handle)
        except json.JSONDecodeError as error:
            raise RuntimeError(f"{path} is not valid JSON: {error}")
    config.setdefault(key, {})[SERVER_NAME] = server_command(repo_dir)
    if not dry_run:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(config, handle, indent=2)
            handle.write("\n")
    return path


# ── Claude Code ──

def _claude_code_detect() -> bool:
    return bool(shutil.which("claude")) or os.path.isdir(_home(".claude"))


def _claude_code_configure(repo_dir: str, dry_run: bool) -> str:
    if not shutil.which("claude"):
        return _write_json_server(_home(".claude.json"), repo_dir, dry_run)
    if dry_run:
        return "claude mcp add --scope user"
    subprocess.run(["claude", "mcp", "remove", "--scope", "user", SERVER_NAME],
                   capture_output=True, check=False)
    command = server_command(repo_dir)
    result = subprocess.run(
        ["claude", "mcp", "add", "--transport", "stdio", "--scope", "user", SERVER_NAME,
         "--", command["command"], *command["args"]],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "claude mcp add failed")
    return "claude mcp list"


# ── Claude Desktop ──

def _claude_desktop_config() -> str:
    system = platform.system()
    if system == "Windows":
        return os.path.join(os.environ.get("APPDATA", _home("AppData", "Roaming")),
                            "Claude", "claude_desktop_config.json")
    if system == "Darwin":
        return _home("Library", "Application Support", "Claude", "claude_desktop_config.json")
    return _home(".config", "Claude", "claude_desktop_config.json")


def _claude_desktop_detect() -> bool:
    if os.path.isdir(os.path.dirname(_claude_desktop_config())):
        return True
    system = platform.system()
    if system == "Darwin":
        return os.path.isdir("/Applications/Claude.app")
    if system == "Windows":
        return os.path.isdir(os.path.join(os.environ.get("LOCALAPPDATA", ""), "AnthropicClaude"))
    return bool(shutil.which("claude-desktop"))


def _claude_desktop_configure(repo_dir: str, dry_run: bool) -> str:
    return _write_json_server(_claude_desktop_config(), repo_dir, dry_run)


# ── Codex ──

def _codex_detect() -> bool:
    return bool(shutil.which("codex")) or os.path.isdir(_home(".codex"))


def _codex_configure(repo_dir: str, dry_run: bool) -> str:
    path = _home(".codex", "config.toml")
    text = ""
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
    # Drop any previous block for this server, up to the next table header.
    text = re.sub(
        rf"(?ms)^\[mcp_servers\.{SERVER_NAME}\].*?(?=^\[|\Z)", "", text
    ).rstrip()
    command = server_command(repo_dir)
    block = (
        f"[mcp_servers.{SERVER_NAME}]\n"
        # JSON string syntax is valid TOML basic-string syntax: backslashes in Windows paths come out escaped
        # (a bare "C:\Users\..." is an invalid escape and Codex / ChatGPT desktop refuse to start)
        f"command = {json.dumps(command['command'], ensure_ascii=False)}\n"
        f"args = {json.dumps(command['args'], ensure_ascii=False)}\n"
    )
    if not dry_run:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(f"{text}\n\n{block}" if text else block)
    return path


# ── Gemini CLI ──

def _gemini_detect() -> bool:
    return bool(shutil.which("gemini")) or os.path.isdir(_home(".gemini"))


def _gemini_configure(repo_dir: str, dry_run: bool) -> str:
    return _write_json_server(_home(".gemini", "settings.json"), repo_dir, dry_run)


# ── Cursor ──

def _cursor_detect() -> bool:
    return os.path.isdir(_home(".cursor"))


def _cursor_configure(repo_dir: str, dry_run: bool) -> str:
    return _write_json_server(_home(".cursor", "mcp.json"), repo_dir, dry_run)


# ── opencode ──

def _opencode_dir() -> str:
    return os.path.join(os.environ.get("XDG_CONFIG_HOME") or _home(".config"), "opencode")


def _opencode_detect() -> bool:
    return bool(shutil.which("opencode")) or os.path.isdir(_opencode_dir())


def _opencode_configure(repo_dir: str, dry_run: bool) -> str:
    # The global config has three accepted names. Use the one that exists.
    names = ("opencode.json", "opencode.jsonc", "config.json")
    path = next((os.path.join(_opencode_dir(), name) for name in names
                 if os.path.isfile(os.path.join(_opencode_dir(), name))),
                os.path.join(_opencode_dir(), names[0]))
    config = {}
    if os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as handle:
                config = json.load(handle)
        except json.JSONDecodeError as error:
            raise RuntimeError(f"{path} is not plain JSON ({error}). Add the server by hand: "
                               f"mcp.{SERVER_NAME} = {_opencode_server(repo_dir)}")
    config.setdefault("$schema", "https://opencode.ai/config.json")
    config.setdefault("mcp", {})[SERVER_NAME] = _opencode_server(repo_dir)
    if not dry_run:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(config, handle, indent=2)
            handle.write("\n")
    return path


def _opencode_server(repo_dir: str) -> dict:
    command = server_command(repo_dir)
    return {"type": "local", "command": [command["command"], *command["args"]], "enabled": True}


# ── pi ──

def _pi_dir() -> str:
    return os.environ.get("PI_CODING_AGENT_DIR") or _home(".pi", "agent")


def _pi_detect() -> bool:
    return bool(shutil.which("pi")) or os.path.isdir(_pi_dir())


def _pi_configure(repo_dir: str, dry_run: bool) -> str:
    # pi has no MCP of its own. The pi-mcp-adapter extension reads this file.
    path = _write_json_server(os.path.join(_pi_dir(), "mcp.json"), repo_dir, dry_run)
    return f"{path} (pi reads it through pi-mcp-adapter: pi install npm:pi-mcp-adapter)"


class Harness:
    def __init__(self, key, label, detect, configure):
        self.key = key
        self.label = label
        self.detect = detect
        self.configure = configure

    @property
    def installed(self) -> bool:
        return bool(self.detect())


HARNESSES = [
    Harness("claude-code", "Claude Code (CLI)", _claude_code_detect, _claude_code_configure),
    Harness("claude-desktop", "Claude Desktop", _claude_desktop_detect, _claude_desktop_configure),
    Harness("codex", "OpenAI Codex", _codex_detect, _codex_configure),
    Harness("gemini-cli", "Gemini CLI", _gemini_detect, _gemini_configure),
    Harness("cursor", "Cursor", _cursor_detect, _cursor_configure),
    Harness("opencode", "opencode", _opencode_detect, _opencode_configure),
    Harness("pi", "pi", _pi_detect, _pi_configure),
]

BY_KEY = {harness.key: harness for harness in HARNESSES}


def detected() -> list:
    return [harness for harness in HARNESSES if harness.installed]


# ── Claude Code tool permissions ──

CLAUDE_PERMISSIONS = [
    "mcp__houdini__*",
    "Bash(mplay *)",
    "Read(/tmp/*)",
]


def allow_claude_tools(dry_run: bool) -> list:
    """Pre-approve the Houdini tools so Claude Code does not prompt per call."""
    path = _home(".claude", "settings.json")
    settings = {}
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as handle:
            settings = json.load(handle)
    allow = settings.setdefault("permissions", {}).setdefault("allow", [])
    added = [rule for rule in CLAUDE_PERMISSIONS if rule not in allow]
    if added and not dry_run:
        allow.extend(added)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(settings, handle, indent=2)
            handle.write("\n")
    return added
