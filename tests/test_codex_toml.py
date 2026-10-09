"""The Codex block of config.toml must parse with Windows paths (ChatGPT desktop refused to start on "C:\\Users")."""
import tomllib

from bridge.onboarding import harnesses


def test_codex_block_parses_windows_paths(tmp_path, monkeypatch):
    cmd = {"command": r"C:\Users\Родион\.local\bin\uv.exe",
           "args": ["--directory", r"C:\Users\Родион\easyhoudini_mcp", "run", "server"]}
    monkeypatch.setattr(harnesses, "server_command", lambda repo_dir: cmd)
    monkeypatch.setattr(harnesses, "_home", lambda *p: str(tmp_path.joinpath(*p)))
    cfg = tmp_path / ".codex" / "config.toml"
    cfg.parent.mkdir()
    cfg.write_text('model = "gpt-5"\n', encoding="utf-8")
    harnesses._codex_configure("repo", dry_run=False)
    harnesses._codex_configure("repo", dry_run=False)          # a second run replaces the block
    data = tomllib.loads(cfg.read_text(encoding="utf-8"))
    srv = data["mcp_servers"][harnesses.SERVER_NAME]
    assert srv["command"] == cmd["command"] and srv["args"] == cmd["args"] and data["model"] == "gpt-5"
