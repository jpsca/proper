"""The `{% cache %}` tag of the views: fragment caching.

```html+jinja
{% cache(card) %}<h2>{{ card.title }}</h2>{% endcache %}
{% cache("sidebar", expires_in=300) %}...{% endcache %}
```

The body is rendered only when the fragment is not in the cache. The key is
built with `key_for`: an object or a collection is prefixed with the path of
the template; a string is used as it is (lowercased), so the same string in
two templates is one fragment.
"""
import typing as t

from .keys import key_for


if t.TYPE_CHECKING:
    from .base import BaseCache


def cache_tag(cache: "BaseCache") -> t.Callable[..., t.Any]:
    """The function of the `cache` tag, storing the fragments in `cache`."""

    def tag(
        key_context: t.Any,
        *,
        caller: t.Callable[[], t.Any],
        template: str,
        expires_in: int | None = None,
        version: str | int | None = None,
        race_condition_ttl: int | None = None,
    ) -> t.Any:
        key = key_for(prefix=template, key_context=key_context, version=version)
        return cache.get_or_set(
            key, caller, expires_in=expires_in, race_condition_ttl=race_condition_ttl,
        )

    return tag
