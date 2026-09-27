"""
Jx | Copyright (c) Juan-Pablo Scaletti
"""

from proper.jx import Catalog


def test_slots(folder):
    (folder / "modal.jx").write_text("""
<div {{ attrs.render(class="modal") }}>
<div class="modal-header">{% slot header %}My header{% endslot %}</div>
<div class="modal-body">{{ content }}</div>
<div class="modal-footer">{% slot footer %}My footer{% endslot %}</div>
</div>
""")

    (folder / "page.jx").write_text("""
{# import "modal.jx" as Modal #}
<Modal>
{% fill header %}My custom header{% endfill %}
<p>Hello world!</p>
{% fill footer %}My custom footer{% endfill %}
</Modal>
""")

    cat = Catalog(folder, lorem="ipsum")
    html = cat.render("page.jx")
    print(html)
    assert html == """
<div class="modal">
<div class="modal-header">My custom header</div>
<div class="modal-body"><p>Hello world!</p></div>
<div class="modal-footer">My custom footer</div>
</div>
""".strip()


def test_slots_defaults(folder):
    (folder / "modal.jx").write_text("""
<div {{ attrs.render(class="modal") }}>
<div class="modal-header">{% slot header %}My header{% endslot %}</div>
<div class="modal-body">{{ content }}</div>
<div class="modal-footer">{% slot footer %}My footer{% endslot %}</div>
</div>
""")

    (folder / "page.jx").write_text("""
{# import "modal.jx" as Modal #}
<Modal>
<p>Hello world!</p>
{% fill random %}Random content{% endfill %}
</Modal>
""")

    cat = Catalog(folder, lorem="ipsum")
    html = cat.render("page.jx")
    print(html)
    assert html == """
<div class="modal">
<div class="modal-header">My header</div>
<div class="modal-body"><p>Hello world!</p></div>
<div class="modal-footer">My footer</div>
</div>
""".strip()


def test_slots_are_namespaced(folder):
    (folder / "modal.jx").write_text("""
<div {{ attrs.render(class="modal") }}>
<div class="modal-header">{% slot header %}My header{% endslot %}</div>
<div class="modal-body">{{ content }}</div>
<div class="modal-footer">{% slot footer %}My footer{% endslot %}</div>
</div>
""")

    (folder / "page.jx").write_text("""
{# import "modal.jx" as Modal #}
<Modal id="m1">
{% fill header %}Header 1{% endfill %}
<p>Hello world!</p>
{% fill footer %}Footer 1{% endfill %}
</Modal>
<Modal id="m2">
{% fill header %}Header 2{% endfill %}
<p>Hello world!</p>
{% fill footer %}Footer 2{% endfill %}
</Modal>
""")

    cat = Catalog(folder, lorem="ipsum")
    html = cat.render("page.jx")
    print(html)
    assert html == """
<div class="modal" id="m1">
<div class="modal-header">Header 1</div>
<div class="modal-body"><p>Hello world!</p></div>
<div class="modal-footer">Footer 1</div>
</div>
<div class="modal" id="m2">
<div class="modal-header">Header 2</div>
<div class="modal-body"><p>Hello world!</p></div>
<div class="modal-footer">Footer 2</div>
</div>
""".strip()


def test_slots_when_inline(folder):
    (folder / "modal.jx").write_text("""
<div {{ attrs.render(class="modal") }}>
<div class="modal-header">{% slot header %}My header{% endslot %}</div>
<div class="modal-body">{{ content }}</div>
<div class="modal-footer">{% slot footer %}My footer{% endslot %}</div>
</div>
""")

    (folder / "page.jx").write_text("""
{# import "modal.jx" as Modal #}
<Modal content="Hi" />
""")

    cat = Catalog(folder, lorem="ipsum")
    html = cat.render("page.jx")
    print(html)
    assert html == """
<div class="modal">
<div class="modal-header">My header</div>
<div class="modal-body">Hi</div>
<div class="modal-footer">My footer</div>
</div>
""".strip()


def test_fill_rendered(folder):
    (folder / "icon.jx").write_text("""
{# def name #}
<span class="fa fa-{{ name }}"></span>
""".strip())

    (folder / "modal.jx").write_text("""
<div {{ attrs.render(class="modal") }}>
<div class="modal-header">
{% slot header %}My header{% endslot %}
</div>
<div class="modal-body">{{ content }}</div>
</div>
""".strip())


    (folder / "page.jx").write_text("""
{# import "modal.jx" as Modal #}
{# import "icon.jx" as Icon #}
<Modal>
{% fill header -%}
<Icon name="wave" /> Hi!
{%- endfill %}
<p>Hello world!</p>
</Modal>
""")

    cat = Catalog(folder, lorem="ipsum")
    html = cat.render("page.jx")
    print(html)
    assert html == """
<div class="modal">
<div class="modal-header">
<span class="fa fa-wave"></span> Hi!
</div>
<div class="modal-body"><p>Hello world!</p></div>
</div>
""".strip()


def test_fills_of_a_nested_component(folder):
    """A fill must be applied to its own component, not to a wrapping one."""
    (folder / "wrapper.jx").write_text("""
<section>{{ content }}</section>
""".strip())

    (folder / "modal.jx").write_text("""
<div class="modal-header">{% slot header %}My header{% endslot %}</div>
<div class="modal-body">{{ content }}</div>
""".strip())

    (folder / "page.jx").write_text("""
{# import "wrapper.jx" as Wrapper #}
{# import "modal.jx" as Modal #}
<Wrapper>
<Modal>
{% fill header %}My custom header{% endfill %}
<p>Hello world!</p>
</Modal>
</Wrapper>
""")

    cat = Catalog(folder, lorem="ipsum")
    html = cat.render("page.jx")
    print(html)
    assert html == """
<section><div class="modal-header">My custom header</div>
<div class="modal-body"><p>Hello world!</p></div></section>
""".strip()


def test_slot_default_rendered(folder):
    (folder / "icon.jx").write_text("""
{# def name #}
<span class="fa fa-{{ name }}"></span>
""".strip())

    (folder / "modal.jx").write_text("""
{# import "icon.jx" as Icon #}
<div {{ attrs.render(class="modal") }}>
<div class="modal-header">
{% slot header %}<Icon name="wave" /> Hi!{% endslot %}
</div>
<div class="modal-body">{{ content }}</div>
</div>
""".strip())

    (folder / "page.jx").write_text("""
{# import "modal.jx" as Modal #}
<Modal>
<p>Hello world!</p>
</Modal>
""")

    cat = Catalog(folder, lorem="ipsum")
    html = cat.render("page.jx")
    print(html)
    assert html == """
<div class="modal">
<div class="modal-header">
<span class="fa fa-wave"></span> Hi!
</div>
<div class="modal-body"><p>Hello world!</p></div>
</div>
""".strip()
