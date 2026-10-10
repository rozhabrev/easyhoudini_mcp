"""The tools that the person wrote: list them, run one (see houdinimcp.custom)."""
import json

from . import unknown_mode
from .. import custom

MUTATES = True


def mutates(params) -> bool:
    """A list changes nothing. A run changes the scene unless its tool was
    marked mutates=False, and only then goes in an undo group."""
    return params.get("mode", "list") == "run" and custom.mutates(params.get("name"))


def run(mode="list", name=None, params=None):
    if mode == "list":
        tools, problems = custom.load()
        return {"folders": custom.folders(),
                "tools": [custom.describe(tool, function, path)
                          for tool, (function, path) in tools.items()],
                "problems": problems}
    if mode == "run":
        if not name:
            raise ValueError("mode 'run' needs the argument 'name'.")
        result = custom.call(name, params)
        # The result goes out as JSON: what JSON cannot hold goes as its text.
        return json.loads(json.dumps(result, default=str))
    raise unknown_mode(mode, ["list", "run"])
