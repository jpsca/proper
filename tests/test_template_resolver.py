"""Tests for proper.template_resolver."""
import pytest
from jx import ComponentNotFoundError

from proper.template_resolver import (
    iter_candidates,
    iter_format_extensions,
    resolve_template,
)


class FakeCatalog:
    def __init__(self, names):
        self.names = set(names)
        self.probed = []

    def has(self, name):
        self.probed.append(name)
        return name in self.names


class TestIterFormatExtensions:
    def test_single_mime(self):
        assert list(iter_format_extensions(["application/json"])) == ["json"]

    def test_preserves_order(self):
        assert list(iter_format_extensions(
            ["application/json", "text/html"]
        )) == ["json", "html"]

    def test_stops_at_wildcard(self):
        assert list(iter_format_extensions(
            ["text/html", "*/*", "application/json"]
        )) == ["html"]

    def test_skips_unknown_mimes(self):
        assert list(iter_format_extensions(
            ["application/x-made-up", "text/html"]
        )) == ["html"]

    def test_empty(self):
        assert list(iter_format_extensions([])) == []


class TestIterCandidates:
    def test_single_prefix_single_format(self):
        assert list(iter_candidates(["pages/posts"], "show", ["html"])) == [
            "pages/posts/show.html.jx",
            "pages/posts/show.jx",
        ]

    def test_multiple_formats(self):
        assert list(iter_candidates(["pages/posts"], "show", ["json", "html"])) == [
            "pages/posts/show.json.jx",
            "pages/posts/show.html.jx",
            "pages/posts/show.jx",
        ]

    def test_multiple_prefixes(self):
        assert list(iter_candidates(
            ["pages/posts", "pages/application"], "show", ["html"]
        )) == [
            "pages/posts/show.html.jx",
            "pages/posts/show.jx",
            "pages/application/show.html.jx",
            "pages/application/show.jx",
        ]

    def test_custom_handler(self):
        assert list(iter_candidates(
            ["pages/x"], "show", ["html"], handler="haml"
        )) == [
            "pages/x/show.html.haml",
            "pages/x/show.haml",
        ]


class TestResolveTemplate:
    def test_picks_format_specific(self):
        cat = FakeCatalog([
            "pages/posts/show.json.jx",
            "pages/posts/show.jx",
        ])
        name = resolve_template(
            cat, ["pages/posts"], "show",
            accept=["application/json"], default_format="html",
        )
        assert name == "pages/posts/show.json.jx"

    def test_falls_back_to_bare(self):
        cat = FakeCatalog(["pages/posts/show.jx"])
        name = resolve_template(
            cat, ["pages/posts"], "show",
            accept=["text/html"], default_format="html",
        )
        assert name == "pages/posts/show.jx"

    def test_falls_back_to_next_prefix(self):
        cat = FakeCatalog(["pages/application/error.jx"])
        name = resolve_template(
            cat, ["pages/posts", "pages/application"], "error",
            accept=[], default_format="html",
        )
        assert name == "pages/application/error.jx"

    def test_empty_accept_uses_default_format(self):
        cat = FakeCatalog(["pages/posts/show.html.jx"])
        name = resolve_template(
            cat, ["pages/posts"], "show",
            accept=[], default_format="html",
        )
        assert name == "pages/posts/show.html.jx"

    def test_missing_raises(self):
        cat = FakeCatalog([])
        with pytest.raises(ComponentNotFoundError) as exc:
            resolve_template(
                cat, ["pages/posts"], "show",
                accept=["text/html"], default_format="html",
            )
        # Message should list what was tried, for debugging
        assert "pages/posts/show.html.jx" in str(exc.value)
        assert "pages/posts/show.jx" in str(exc.value)
