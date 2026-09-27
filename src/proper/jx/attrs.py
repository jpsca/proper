"""
Jx | Copyright (c) Juan-Pablo Scaletti
"""

import builtins
import typing as t
from collections import UserString
from functools import cached_property

from markupsafe import Markup


CLASS_KEY = "class"
CLASS_ALT_KEY = "classes"
CLASS_KEYS = (CLASS_KEY, CLASS_ALT_KEY)


def quote(value: "str | LazyString") -> str:
    if isinstance(value, LazyString) and value.is_safe:
        # Already knows how to render itself as HTML; escaping it again would
        # turn its entities into visible text.
        text = value.data
    else:
        # `&` first, so the `&quot;` produced below is not escaped a second time.
        text = str(value).replace("&", "&amp;").replace("<", "&lt;")

    if '"' in text:
        if "'" in text:
            text = text.replace('"', "&quot;")
            return f'"{text}"'
        else:
            return f"'{text}'"

    return f'"{text}"'


class LazyString(UserString):
    # `UserString` declares no `__slots__`, so instances keep a (lazily created)
    # `__dict__` regardless -- which is what `data` below needs. This slot is
    # still worth it: it keeps `_seq` out of that dict, so a LazyString that is
    # never stringified stays small and never materialises the dict at all.
    __slots__ = ("_seq",)

    def __init__(self, seq):
        """
        Behave like regular strings, but the actual casting of the initial value
        is deferred until the value is actually required.
        """
        self._seq = seq

    @cached_property
    def data(self):
        return str(self._seq)

    @property
    def is_safe(self) -> bool:
        """Whether the wrapped value already carries its own HTML representation."""
        return hasattr(self._seq, "__html__")


class Attrs:
    _classes: tuple[str, ...]
    _attributes: dict[str, str | LazyString]
    # `builtins.` because this class defines a `set` method of its own.
    _properties: builtins.set[str]

    def __init__(self, attrs: "dict[str, t.Any | LazyString]") -> None:
        """
        Contains all the HTML attributes/properties (a property is an
        attribute without a value) passed to a component but that weren't
        in the declared attributes list.

        For HTML classes you can use the name "classes" (instead of "class")
        if you need to.

        **NOTE**: The string values passed to this class, are not cast to `str` until
        the string representation is actually needed, for example when
        `attrs.render()` is invoked.

        """
        # Fast path: empty attrs (common for most child components)
        if not attrs:
            self._classes = ()
            self._attributes = {}
            self._properties = set()
            return

        attributes: "dict[str, str | LazyString]" = {}
        properties: set[str] = set()

        # Read, never pop: `attrs` belongs to the caller. The class keys are
        # skipped in the loop below instead.
        cls1 = attrs.get(CLASS_KEY, "")
        cls2 = attrs.get(CLASS_ALT_KEY, "")
        if cls1 or cls2:
            class_names = f"{cls1} {cls2}".split()
            classes = []
            for name in class_names:
                if name and name not in classes:
                    classes.append(name)
            self._classes = tuple(classes)
        else:
            self._classes = ()

        for name, value in attrs.items():
            if name.startswith("_") or name in CLASS_KEYS:
                continue
            name = name.replace("_", "-")
            if value is True:
                properties.add(name)
            elif value is not False and value is not None:
                attributes[name] = LazyString(value)

        self._attributes = attributes
        self._properties = properties

    @property
    def classes(self) -> str:
        """
        All the HTML classes separated by a space.

        Example:

            ```python
            attrs = Attrs({"class": "italic bold bg-blue wide abcde"})
            attrs.set(class="bold text-white")
            print(attrs.classes)
            italic bold bg-blue wide abcde text-white
            ```

        """
        return " ".join(self._classes)

    @property
    def as_dict(self) -> dict[str, t.Any]:
        """
        An ordered dict of all the attributes and properties, both
        sorted by name before join.

        Example:

            ```python
            attrs = Attrs({
            "class": "lorem ipsum",
            "data_test": True,
            "hidden": True,
            "aria_label": "hello",
            "id": "world",
            })
            attrs.as_dict
            {
                "aria_label": "hello",
                "class": "lorem ipsum",
                "id": "world",
                "data_test": True,
                "hidden": True
            }
            ```

        """
        attributes = self._attributes.copy()
        classes = self.classes
        if classes:
            attributes[CLASS_KEY] = classes

        out: dict[str, t.Any] = dict(sorted(attributes.items()))
        for name in sorted(self._properties):
            out[name] = True
        return out

    def __getitem__(self, name: str) -> t.Any:
        return self.get(name)

    def __delitem__(self, name: str) -> None:
        self._remove(name)

    def __str__(self) -> str:
        return str(self.as_dict)

    def set(self, **kw) -> None:
        """
        Sets an attribute or property

        - Pass a name and a value to set an attribute (e.g. `type="text"`)
        - Use `True` as a value to set a property (e.g. `disabled`)
        - Use `False` to remove an attribute or property
        - If the attribute is "class", the new classes are appended to
          the old ones (if not repeated) instead of replacing them.
        - The underscores in the names will be translated automatically to dashes,
          so `aria_selected` becomes the attribute `aria-selected`.

        Example:

            ```python
            attrs = Attrs({"secret": "qwertyuiop"})
            attrs.set(secret=False)
            attrs.as_dict
            {}

            attrs.set(unknown=False, lorem="ipsum", count=42, data_good=True)
            attrs.as_dict
            {"count":42, "lorem":"ipsum", "data_good": True}

            attrs = Attrs({"class": "b c a"})
            attrs.set(class="c b f d e")
            attrs.as_dict
            {"class": "b c a f d e"}
            ```

        """
        for name, value in kw.items():
            name = name.replace("_", "-")
            if value is False or value is None:
                self._remove(name)
                continue

            if name in CLASS_KEYS:
                self.add_class(value)
            elif value is True:
                self._properties.add(name)
            else:
                self._attributes[name] = LazyString(value)

    def setdefault(self, **kw) -> None:
        """
        Adds an attribute, but only if it's not already present.

        The underscores in the names will be translated automatically to dashes,
        so `aria_selected` becomes the attribute `aria-selected`.

        Example:

            ```python
            attrs = Attrs({"lorem": "ipsum"})
            attrs.setdefault(tabindex=0, lorem="meh")
            attrs.as_dict
            # "tabindex" changed but "lorem" didn't
            {"lorem": "ipsum", tabindex: 0}
            ```

        """
        for name, value in kw.items():
            name = name.replace("_", "-")
            if value is False or value is None:
                continue

            if name in CLASS_KEYS:
                if not self._classes:
                    self.add_class(value)
                continue

            if value is True:
                if name not in self._properties:
                    self._properties.add(name)
            elif name not in self._attributes:
                self._attributes[name] = LazyString(value)

    def add_class(self, *values: str) -> None:
        """
        Adds one or more classes to the end of the list of classes,
        if not already present.

        Arguments:
            values:
                One or more class names to add, separated by spaces.

        Example:

            ```python
            attrs = Attrs({"class": "a b c"})
            attrs.add_class("c d")
            attrs.as_dict
            {"class": "a b c d"}
            ```

        """
        new = list(self._classes)
        for names in values:
            for name in names.strip().split():
                if name not in new:
                    new.append(name)
        self._classes = tuple(new)

    def prepend_class(self, *values: str) -> None:
        """
        Adds one or more classes to the beginning of the list of classes,
        if not already present.

        Arguments:
            values:
                One or more class names to add, separated by spaces.

        Example:

            ```python
            attrs = Attrs({"class": "a b c"})
            attrs.prepend_class("c d |")
            attrs.as_dict
            {"class": "d | a b c"}
            ```

        """
        new = []
        for names in values:
            for name in names.strip().split():
                if name not in self._classes and name not in new:
                    new.append(name)

        self._classes = tuple(new) + self._classes

    def remove_class(self, *names: str) -> None:
        """
        Removes one or more classes from the list of classes.

        Example:

            ```python
            attrs = Attrs({"class": "a b c"})
            attrs.remove_class("c", "d")
            attrs.as_dict
            {"class": "a b"}
            ```

        """
        self._classes = tuple(c for c in self._classes if c not in names)

    def get(self, name: str, default: t.Any = None) -> t.Any:
        """
        Returns the value of the attribute or property,
        or the default value if it doesn't exist.

        Arguments:

            name:
                The name of the attribute or property to get.

            default:
                The default value to return if the attribute or property doesn't exist.

        Example:

            ```python
            attrs = Attrs({"lorem": "ipsum", "hidden": True})

            attrs.get("lorem", default="bar")
            'ipsum'

            attrs.get("foo")
            None

            attrs.get("foo", default="bar")
            'bar'

            attrs.get("hidden")
            True
            ```

        """
        name = name.replace("_", "-")
        if name in CLASS_KEYS:
            return self.classes
        if name in self._attributes:
            return self._attributes[name]
        if name in self._properties:
            return True
        return default

    def render(self, **kw) -> str:
        """
        Renders the attributes and properties as a string.

        Any arguments you use with this function are merged with the existing
        attributes/properties by the same rules as the `Attrs.set()` function:

        - Pass a name and a value to set an attribute (e.g. `type="text"`)
        - Use `True` as a value to set a property (e.g. `disabled`)
        - Use `False` to remove an attribute or property
        - If the attribute is "class", the new classes are appended to
          the old ones (if not repeated) instead of replacing them.
        - The underscores in the names will be translated automatically to dashes,
          so `aria_selected` becomes the attribute `aria-selected`.

        To provide consistent output, the attributes and properties
        are sorted by name and rendered like this:
        `<sorted attributes> + <sorted properties>`.

        Values are HTML-escaped, unless they are markup objects (those with an
        `__html__` method, e.g. the result of Jinja's `|safe`), which are used
        as-is.

        Example:

            ```python
            attrs = Attrs({"class": "ipsum", "data_good": True, "width": 42})

            attrs.render()
            'class="ipsum" width="42" data-good'

            attrs.render(class="abc", data_good=False, tabindex=0)
            'class="abc ipsum" width="42" tabindex="0"'  # render classes come first
            ```

        """
        if kw:
            # Work on copies so render() doesn't mutate self
            render_classes = None
            for key in CLASS_KEYS:
                if key in kw:
                    render_classes = kw.pop(key)

            attributes = dict(self._attributes)
            classes = list(self._classes)
            properties = set(self._properties)

            for name, value in kw.items():
                name = name.replace("_", "-")
                if value is False or value is None:
                    attributes.pop(name, None)
                    properties.discard(name)
                elif value is True:
                    properties.add(name)
                else:
                    attributes[name] = LazyString(value)

            if render_classes:
                new = [
                    name
                    for name in render_classes.strip().split()
                    if name not in classes
                ]
                classes = new + classes
        else:
            attributes = self._attributes
            classes = list(self._classes)
            properties = self._properties

        # Fast path: nothing to render
        if not attributes and not classes and not properties:
            return Markup("")

        # Build sorted attributes, inserting class in order
        if classes:
            items = {**attributes, CLASS_KEY: " ".join(classes)}
        else:
            items = attributes

        if len(items) > 1:
            items = dict(sorted(items.items()))

        html_attrs = [
            f"{name}={quote(value)}"
            for name, value in items.items()
        ]
        if properties:
            html_attrs.extend(sorted(properties))

        return Markup(" ".join(html_attrs))

    # Private

    def _remove(self, name: str) -> None:
        """
        Removes an attribute or property.
        """
        if name in CLASS_KEYS:
            self._classes = ()
        else:
            self._attributes.pop(name, None)
            self._properties.discard(name)
