"""The Turbo block tags of the views.

```html+jinja
{% turbo_frame post %}{{ post.title }}{% endturbo_frame %}
{% turbo_stream "append", "messages" %}<li>{{ message.body }}</li>{% endturbo_stream %}
```

`turbo_frame` takes the arguments of `turbo_frame_tag`, and `turbo_stream`
the action followed by the arguments of that action method; the body is
the content. As expressions, without a body, `turbo_frame_tag(...)` and
`turbo_stream.append(...)` are template globals.
"""
import typing as t
from collections.abc import Callable

from markupsafe import Markup

from .frame import turbo_frame_tag
from .stream import turbo_stream


def turbo_frame(*ids: t.Any, caller: Callable[[], t.Any], template: str, **attrs: t.Any) -> Markup:
    return turbo_frame_tag(*ids, caller=caller, **attrs)


def turbo_stream_tag(action: str, *args: t.Any, caller: Callable[[], t.Any], template: str, **kwargs: t.Any) -> Markup:
    return turbo_stream(action, *args, caller=caller, **kwargs)


TAGS = {
    "turbo_frame": turbo_frame,
    "turbo_stream": turbo_stream_tag,
}
