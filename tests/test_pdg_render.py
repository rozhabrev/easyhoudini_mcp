"""The parts of the parallel render setup that do not need Houdini."""
import pytest


def test_each_variant_gets_its_own_folder_and_file_name(hou):
    from houdinimcp.handlers import pdg
    out = pdg.variant_output("$HIP/render/hero.$F4.exr", "$HIP/render/variants")
    assert out == "$HIP/render/variants/`@variant`/hero.`@variant`.$F4.exr"
    assert pdg.variant_output("", "R").startswith("R/`@variant`/")


def test_variants_need_unique_safe_names(hou):
    from houdinimcp.handlers import pdg
    assert pdg.check_variants([{"name": "front", "camera": "/c"}]) == \
        [{"camera": "/c", "variant": "front"}]
    for bad in ([], [{"camera": "/c"}], [{"variant": "a b"}],
                [{"variant": "a"}, {"variant": "a"}]):
        with pytest.raises(ValueError):
            pdg.check_variants(bad)


def test_the_generate_script_makes_typed_attributes(hou):
    from houdinimcp.handlers import pdg

    made = []

    class Item:
        def __init__(self):
            self.attribs = {}
            made.append(self)

        def setIntAttrib(self, name, value, position):
            self.attribs.setdefault(name, ("int", []))[1].append(value)

        def setFloatAttrib(self, name, value, position):
            self.attribs.setdefault(name, ("float", []))[1].append(value)

        def setStringAttrib(self, name, value, position):
            self.attribs.setdefault(name, ("str", []))[1].append(value)

    class Holder:
        def addWorkItem(self, index):
            return Item()

    script = pdg.generate_script([
        {"variant": "top", "camera": "/cameras/top", "resolution": [960, 540],
         "pathtracedsamples": 0.5}])
    exec(script, {"item_holder": Holder()})
    assert made[0].attribs == {
        "variant": ("str", ["top"]), "camera": ("str", ["/cameras/top"]),
        "resolution": ("int", [960, 540]), "pathtracedsamples": ("float", [0.5])}


def test_a_render_setup_call_brings_the_pdg_rules(monkeypatch):
    from bridge.tools import topics
    monkeypatch.setattr(topics, "SENT", set())
    assert "pdg" in topics.due("pdg", {"mode": "render_setup", "path": "/stage/rop"})
