from proper.helpers import dom_id


def test_dom_id():
    class Post:
        def __init__(self, pk) -> None:
            self._pk = pk

    assert dom_id(Post(45)) == "post_45"
    assert dom_id(Post(None)) == "new_post"
    assert dom_id(Post((12, 36))) == "post_12_36"
    assert dom_id(Post(("lorem", "ipsum"))) == "post_lorem_ipsum"

    assert dom_id(Post) == "post"
    assert dom_id(Post, "custom") == "custom_post"


def test_dom_id_to_key():
    class Post:
        def __init__(self, pk, slug) -> None:
            self._pk = pk
            self._slug = slug

        def to_key(self):
            return self._slug

    assert dom_id(Post(45, "lorem")) == "post_lorem"
    assert dom_id(Post(45, (12, 36))) == "post_12_36"
    assert dom_id(Post(45, ("lorem", "ipsum"))) == "post_lorem_ipsum"

    assert dom_id(Post(None, "ipsum")) == "post_ipsum"
    assert dom_id(Post(None, 0)) == "post_0"

    assert dom_id(Post(None, None)) == "new_post"
    assert dom_id(Post(None, "")) == "new_post"
    assert dom_id(Post(None, False)) == "new_post"

    assert dom_id(Post) == "post"
    assert dom_id(Post, "custom") == "custom_post"
