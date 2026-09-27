"""
Jx | Copyright (c) Juan-Pablo Scaletti
"""

import copy
import typing as t
from collections.abc import Callable
from functools import partial

import jinja2
from markupsafe import Markup

from .attrs import Attrs
from .exceptions import (
    ComponentNotFoundError,
    InvalidPropType,
    MaxRecursionDepthError,
    MissingRequiredArgument,
)


MAX_COMPONENT_DEPTH = 100

# Defaults that cannot be shared between renders: one component mutating its
# own default would change it for every later render of that component.
MUTABLE_DEFAULTS = (list, dict, set)

# "No value was passed", as opposed to "None was passed". Module level because
# `filter_attrs` runs once per component render and this never varies.
_MISSING = object()

# What the catalog's asset cache holds: the list of assets for a whole subtree,
# and the set of components it was built from. The list alone is not enough to
# know whether it is still good — see `Component._cached_assets`.
AssetEntry = tuple[set[str], list[str]]
AssetCache = dict[str, AssetEntry]


class Component:
    __slots__ = (
        "relpath",
        "tmpl",
        "get_component",
        "required",
        "optional",
        "imports",
        "css",
        "js",
        "slots",
        "asset_resolver",
        "_asset_cache",
        "_child_cache",
        "_required_spec",
        "_optional_plain",
        "_optional_spec",
    )

    def __init__(
        self,
        *,
        relpath: str,
        tmpl: jinja2.Template,
        get_component: Callable[[str], "Component"],
        required: dict[str, type | None] | None = None,
        optional: dict[str, tuple[t.Any, type | None]] | None = None,
        imports: dict[str, str] | None = None,
        css: tuple[str, ...] = (),
        js: tuple[str, ...] = (),
        slots: tuple[str, ...] = (),
        asset_resolver: Callable[[str, str], str] | None = None,
        asset_cache: "Callable[[], AssetCache] | None" = None,
        cache_children: bool = False,
    ) -> None:
        """
        Internal object that represents a Jx component.

        Arguments:
            relpath:
                The "name" of the component.
            tmpl:
                The jinja2.Template for the component.
            get_component:
                A callable that retrieves a component by its name/relpath.
            required:
                A dictionary of required attribute names mapped to their type (or None).
            optional:
                A dictionary of optional attributes mapped to (default_value, type or None).
            imports:
                A dictionary of imported component names as "name": "relpath" pairs.
            css:
                A tuple of CSS file URLs.
            js:
                A tuple of JS file URLs.
            slots:
                A tuple of slot names.
            asset_resolver:
                A callable that transforms asset URLs. Receives (url, prefix) and
                returns the resolved URL.
            asset_cache:
                A callable returning the catalog's current asset cache. Read on
                use, not captured on construction: a component outlives any one
                of those dicts, since a recompile replaces it.
            cache_children:
                Whether resolved child components can be remembered on this
                instance. Only true when the catalog does not auto-reload:
                resolving a child goes through `get_component_data`, and with
                auto-reload on that call is what stats the child's file. Caching
                past it would keep serving a child whose source has changed.

        """
        self.relpath = relpath
        self.tmpl = tmpl
        self.get_component = get_component

        self.required = required or {}
        self.optional = optional or {}
        self.imports = imports or {}
        self.css = css
        self.js = js
        self.slots = slots
        self.asset_resolver = asset_resolver
        self._asset_cache = asset_cache
        # `None` means "do not cache", which is one check on the hot path
        # instead of a flag plus a dict lookup.
        self._child_cache: dict[str, Component] | None = {} if cache_children else None

        # The prop signature is fixed for the life of the component, so
        # everything `filter_attrs` can answer from it alone is answered here,
        # once, instead of on every render.
        self._required_spec = tuple(self.required.items())

        # An untyped prop with an immutable default needs no validation and no
        # copy: the value either arrived or it is the default. That collapses
        # to a single `dict.pop(key, default)`.
        plain: dict[str, t.Any] = {}
        spec: list[tuple[str, t.Any, type | None, bool]] = []
        for key, (default, expected_type) in self.optional.items():
            mutable = isinstance(default, MUTABLE_DEFAULTS)
            if expected_type is None and not mutable:
                plain[key] = default
            else:
                spec.append((key, default, expected_type, mutable))
        self._optional_plain = plain
        self._optional_spec = tuple(spec)

    def render(
        self,
        *,
        content: str | None = None,
        attrs: Attrs | dict[str, t.Any] | None = None,
        caller: Callable[[], str] | None = None,
        _fills: "dict[str, Callable[[], Markup]] | None" = None,
        _globals: dict[str, t.Any] | None = None,
        **params: t.Any,
    ) -> Markup:
        # The globals belong to a render tree, not to a component. Passing them
        # in, instead of assigning them to the instance, is what lets one
        # instance be shared by every render of that component.
        _globals = _globals or {}
        depth = _globals.get("_depth", 0)
        if depth > MAX_COMPONENT_DEPTH:
            raise MaxRecursionDepthError(MAX_COMPONENT_DEPTH)

        child_globals = {**_globals, "_depth": depth + 1}

        content = content if content is not None else caller() if caller else ""
        attrs = attrs.as_dict if isinstance(attrs, Attrs) else attrs or {}
        params = {**attrs, **params}
        props, attrs = self.filter_attrs(params)

        tpl_globals = {
            **child_globals,
            "_render": partial(self._render_child, child_globals),
        }
        tpl_globals.setdefault("attrs", Attrs(attrs))
        tpl_globals.setdefault("content", content)

        # One body, one function: the caller states which slots it filled by
        # passing them, so there is nothing to infer. A name the component does
        # not declare is simply never looked up.
        props["_slots"] = _fills or {}

        html = self.tmpl.render({**props, **tpl_globals}).lstrip()
        return Markup(html)

    def filter_attrs(
        self, kw: dict[str, t.Any]
    ) -> tuple[dict[str, t.Any], dict[str, t.Any]]:
        props = {}

        for key, expected_type in self._required_spec:
            try:
                value = kw.pop(key)
            except KeyError:
                raise MissingRequiredArgument(self.relpath, key) from None
            if expected_type is not None and not isinstance(value, expected_type):
                raise InvalidPropType(self.relpath, key, expected_type, type(value))
            props[key] = value

        for key, default in self._optional_plain.items():
            props[key] = kw.pop(key, default)

        for key, default, expected_type, mutable in self._optional_spec:
            value = kw.pop(key, _MISSING)
            if value is _MISSING:
                value = copy.copy(default) if mutable else default
            if expected_type is not None and not isinstance(value, expected_type):
                raise InvalidPropType(self.relpath, key, expected_type, type(value))
            props[key] = value

        return props, kw

    def _render_child(
        self, globals: dict[str, t.Any], name: str, /, **params: t.Any
    ) -> Markup:
        """
        Resolve a tag and render it under the globals of the current render.

        Both leading arguments are positional-only: every attribute written on
        the tag arrives in `**params`, and a component is free to declare a
        prop called `name` or `globals`.

        The cache is read here rather than in `get_child` so that a hit costs
        one dict lookup instead of a call: this runs once per child component
        per render, which is the single hottest path in the library.
        """
        cache = self._child_cache
        if cache is not None:
            child = cache.get(name)
            if child is not None:
                return child.render(_globals=globals, **params)
        return self.get_child(name).render(_globals=globals, **params)

    def get_child(self, name: str) -> "Component":
        cache = self._child_cache
        if cache is not None:
            child = cache.get(name)
            if child is not None:
                return child

        relpath = self.imports.get(name)
        if relpath is None:
            raise ComponentNotFoundError(
                f"{name} (imported in {self.relpath})"
            )
        child = self.get_component(relpath)

        if cache is not None:
            cache[name] = child
        return child

    def resolve_url(self, url: str) -> str:
        if not self.asset_resolver:
            return url
        prefix = ""
        if self.relpath.startswith("@"):
            prefix = self.relpath.split("/", 1)[0][1:]
        return self.asset_resolver(url, prefix)

    def collect_css(self, _visited: set[str] | None = None) -> list[str]:
        """
        Returns a list of CSS files for the component and its children.
        """
        if _visited is None and self._asset_cache is not None:
            return self._cached_assets("css")
        return self._collect_assets("css", _visited)

    def collect_js(self, _visited: set[str] | None = None) -> list[str]:
        """
        Returns a list of JS files for the component and its children.
        """
        if _visited is None and self._asset_cache is not None:
            return self._cached_assets("js")
        return self._collect_assets("js", _visited)

    def _cached_assets(self, attr: str) -> list[str]:
        """
        The asset list for this component, remembered between renders.

        The list covers the whole subtree, so this component being unchanged
        says nothing about whether the list is still right. Every component it
        was built from is touched before the entry is trusted: a stale one
        recompiles right here, and recompiling is what drops the catalog's
        asset cache — which is how we find out the entry is no longer good.
        """
        assert self._asset_cache is not None
        key = f"{self.relpath}:{attr}"
        entry = self._asset_cache().get(key)
        if entry is not None:
            deps, result = entry
            for relpath in deps:
                self.get_component(relpath)
            if self._asset_cache().get(key) is entry:
                return result

        deps: set[str] = set()
        result = self._collect_assets(attr, deps)
        self._asset_cache()[key] = (deps, result)
        return result

    def _collect_assets(
        self, attr: str, _visited: set[str] | None = None
    ) -> list[str]:
        resolved = [self.resolve_url(url) for url in getattr(self, attr)]
        urls = dict.fromkeys(resolved)  # ordered dedup
        # Not `or set()`: an empty set is falsy, and the caller needs the set
        # it passed in to come back filled.
        if _visited is None:
            _visited = set()
        _visited.add(self.relpath)

        for name, relpath in self.imports.items():
            if relpath in _visited:
                continue
            co = self.get_child(name)
            for file in co._collect_assets(attr, _visited=_visited):
                if file not in urls:
                    urls[file] = None

        return list(urls.keys())

    def render_css(self) -> Markup:
        """
        Uses the `collect_css()` list to generate an HTML fragment
        with `<link rel="stylesheet" href="{url}">` tags.
        """
        html = []
        for url in self.collect_css():
            html.append(f'<link rel="stylesheet" href="{url}">')

        return Markup("\n".join(html))

    def render_js(self, module: bool = True, defer: bool = True) -> Markup:
        """
        Uses the `collect_js()` list to generate an HTML fragment
        with `<script type="module" src="{url}"></script>` tags.

        Arguments:
            module:
                Whether to render the script tags as modules, e.g.:
                `<script type="module" src="..."></script>`
            defer:
                Whether to add the `defer` attribute to the script tags,
                if `module` is `False` (all module scripts are also deferred), e.g.:
                `<script src="..." defer></script>`

        """
        html = []
        for url in self.collect_js():
            if module:
                tag = f'<script type="module" src="{url}"></script>'
            elif defer:
                tag = f'<script src="{url}" defer></script>'
            else:
                tag = f'<script src="{url}"></script>'
            html.append(tag)

        return Markup("\n".join(html))

    def render_assets(self, module: bool = True, defer: bool = True) -> Markup:
        """
        Calls `render_css()` and `render_js()` to generate
        an HTML fragment with `<link rel="stylesheet" href="{url}">`
        and `<script type="module" src="{url}"></script>` tags.

        Arguments:
            module:
                Whether to render the script tags as modules, e.g.:
                `<script type="module" src="..."></script>`
            defer:
                Whether to add the `defer` attribute to the script tags,
                if `module` is `False` (all module scripts are also deferred), e.g.:
                `<script src="..." defer></script>`

        """
        html_css = self.render_css()
        html_js = self.render_js(module=module, defer=defer)
        return Markup(("\n".join([html_css, html_js]).strip()))
