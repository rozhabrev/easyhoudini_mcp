def test_the_rules_go_with_the_first_result_only(monkeypatch):
    from bridge import tools
    from bridge.tools import playbar
    tools.build("RULES TEXT")
    monkeypatch.setitem(tools.RULES, "sent", False)
    monkeypatch.setattr(playbar, "call_json", lambda *a, **k: '{"frame": 1}')
    call = tools.TOOLS["playbar"].fn
    first, second = call(mode="get"), call(mode="get")
    assert first.startswith('{"frame": 1}') and first.endswith("RULES TEXT")
    assert second == '{"frame": 1}'


def test_a_list_result_gets_the_rules_as_its_own_item(monkeypatch):
    from bridge import tools
    monkeypatch.setitem(tools.RULES, "text", "R")
    monkeypatch.setitem(tools.RULES, "sent", False)
    assert tools._with_rules(["picture", "{}"])[-1].endswith("R")


def test_the_server_carries_the_rules():
    from bridge import cli
    assert "revolving a profile" in cli.RULES
    assert "outside breaks first" in cli.RULES
    assert cli.RULES in cli.build().instructions
