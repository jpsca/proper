from proper.turbo import turbo_frame_tag


def test_empty_frame():
    assert str(turbo_frame_tag("messages")) == (
        '<turbo-frame id="messages"></turbo-frame>'
    )


def test_frame_with_src_and_loading():
    out = str(turbo_frame_tag("messages", src="/messages", loading="lazy"))
    assert out == (
        '<turbo-frame id="messages" src="/messages" loading="lazy"></turbo-frame>'
    )


def test_id_from_a_model_instance():
    class Post:
        _pk = 5

    assert str(turbo_frame_tag(Post())).startswith('<turbo-frame id="post_5">')


def test_multiple_ids_are_joined():
    assert str(turbo_frame_tag("a", "b")).startswith('<turbo-frame id="a_b">')


def test_target_attribute():
    assert 'target="_top"' in str(turbo_frame_tag("box", target="_top"))


def test_extra_attrs_turn_underscores_into_dashes():
    assert 'data-turbo="false"' in str(turbo_frame_tag("box", data_turbo="false"))


def test_escapes_attribute_values():
    assert 'src="&#34;/x&#34;"' in str(turbo_frame_tag("box", src='"/x"'))


def test_expression_form_renders_an_empty_frame(app):
    out = app.catalog.render_string('{{ turbo_frame_tag("messages") }}')
    assert out.strip() == '<turbo-frame id="messages"></turbo-frame>'


def test_call_block_wraps_rendered_content(app):
    out = app.catalog.render_string(
        '{% call turbo_frame_tag("messages") %}<p>{{ 1 + 1 }}</p>{% endcall %}'
    )
    assert out.strip() == '<turbo-frame id="messages"><p>2</p></turbo-frame>'
