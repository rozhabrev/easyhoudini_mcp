"""The topic files of the house rules, and which of them the agent has read.

Not a tool: build() skips modules without a tool() function.
"""
import json
from pathlib import Path

FOLDER = Path(__file__).parent.parent / "rules"
SENT = set()

# A call that touches one of these words works in that topic. The agent that
# skipped the topic gets it with the result, once: a rule that it never read
# does not exist for it.
TRIGGERS = {
    "usd": ("/stage", "usd", "sopcreate", "lopnet"),
    "look": ("/stage", "karma", "materiallibrary", "mtlx", "copnet"),
    "destruction": ("rbd", "fracture", "bullet"),
    "pdg": ("topnet", "render_setup", "ropfetch", "wedge", "localscheduler"),
}


def names() -> list:
    return sorted(path.stem for path in FOLDER.glob("*.md"))


def read(topic: str):
    path = FOLDER / f"{(topic or '').strip().lower()}.md"
    return path.read_text(encoding="utf-8") if path.is_file() else None


def mark_sent(topic: str) -> None:
    SENT.add(topic.strip().lower())


def due(tool: str, arguments: dict) -> list:
    """The topics this call works in that the agent has not read yet."""
    if tool == "rules":
        return []
    text = json.dumps(arguments, default=str).lower()
    found = [topic for topic, words in TRIGGERS.items()
             if any(word in text for word in words)]
    if tool == "execute":
        found.append("scripting")
    return [topic for topic in found if topic not in SENT and read(topic)]
