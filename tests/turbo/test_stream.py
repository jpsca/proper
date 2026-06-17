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
    for action in ("append", "prepend", "replace", "update", "before", "after", "morph"):
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


def test_morph_keeps_the_template():
    out = str(turbo_stream.morph("post_1", html="<p>x</p>"))
    assert out == (
        '<turbo-stream action="morph" target="post_1">'
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


def test_action_method_renders_a_jx_component(app, tmp_path):
    (tmp_path / "Card.jx").write_text('<div class="card">Hi</div>')
    app.catalog.add_folder(tmp_path)

    out = str(turbo_stream.append("messages", "Card.jx"))
    assert '<turbo-stream action="append" target="messages">' in out
    assert '<div class="card">Hi</div>' in out


def test_html_as_a_value():
    out = str(turbo_stream.append("messages", html="<li>x</li>"))
    assert out == (
        '<turbo-stream action="append" target="messages">'
        "<template><li>x</li></template>"
        "</turbo-stream>"
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


def test_call_block_form_in_a_template(app):
    out = app.catalog.render_string(
        '{% call turbo_stream.append("messages") %}<li>{{ 1 + 1 }}</li>{% endcall %}'
    )
    assert out.strip() == (
        '<turbo-stream action="append" target="messages">'
        "<template><li>2</li></template>"
        "</turbo-stream>"
    )
