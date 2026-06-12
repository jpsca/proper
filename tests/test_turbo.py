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
