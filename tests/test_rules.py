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


def test_the_server_carries_the_core_rules():
    from bridge import cli
    assert "When to stop and ask" in cli.RULES
    assert "Topics" in cli.RULES
    assert cli.RULES in cli.build().instructions


def test_every_topic_named_in_the_core_has_a_file():
    from bridge import cli
    from bridge.tools import topics
    assert set(topics.names()) == {"modeling", "usd", "look", "destruction", "scripting", "pdg"}
    for name in topics.names():
        assert f"`{name}`" in cli.RULES
    assert "revolving a profile" in topics.read("modeling")
    assert "outside breaks first" in topics.read("destruction")


def test_the_rules_tool_reads_a_topic_and_names_the_topics_for_a_wrong_one(monkeypatch):
    from bridge import tools
    from bridge.tools import topics
    tools.build("")
    monkeypatch.setattr(topics, "SENT", set())
    call = tools.TOOLS["rules"].fn
    assert "Karma Material Builder" in call(topic="look")
    assert "Topics: destruction, look" in call(topic="lighting")


def test_a_call_in_stage_brings_the_usd_and_look_topics_once(monkeypatch):
    from bridge import tools
    from bridge.tools import playbar, topics
    tools.build("")
    monkeypatch.setattr(topics, "SENT", set())
    assert "Studio" not in tools._with_topics("ok", "playbar", {"mode": "get"})
    first = tools._with_topics("ok", "node_edit", {"parent": "/stage"})
    assert "USD pipeline" in first and "Karma Material Builder" in first
    assert tools._with_topics("ok", "node_edit", {"parent": "/stage"}) == "ok"
    assert "Scripting" in tools._with_topics("ok", "execute", {"code": "x"})


def test_the_core_tells_the_agent_to_show_its_work():
    from bridge import cli
    assert "Show your work on screen" in cli.RULES
    assert cli.RULES.index("Show your work") < cli.RULES.index("Before you build")


def test_select_sends_show_only_when_asked(monkeypatch):
    from bridge import tools
    from bridge.tools import select
    tools.build("")
    sent = []
    monkeypatch.setattr(select, "call_json", lambda name, params: sent.append(params) or "{}")
    select.tool(paths=["/stage/a"])
    select.tool(paths=["/stage/a"], show=True)
    assert sent == [{"paths": ["/stage/a"]},
                    {"paths": ["/stage/a"], "show": True, "display": False}]
