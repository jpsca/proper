from proper.turbo import turbo_stream


def test_wraps_raw_html():
    out = str(turbo_stream("append", "messages", html="<li>hi</li>"))
    assert out == (
        '<turbo-stream action="append" target="messages">'
        "<template><li>hi</li></template>"
        "</turbo-stream>"
    )


def test_remove_omits_the_template():
    out = str(turbo_stream("remove", "message_1"))
    assert out == '<turbo-stream action="remove" target="message_1"></turbo-stream>'


def test_escapes_action_and_target():
    out = str(turbo_stream('a"x', 't"z', html="<b>!</b>"))
    assert 'action="a&#34;x"' in out
    assert 'target="t&#34;z"' in out


def test_renders_a_jx_component(app, tmp_path):
    (tmp_path / "Card.jx").write_text('<div class="card">Hi</div>')
    app.catalog.add_folder(tmp_path)

    out = str(turbo_stream("append", "messages", "Card.jx"))
    assert '<turbo-stream action="append" target="messages">' in out
    assert "<template>" in out
    assert '<div class="card">Hi</div>' in out


def test_streams_concatenate():
    combined = (
        turbo_stream("remove", "message_1")
        + turbo_stream("append", "messages", html="<li>x</li>")
    )
    assert str(combined).count("<turbo-stream") == 2


def test_action_method_matches_positional_call():
    method = str(turbo_stream.append("messages", html="<li>x</li>"))
    positional = str(turbo_stream("append", "messages", html="<li>x</li>"))
    assert method == positional


def test_each_action_method_sets_its_action():
    for action in ("append", "prepend", "replace", "update", "before", "after"):
        out = str(getattr(turbo_stream, action)("box", html="<p>x</p>"))
        assert out.startswith(f'<turbo-stream action="{action}" target="box">')
        assert "<template><p>x</p></template>" in out


def test_target_accepts_a_model_instance():
    class Message:
        _pk = 7

    out = str(turbo_stream.replace(Message(), html="<li>x</li>"))
    assert out.startswith('<turbo-stream action="replace" target="message_7">')


def test_targets_uses_a_css_selector():
    out = str(turbo_stream.append(targets="li.done", html="<li>x</li>"))
    assert '<turbo-stream action="append" targets="li.done">' in out
    assert 'target="' not in out


def test_remove_with_targets_omits_the_template():
    out = str(turbo_stream.remove(targets=".gone"))
    assert out == '<turbo-stream action="remove" targets=".gone"></turbo-stream>'


def test_replace_with_the_morph_method():
    out = str(turbo_stream.replace("post_1", html="<p>x</p>", method="morph"))
    assert out == (
        '<turbo-stream action="replace" method="morph" target="post_1">'
        "<template><p>x</p></template>"
        "</turbo-stream>"
    )


def test_update_with_the_morph_method():
    out = str(turbo_stream.update(targets=".post", html="<p>x</p>", method="morph"))
    assert out == (
        '<turbo-stream action="update" method="morph" targets=".post">'
        "<template><p>x</p></template>"
        "</turbo-stream>"
    )


def test_method_in_a_positional_call_matches_the_action_method():
    method = str(turbo_stream.replace("post_1", html="<p>x</p>", method="morph"))
    positional = str(turbo_stream("replace", "post_1", html="<p>x</p>", method="morph"))
    assert method == positional


def test_method_is_escaped():
    out = str(turbo_stream.replace("post_1", html="", method='m"x'))
    assert 'method="m&#34;x"' in out


def test_method_is_not_a_prop_of_the_component(app, tmp_path):
    (tmp_path / "Card.jx").write_text("<div {{ attrs.render() }}>Hi</div>")
    app.catalog.add_folder(tmp_path)

    out = str(turbo_stream.replace("post_1", "Card.jx", method="morph"))
    assert "<template><div >Hi</div></template>" in out


def test_method_is_a_prop_in_the_other_actions(app, tmp_path):
    (tmp_path / "Form.jx").write_text('{#def method #}<form method="{{ method }}"></form>')
    app.catalog.add_folder(tmp_path)

    out = str(turbo_stream.append("forms", "Form.jx", method="post"))
    assert out == (
        '<turbo-stream action="append" target="forms">'
        '<template><form method="post"></form></template>'
        "</turbo-stream>"
    )


def test_tag_with_the_morph_method(app):
    out = app.catalog.render_string(
        '{% stream "update", "post_1", method="morph" %}<p>x</p>{% endstream %}'
    )
    assert out.strip() == (
        '<turbo-stream action="update" method="morph" target="post_1">'
        "<template><p>x</p></template>"
        "</turbo-stream>"
    )


def test_refresh_has_no_target_or_template():
    assert str(turbo_stream.refresh()) == (
        '<turbo-stream action="refresh"></turbo-stream>'
    )


def test_refresh_with_request_id():
    out = str(turbo_stream.refresh(request_id="abc"))
    assert out == '<turbo-stream action="refresh" request-id="abc"></turbo-stream>'


def test_refresh_with_method_and_scroll():
    out = str(turbo_stream.refresh(method="morph", scroll="preserve"))
    assert out == (
        '<turbo-stream action="refresh" method="morph" scroll="preserve">'
        "</turbo-stream>"
    )


def test_refresh_escapes_its_attributes():
    out = str(turbo_stream.refresh(request_id='a"b', method='m"x', scroll='s"y'))
    assert out == (
        '<turbo-stream action="refresh" request-id="a&#34;b" method="m&#34;x"'
        ' scroll="s&#34;y"></turbo-stream>'
    )


def test_component_takes_precedence_over_html(app, tmp_path):
    (tmp_path / "Card.jx").write_text('<div class="card">Hi</div>')
    app.catalog.add_folder(tmp_path)

    out = str(turbo_stream.append("messages", "Card.jx", html="<li>ignored</li>"))
    assert '<div class="card">Hi</div>' in out
    assert "ignored" not in out


def test_caller_takes_precedence_over_html(app, tmp_path):
    (tmp_path / "Card.jx").write_text('<div class="card">Hi</div>')
    app.catalog.add_folder(tmp_path)

    out = str(turbo_stream.append("messages", html="<li>ignored</li>", caller=lambda: '<div class="card">Hi</div>'))
    assert '<div class="card">Hi</div>' in out
    assert "ignored" not in out


def test_tag_in_a_template(app):
    out = app.catalog.render_string(
        '{% stream "append", "messages" %}<li>{{ 1 + 1 }}</li>{% endstream %}'
    )
    assert out.strip() == (
        '<turbo-stream action="append" target="messages">'
        "<template><li>2</li></template>"
        "</turbo-stream>"
    )
