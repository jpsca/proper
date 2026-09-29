from proper.turbo import turbo_frame


def test_empty_frame():
    assert str(turbo_frame("messages")) == (
        '<turbo-frame id="messages"></turbo-frame>'
    )


def test_frame_with_src_and_loading():
    out = str(turbo_frame("messages", src="/messages", loading="lazy"))
    assert out == (
        '<turbo-frame id="messages" src="/messages" loading="lazy"></turbo-frame>'
    )


def test_id_from_a_model_instance():
    class Post:
        _pk = 5

    assert str(turbo_frame(Post())).startswith('<turbo-frame id="post_5">')


def test_multiple_ids_are_joined():
    assert str(turbo_frame("a", "b")).startswith('<turbo-frame id="a_b">')


def test_target_attribute():
    assert 'target="_top"' in str(turbo_frame("box", target="_top"))


def test_extra_attrs_turn_underscores_into_dashes():
    assert 'data-turbo="false"' in str(turbo_frame("box", data_turbo="false"))


def test_escapes_attribute_values():
    assert 'src="&#34;/x&#34;"' in str(turbo_frame("box", src='"/x"'))


def test_expression_form_renders_an_empty_frame(app):
    out = app.catalog.render_string('{{ frame("messages") }}')
    assert out.strip() == '<turbo-frame id="messages"></turbo-frame>'


def test_tag_wraps_rendered_content(app):
    out = app.catalog.render_string(
        '{% frame "messages" %}<p>{{ 1 + 1 }}</p>{% endframe %}'
    )
    assert out.strip() == '<turbo-frame id="messages"><p>2</p></turbo-frame>'


def test_tag_with_attributes_and_escaping(app):
    out = app.catalog.render_string(
        '{# def v #}{% frame "results", data_turbo_action="advance" %}{{ v }}{% endframe %}',
        v="<x>",
    )
    assert out == '<turbo-frame id="results" data-turbo-action="advance">&lt;x&gt;</turbo-frame>'
