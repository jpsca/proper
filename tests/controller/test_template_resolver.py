import pytest

from proper.controller import template_resolver
from proper.controller.template_resolver import (
    find_template,
    formats_for,
    formats_for_header,
    iter_candidates,
)
from proper.core.request.headers import parse_accept
from proper.views import ComponentNotFoundError


class FakeCatalog:
    def __init__(self, names):
        self.names = set(names)
        self.probed = []

    def has_component(self, name):
        self.probed.append(name)
        return name in self.names


class TestFormatsFor:
    def test_single_mime(self):
        assert formats_for(["application/json"], "html") == ("json",)

    def test_preserves_order(self):
        assert formats_for(["application/json", "text/html"], "html") == ("json", "html")

    def test_stops_at_wildcard_with_the_default(self):
        assert formats_for(["text/csv", "*/*", "application/json"], "html") == ("csv", "html")

    def test_skips_unknown_mimes(self):
        assert formats_for(["application/x-made-up", "text/html"], "html") == ("html",)

    def test_empty(self):
        assert formats_for([], "html") == ("html",)

    def test_turbo_stream_mime(self):
        # Registered by importing `proper.turbo`; routes a Turbo request to a
        # `.turbo_stream.jx` template, falling back to `.html`.
        assert formats_for(
            ["text/vnd.turbo-stream.html", "text/html"], "html"
        ) == ("turbo_stream", "html")


class TestIterCandidates:
    def test_single_prefix_single_format(self):
        assert list(iter_candidates(["posts"], "show", ["html"])) == [
            "posts/show.html.jx",
            "posts/show.jx",
        ]

    def test_multiple_formats(self):
        assert list(iter_candidates(["posts"], "show", ["json", "html"])) == [
            "posts/show.json.jx",
            "posts/show.html.jx",
            "posts/show.jx",
        ]

    def test_multiple_prefixes(self):
        assert list(iter_candidates(
            ["posts", "application"], "show", ["html"]
        )) == [
            "posts/show.html.jx",
            "posts/show.jx",
            "application/show.html.jx",
            "application/show.jx",
        ]

    def test_custom_handler(self):
        assert list(iter_candidates(
            ["x"], "show", ["html"], handler="haml"
        )) == [
            "x/show.html.haml",
            "x/show.haml",
        ]


class TestFindTemplate:
    def test_picks_format_specific(self):
        cat = FakeCatalog([
            "posts/show.json.jx",
            "posts/show.jx",
        ])
        name = find_template(
            cat, ["posts"], "show", formats_for(["application/json"], "html"),
        )
        assert name == "posts/show.json.jx"

    def test_falls_back_to_bare(self):
        cat = FakeCatalog(["posts/show.jx"])
        name = find_template(
            cat, ["posts"], "show", formats_for(["text/html"], "html"),
        )
        assert name == "posts/show.jx"

    def test_falls_back_to_next_prefix(self):
        cat = FakeCatalog(["application/error.jx"])
        name = find_template(
            cat, ["posts", "application"], "error", formats_for([], "html"),
        )
        assert name == "application/error.jx"

    def test_empty_accept_uses_default_format(self):
        cat = FakeCatalog(["posts/show.html.jx"])
        name = find_template(
            cat, ["posts"], "show", formats_for([], "html"),
        )
        assert name == "posts/show.html.jx"

    def test_missing_raises(self):
        cat = FakeCatalog([])
        with pytest.raises(ComponentNotFoundError) as exc:
            find_template(
                cat, ["posts"], "show", formats_for(["text/html"], "html"),
            )
        # Message should list what was tried, for debugging
        assert "posts/show.html.jx" in str(exc.value)
        assert "posts/show.jx" in str(exc.value)


# --- formats_for_header ---

ACCEPTS = [
    None,
    "",
    "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "application/json",
    "application/json, text/plain, */*",
    "text/plain;q=0.5, application/json",
    "image/avif,image/webp,*/*",
    "x/unknown",
]


@pytest.mark.parametrize("accept", ACCEPTS)
@pytest.mark.parametrize("default_format", ["html", "json"])
def test_formats_for_header_is_formats_for_of_the_parsed_header(
    accept, default_format, monkeypatch
):
    monkeypatch.setattr(template_resolver, "_FORMATS", {})
    expected = formats_for(parse_accept(accept), default_format)
    assert formats_for_header(accept, default_format) == expected
    # and the second time, from what it remembered
    assert formats_for_header(accept, default_format) == expected
    assert template_resolver._FORMATS[(accept, default_format)] == expected


def test_formats_for_header_remembers_a_bounded_number(monkeypatch):
    monkeypatch.setattr(template_resolver, "_FORMATS", {})
    monkeypatch.setattr(template_resolver, "MAX_ACCEPT_HEADERS", 2)
    formats_for_header("text/html", "html")
    formats_for_header("application/json", "html")
    assert formats_for_header("text/plain", "html") == ("txt",)
    assert len(template_resolver._FORMATS) == 2
    assert ("text/plain", "html") not in template_resolver._FORMATS
