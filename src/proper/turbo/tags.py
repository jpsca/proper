"""The Turbo block tags of the views.

```html+jinja
{% frame post %}{{ post.title }}{% endframe %}
{% stream "append", "messages" %}<li>{{ message.body }}</li>{% endstream %}
```

`turbo_frame` takes the arguments of `frame` tag, and `turbo_stream`
the action followed by the arguments of that action method; the body is
the content. As expressions, without a body, `frame(...)` and
`stream.append(...)` are template globals.
"""
import typing as t
from collections.abc import Callable

from markupsafe import Markup

from .frame import turbo_frame
from .stream import turbo_stream


def frame_tag(*ids: t.Any, caller: Callable[[], t.Any], template: str, **attrs: t.Any) -> Markup:
    return turbo_frame(*ids, caller=caller, **attrs)


def stream_tag(action: str, *args: t.Any, caller: Callable[[], t.Any], template: str, **kwargs: t.Any) -> Markup:
    return turbo_stream(action, *args, caller=caller, **kwargs)


TAGS = {
    "frame": frame_tag,
    "stream": stream_tag,
}
