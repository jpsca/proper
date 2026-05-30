# Locales folder

Files in the config/locales folder are used for internationalization and
are automatically loaded by Proper. To use locales other than English,
add the necessary files to this directory.

To translate strings, call `app.i18n`:

```python
app.i18n("hello")
```

In views, this is aliased to just `_`:

```html+jinja
{{ _('hello') }}
```

The default `en.yml` locale in this directory contains a sample translation string:

```yaml
en:
  hello: "Hello world"
```

This means that in the `en` locale, the key `hello` maps to the `"Hello world"` string.
When the current locale is `en`, this:

```html+jinja
<h1>{{ _('hello') }}</h1>
```

will render as

```html
<h1>Hello world</h1>
```

To learn more about the API, please read the Proper Internationalization guide
at https://properproject.org/docs/i18n.

Be aware that YAML interprets the following case-insensitive strings as
booleans: `true`, `false`, `on`, `off`, `yes`, `no`. Therefore, these strings
must be quoted to be interpreted as strings. For example:

```yaml
en:
  "yes": yup
  enabled: "ON"
```
