"""rules — the house rules for one kind of work."""
from mcp.types import ToolAnnotations

from . import topics

ANNOTATIONS = ToolAnnotations(readOnlyHint=True)


def tool(topic: str) -> str:
    """Read the house rules for one kind of work, before you start it.

    The core rules came with your first result. Each topic adds what one kind
    of work needs, and wins over your habits the same way:

        modeling     modeling from references or a description, blockout,
                     repeats, turned shapes, booleans
        usd          anything in /stage: stage layout, prim names, kinds,
                     references and payloads, instancing, caches
        look         materials, COP textures, lights, camera, Karma render
        destruction  RBD fracture, constraints, the bullet solver, caches
        scripting    before Python or HScript sent to Houdini
        pdg          several renders at once, anything in a TOP network

    Read a topic once per session. Work in /stage needs both usd and look.
    """
    text = topics.read(topic)
    if text is None:
        return f"There is no topic '{topic}'. Topics: {', '.join(topics.names())}."
    topics.mark_sent(topic)
    return text
