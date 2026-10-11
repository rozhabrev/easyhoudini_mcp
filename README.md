# easyhoudini MCP

  <a href="https://github.com/rozhabrev/easyhoudini_mcp/blob/main/LICENSE"><img src="https://img.shields.io/github/license/rozhabrev/easyhoudini_mcp?color=blue" alt="License: MIT"/></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.10%2B-blue?logo=python&logoColor=white" alt="Python 3.10+"/></a>
  <a href="https://modelcontextprotocol.io/"><img src="https://img.shields.io/badge/MCP-compatible-green" alt="MCP Compatible"/></a>
  <a href="https://www.sidefx.com/"><img src="https://img.shields.io/badge/Houdini-22.0-orange" alt="Houdini 22.0"/></a>

**An attempt to build the most sensible Houdini MCP out there.** It should be fast, build node graphs that a person can actually read, follow studio USD practice, and know when to stop and ask you instead of "improving" your scene into spaghetti.

Will it succeed? Ask us after the next timelapse. So far our agent has frozen Houdini with an endless VEX loop live on a screencast, quit Houdini by cooking a fracture in RAM, and built a beautiful procedural rig nobody asked for, when the prompt said "just draw it by hand". Each of those is now a rule in this repository. That is the whole idea: **every rule here was paid for by a real failure.**

And it records a neat **timelapse** of every session, so afterwards you can sit back and enjoy watching your scene grow node by node.

## How to install

Simply copy this line to the AI agent of your choice (Claude Code, Codex, Cursor, Gemini CLI, opencode, pi):

```
Install the Houdini MCP from https://github.com/rozhabrev/easyhoudini_mcp following its README, and connect it to my Houdini.
```

That's it. The agent runs the installer, which adds the plugin to Houdini and the server to your AI clients. Restart both. Manual install is [below](#manual-install).

## How to update

From 0.4.2 on, the MCP tells your agent when a new release is out, once a day at most. The agent tells you what changed and asks; nothing is downloaded until you say yes. It also tells you when the plugin in Houdini is an older copy than the server.

**On 0.4.1 or older?** Those versions cannot tell you. Update once: paste this to your agent.

```
Update the Houdini MCP to the latest version. Run these two commands, one after the other:
uv tool install --force git+https://github.com/rozhabrev/easyhoudini_mcp
uvx --from git+https://github.com/rozhabrev/easyhoudini_mcp houdinimcp-install --harness none --yes
On Windows the first command can end with "Failed to install entrypoint ... os error 32". That is expected: the MCP is updated, only its running launcher is busy. Then tell me to restart Houdini and you.
```

Then restart Houdini and the AI client. To check, ask the agent for `session` status: `mcp_version` shows the bridge and the plugin.

Set `HOUDINIMCP_NO_UPDATE_CHECK=1` to turn the check off.

## Why another Houdini MCP

We tried the big ones (188 tools) and the small ones. Agents ended up writing raw Python in most of their calls anyway, so a large tool list costs time and gives little. This MCP keeps a **small set of tools with modes** (one call, many items, one round trip) and puts the value where it matters: **house rules** that an agent reads before it touches your scene.

- **Fast.** About 20 tools with modes instead of hundreds. A batch is one round trip and one undo group.
- **Graphs a person can read.** Nodes named by meaning with an `aiNN_` prefix, blocks that end in `OUT_` nulls, network boxes, colour code, no stacked nodes (`scene_file` save runs a layout check).
- **Studio USD practice.** Stage layout, prim names, kinds, reference vs payload, instancing, USD caches, Karma setup, COP textures.
- **Works where you point it.** Give it a node, and it builds next to that node, in the same network, without flipping your display flags.
- **Procedural when you want it, by hand when you say so.** "Draw it by hand" means fixed geometry, not a rig with twelve sliders.
- **Shows, then asks.** After each result that is anywhere near ready, it shows a picture and a couple of numbers and asks: OK, or what to change. No endless "let me polish this a bit more".
- **Does not lose your work.** Saves a new version after each stage, autosaves before heavy steps, caches simulations and fractures to disk instead of RAM, stops a runaway script over the bridge, even when Houdini runs on another machine, and puts a limit on every VEX loop (a stuck VEX cook still needs Esc in Houdini, we know).
- **Learns from its own mistakes.** Every tool error goes to a local log, frequent errors come back to the agent with a concrete hint, and the same error twice tells it to stop and read the docs.
- **Sees what it built.** `capture` returns pictures to the agent, even when the agent runs on another machine.
- **Timelapse.** Every change is a frame: the Houdini window plus a still-camera view, so a session becomes a video.
- **Parallel renders.** Variants of one shot through a TOP network.
- **Offline docs.** The Houdini help of your own build, through houdinimd-docs.

The rules live in [`src/bridge/rules.md`](src/bridge/rules.md) (the core) and [`src/bridge/rules/`](src/bridge/rules/) (topics: modeling, USD, look, destruction, PDG, scripting). Your prompt always wins over a rule.

## Who tests it

The first testers are the students of **easyhoudini**, a Houdini + AI course by Rodion Zhabrev (in Russian). The rules come from their homework reviews and from real production sessions recorded on video.

Watch the sessions, the failures and the fixes on YouTube: **[youtube.com/@rodionzhabrev](https://www.youtube.com/@rodionzhabrev)**

## Manual install

**Windows**

```powershell
powershell -c "irm https://raw.githubusercontent.com/rozhabrev/easyhoudini_mcp/main/bootstrap.bat -OutFile bootstrap.bat; .\bootstrap.bat"
```

**macOS / Linux**

```bash
curl -sSL https://raw.githubusercontent.com/rozhabrev/easyhoudini_mcp/main/bootstrap.sh | bash
```

**uv**

```bash
uv tool install git+https://github.com/rozhabrev/easyhoudini_mcp && houdinimcp-install
```

The installer adds the plugin to Houdini and the server to your AI clients of choice. Restart both.\
pi also needs `pi install npm:pi-mcp-adapter`.

<details>
<summary><b>Troubleshooting</b></summary>

| Problem | Fix |
|---|---|
| No Houdini listens for the bridge | Start Houdini, or click **Toggle MCP Server** on the HoudiniMCP shelf. |
| No HoudiniMCP shelf | Restart Houdini. `houdinimcp-install --list` shows where the plugin went. |
| Houdini started from Git Bash has no plugin | Git Bash sets `HOME`. Set the user variable `HOUDINI_USER_PREF_DIR` to `%USERPROFILE%\Documents\houdini__HVER__`. |
| `capture` says there is no viewport | The session is headless. Call `session` with `action="start_gui"`. |
| You must have a fixed port | Set `HOUDINIMCP_PORT` for Houdini and for the bridge. Without it, the plugin takes a free port from the operating system and tells the bridge which one. |

</details>

<details>
<summary><b>For agents and scripts</b></summary>

Without a terminal, the installer asks nothing and takes the defaults.

```bash
houdinimcp-install --list          # Houdini installs and clients found, as JSON
houdinimcp-install --yes --json    # newest Houdini, every client found; JSON report
houdinimcp-install --houdini-version 22.0 --harness claude-code --yes
houdinimcp-install --dry-run --yes # change nothing
```

Flags: `--houdini-version none` skips the plugin, `--prefs-dir PATH` names the
prefs folder, `--harness none|all|KEY` (repeatable), `--quiet-start` stops the
first-launch dialogs. The bootstrap scripts pass every flag through.

Manual client setup: run `houdinimcp-bridge` with no arguments.
`claude mcp add --transport stdio houdini -- houdinimcp-bridge` for Claude Code.

From a clone: `uv run python -m bridge.onboarding.install`.

Layout: `src/houdinimcp/` is the plugin, a TCP server inside Houdini on a
free localhost port that it announces to the bridge. `src/bridge/` is the MCP server and the installer. Messages
are JSON with a 4-byte length prefix. `HOUDINIMCP_NO_HEADLESS=1` stops the
headless start. Read [AGENTS.md](AGENTS.md) before you change code.

</details>

## Tools

| | |
|---|---|
| **Read** | `scene_overview` `node_inspect` `geometry_inspect` `stage_inspect` `select` `console` |
| **Edit** | `node_edit` `parm_set` `connect` `hda` `batch` |
| **Run** | `cook` `render` `pdg` `playbar` `scene_file` |
| **See** | `capture`: the viewport, a camera, four views, a flipbook, the timelapse |
| **Code** | `execute`: Python, HScript, expressions, VEX check |
| **Docs** | `docs`: the Houdini documentation of your build, offline |
| **Rules** | `rules`: the house rules by topic |
| **Session** | `session`: status, start, attach, interrupt |
| **Yours** | `custom`: the tools that you write, see below |

> **Warning:** `execute` runs any Python in Houdini. Save your work. (We learned this one too.)

## Your own tools

Put your way of doing a step in a Python file, and the agent uses it instead of
building the step again by hand. The folder is
`$HOUDINI_USER_PREF_DIR/easyhoudini_mcp/tools/`, or any folder in the
environment variable `HOUDINIMCP_TOOLS`. One decorator makes a function a tool:

```python
import hou
from houdinimcp.custom import tool


@tool
def balls_on_grid(parent: str = "/obj", count: int = 50, radius: float = 0.05) -> dict:
    """Spheres scattered on a grid. Use it when the request is balls on a grid."""
    geo = hou.node(parent).createNode("geo", "balls_on_grid")
    scatter = geo.createNode("scatter")
    scatter.setFirstInput(geo.createNode("grid"))
    scatter.parm("npts").set(count)
    sphere = geo.createNode("sphere")
    sphere.parm("scale").set(radius)
    copy = geo.createNode("copytopoints")
    copy.setInput(0, sphere)
    copy.setInput(1, scatter)
    copy.setDisplayFlag(True)
    geo.layoutChildren()
    return {"node": copy.path()}
```

The agent reads the docstring and the arguments, the same way it reads any
other tool, so write in the docstring when to use it. The list of your tools
comes with the first result of a session. A run is one undo group;
`@tool(mutates=False)` marks a tool that only reads. A changed file is read
again on the next call, no restart.

## Credits and license

MIT License, free to use, change and sell, as long as the copyright lines stay. See [LICENSE](LICENSE) and [NOTICE](NOTICE).

This project stands on the work of others, and most of the plumbing is theirs:

- [houdini-mcp](https://github.com/JTCHE/houdini-mcp) by John Chedeville (JTCHE): the base of this repository, its tools and installer.
- [houdinimd-docs (NodebookMD)](https://pypi.org/project/houdinimd-docs/) by John Chedeville: the offline docs engine.
- [fxhoudinimcp](https://github.com/healkeiser/fxhoudinimcp) by healkeiser: the timelapse module is ported from our fork of it.
- [blender-mcp](https://github.com/ahujasid/blender-mcp), [capoomgit/houdini-mcp](https://github.com/capoomgit/houdini-mcp), [eetumartola/houdini-mcp](https://github.com/eetumartola/houdini-mcp), [Houdini21MCP](https://github.com/orrzxz/Houdini21MCP): code that houdini-mcp carries.

Our part is the rules, the timelapse, pictures to the agent, the error loop and the fixes from real sessions.

<sub>Not affiliated with SideFX. Houdini and SideFX are trademarks of SideFX Software Inc.</sub>
