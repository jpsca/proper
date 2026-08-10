---
title: View Helpers
description:
number_headers: true
---

# View Helpers

The following outlines the view helpers available in your views. It serves as a good starting point, but reviewing the [full API Documentation](/docs/api/view_helpers) is also recommended, as it covers all of the helpers in more detail.

These are the ones **added by Proper**, Jinja (the template engine Jx is based on) [include some more builtin filters](https://tedboy.github.io/jinja2/templ14.html).

All of these helpers _can_ be also used in your views with the pipe operator. For example, `{{value|format_date(args)}}` instead of `{{format_date(value, args)}}`.

---

## Format Dates

### format_date

Formats a date/datetime according to the current locale and timezone.

```python
format_date(date(2007, 4, 1), locale='en_US')
# => 'Apr 1, 2007'

format_date(date(2007, 4, 1, 15, 30), locale='en_US')
# => 'Apr 1, 2007, 3:30:00\u202fPM'
```

You can also specify a custom date pattern:

```python
format_date(date(2007, 4, 1), "EEE, MMM d, ''yy", locale='en')
# => "Sun, Apr 1, '07"
```

See the [format_date API Documentation](/docs/api/view_helpers#format_date) for more information.

### format_time

Formats a time according to the current locale and timezone.
    
```python
format_time(time(15, 30), locale='en_US')
# => '3:30:00\u202fPM'

format_time(time(15, 30), format='short', locale='de_DE')
# => '15:30'
```

You can also specify a custom time pattern:

```python
format_time(time(15, 30), "hh 'o''clock' a", locale='en')
# => "03 o'clock PM"
```

See the [format_time API Documentation](/docs/api/view_helpers#format_time) for more information.

### format_timedelta

Formats a timedelta according to the rules of the given locale.

```python
format_timedelta(timedelta(weeks=12), locale='en_US')
# => '3 months'

format_timedelta(timedelta(seconds=1), locale='es')
# => '1 segundo'
```

The granularity parameter can be provided to alter the lowest unit
presented, which defaults to a second.

```python
format_timedelta(timedelta(hours=3), granularity='day', locale='en_US')
# => '1 day'
```

See the [format_timedelta API Documentation](/docs/api/view_helpers#format_timedelta) for more information.

### format_interval

Formats an interval between two dates or times according to the timezone and locale's rules.

```python
format_interval(time(5, 12), time(16, 24), "Hm", locale="en_GB")
# => '5:12–16:24'

format_interval(time(5, 12), time(16, 24), "hm", locale="en_US")
# => '5:12\u202fAM\u2009–\u20094:24\u202fPM'

format_interval(date(2016, 1, 15), date(2016, 1, 17), "yMd", locale="fi")
# => '15.–17.1.2016'
```

See the [format_interval API Documentation](/docs/api/view_helpers#format_interval) for more information.

---

## Format Numbers

For these helpers, the number formatted van be an integer, a float, a string, or a Decimal.

### format_size

Format a byte count as a human-readable string with binary (1024) units.

```python
format_size(120)
# => '120 Bytes'

format_size(1024)
# => '1 KB'

format_size(15_678)
# => '15.3 KB'

format_size(133_235_678)
# => '127 MB'

format_size(133_235_678, precision=5, locale="de")
# => '127,06 MB'
```

See the [format_size API Documentation](/docs/api/view_helpers#format_size) for more information.

### format_decimal

Formats a number for a specific locale.

```python
format_decimal(12_345.5, locale='en_US')
# => '12,345.5'

format_decimal(1.2345, locale='de')
# => '1,234'
```

See the [format_decimal API Documentation](/docs/api/view_helpers#format_decimal) for more information.

### format_compact_decimal

Like `format_decimal` but in compact form.

```python
format_compact_decimal(12_345, format_type="short", locale='en_US')
# => '12K'

format_compact_decimal(12_345, format_type="long", locale='en_US')
# => '12 thousand'

format_compact_decimal(12_345, format_type="short",
    locale='en_US', fraction_digits=2)
# => '12.34K'
```

See the [format_compact_decimal API Documentation](/docs/api/view_helpers#format_compact_decimal) for more information.

### format_currency

Formats a number as a currency value,
following the locale's formatting rules.

```python
format_currency(1_099.98, 'USD', locale='en_US')
# => '$1,099.98'

format_currency(1_099.98, 'USD', locale='es_CO')
# => 'US$1.099,98'

format_currency(1_099.98, 'EUR', locale='de_DE')
# => '1.099,98\xa0\u20ac'
```

See the [format_currency API Documentation](/docs/api/view_helpers#format_currency) for more information.

### format_compact_currency

Like `format_currency` but in compact form.

```python
format_compact_currency(12_345, 'USD', locale='en_US')
# => '$12K'

format_compact_currency(123_456_789, 'USD', locale='en_US', fraction_digits=2)
# => '$123.46M'

format_compact_currency(123_456_789, 'EUR', locale='de_DE', fraction_digits=1)
# => '123,5\xa0Mio.\xa0€'
```

See the [format_compact_currency API Documentation](/docs/api/view_helpers#format_compact_currency) for more information.

### format_percent

Return formatted percent value for a specific locale.

```python
format_percent(0.34, locale='en_US')
# => '34%'

format_percent(25.1234, locale='en_US')
# => '2,512%'

format_percent(25.1234, locale='sv_SE')
# => '2\xa0512\xa0%'
```

See the [format_percent API Documentation](/docs/api/view_helpers#format_percent) for more information.

---

## Format Text

See the [format_date API Documentation](/docs/api/view_helpers#format_date) for more information.

### format_list

Format the items in `lst` as a list.

```python
format_list(['apples', 'oranges', 'pears'], locale='en')
# => 'apples, oranges, and pears'

format_list(['apples', 'oranges', 'pears'], locale='zh')
# => 'apples、oranges和pears'

format_list(['omena', 'peruna', 'aplari'], style='or', locale='fi')
# => 'omena, peruna tai aplari'
```

Avaliable styles:

`standard`
: A typical 'and' list for arbitrary placeholders. eg. "January, February, and March"

`standard-short`
: A short version of an 'and' list, suitable for use with short or abbreviated placeholder values. eg. "Jan., Feb., and Mar."

`or`
: A typical 'or' list for arbitrary placeholders. eg. "January, February, or March"

`or-short`
: A short version of an 'or' list. eg. "Jan., Feb., or Mar."

`unit`
: A list suitable for wide units. eg. "3 feet, 7 inches"

`unit-short`
: A list suitable for short units eg. "3 ft, 7 in"

`unit-narrow`
: A list suitable for narrow units, where space on the screen is very limited. eg. "3′ 7″"

Not all styles are necessarily available in all locales.

See the [format_list API Documentation](/docs/api/view_helpers#format_list) for more information.

### truncate

Truncate a string to a specified length.

The length is specified with the second parameter (`length`) which defaults to `255`.
If the third parameter (`killwords`) is `True` the filter will cut the text at length.
Otherwise it will discard the last word.

If the text was in fact truncated it will append an ellipsis sign (`"..."`).
You can specify a different sign using the fourth (`end`) parameter.

Strings that only exceed the length by the tolerance margin given in the fifth (`leeway`)
parameter will not be truncated.

```python
truncate("foo bar baz qux", 9) }}
# -> "foo..."

truncate("foo bar baz qux", 9, True) }}
# -> "foo ba..."

truncate("foo bar baz qux", 11) }}
# -> "foo bar baz qux"

truncate("foo bar baz qux", 11, False, '...', 0) }}
# -> "foo bar..."
```

See the [truncate API Documentation](/docs/api/view_helpers#truncate) for more information.

---


## Navigation

### url_for

Builds a URL for the route with the given name, filling in placeholders
with the given kwargs or with attributes of the given object.

```python
url_for("Page.show", object=page)
# => "/pages/123"

url_for("Page.show", page_id=123, _anchor="section1")
# => "/pages/123#section1"

# The host is determined by the route's host constraint
# or by the application's default host.
url_for("Page.show", page_id=123, _full=True)
# => "http://www.example.com/pages/123#section1"
```

See the [url_for API Documentation](/docs/api/view_helpers#url_for) for more information.

### url_is

Tells if the URL for the given route name and parameters is the same as the current URL
as reported by `current.request.path` (ignoring trailing slashes and anchors).
This is useful for things like active links in navigation bars.

If a current URL is not given, it defaults to `current.request.path`.
This is useful if you want to compare to a different URL than the current
request's path, for example when you are building a link to a section in the
same page and want to compare

```python
url_is("Page.show", page_id=123, curr_url="/pages/123#section1")
# => True

url_is("Page.show", page_id=123, curr_url="/pages")
# => False
```

See the [url_is API Documentation](/docs/api/view_helpers#url_is) for more information.

### url_startswith

Tells if the URL for the given route name and parameters starts with the current URL
as reported by `current.request.path` (ignoring trailing slashes and anchors).
This is useful for things like active links to sections in navigation bars.

```python
url_startswith("Page.show", page_id=123, curr_url="/pages/123#section1")
# => True

url_startswith("Page.show", page_id=123, curr_url="/pages/")
# => True
```

See the [url_startswith API Documentation](/docs/api/view_helpers#url_startswith) for more information.

### dom_id

Generate a stable id for an object, suitable for use in HTML element ids.

It uses the object's class name and primary key (if available) to generate a unique id.
If there is no primary key, prefix with “new_” instead.

```python
dom_id(Post.get(45))   # => "post_45"
dom_id(Post.create())  # => "new_post"
```

The `prefix` argument can be used to add a namespace to the id, for example:

```python
dom_id(Post.get(45), prefix="edit")  # => "edit_post_45"
```

If the object has a `to_key()` method, it will be used to get the key instead of the primary key.
This allows you to customize the key generation for privacy-sensitive or more complex models.

If the object is a class rather than an instance, only the class name is used:

```python
dom_id(Post)            # => "post"
dom_id(Post, "custom")  # => "custom_post"
```

See the [dom_id API Documentation](/docs/api/view_helpers#dom_id) for more information.

---


## Assets

### assets.render_css

Uses the `assets.collect_css()` list to generate an HTML fragment
with `<link rel="stylesheet" href="{url}">` tags.

See the [render_css API Documentation](/docs/api/view_helpers#render_css) for more information.

### assets.render_js

Uses the `assets.collect_js()` list to generate an HTML fragment
with `<script type="module" src="{url}"></script>` tags.

See the [render_js API Documentation](/docs/api/view_helpers#render_js) for more information.

### assets.render

Calls `assets.render_css()` and `assets.render_js()` to generate
an HTML fragment with `<link rel="stylesheet" href="{url}">`
and `<script type="module" src="{url}"></script>` tags.

See the [render_assets API Documentation](/docs/api/view_helpers#render_assets) for more information.

### assets.collect_css

Returns a list of CSS files for the component and its children.

See the [collect_css API Documentation](/docs/api/view_helpers#collect_css) for more information.

### assets.collect_js

Returns a list of JS files for the component and its children.

See the [collect_js API Documentation](/docs/api/view_helpers#collect_js) for more information.

### render_importmap

Render a script tag containing the import map for the app's assets.

An import map is a JSON object that maps module specifiers to URLs, allowing
you to use bare module specifiers in your JavaScript code. For example, with
the following import map:

```html
<script type="importmap">
{
    "imports": {
        "my-lib": "/static/my-lib.js"
    }
}
</script>
```

You can import `my-lib` in your JavaScript code like this:

```javascript
import { something } from "my-lib";
```

The `render_importmap` function generates a script tag with the import map based on
the app's configuration. It looks for an `IMPORT_MAP` configuration variable, which
should be a dictionary mapping module specifiers to asset paths or URLs.

See the [render_importmap API Documentation](/docs/api/view_helpers#render_importmap) for more information.
